"""
MemoryManager — 记忆系统顶层接口

对外暴露的核心 API:
  - remember(): 从 LLM 交互中提取并存储记忆
  - recall():   根据查询检索相关记忆
  - inject():   将记忆注入 system prompt
  - forget():   删除指定记忆
  - list():     列出项目记忆

集成方式 (3 步):
  1. manager = MemoryManager(storage_dir="./memories")
  2. LLM 调用后: await manager.remember(...)
  3. LLM 调用前: await manager.recall(...) → manager.inject_memories(...)
"""

import asyncio
import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from .bm25 import BM25Index
from .models import MemoryEntry, MemoryType, RecallResult
from .store import MemoryStore
from .tokenizer import tokenize_for_index

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# type alias
# ---------------------------------------------------------------------------

ExtractFn = Callable[[str], Any]  # async (prompt: str) -> str
"""LLM 提取函数签名: 接收提取 prompt, 返回 JSON 字符串."""


# ---------------------------------------------------------------------------
# 默认的记忆提取 Prompt
# ---------------------------------------------------------------------------

EXTRACT_PROMPT = """你是一个知识提取助手。分析以下 LLM 交互, 提取 2-3 条对后续设计有价值的记忆。

## 上下文
用户在做什么: {context}
LLM 调用类型: {call_type}
用户输入摘要: {user_input}

## LLM 输出 (截取前 2000 字符)
{llm_output}

## 用户反馈
{user_feedback}

## 要求
返回 JSON 数组, 每条记忆包含:
- memory_type: "preference" | "decision" | "rejection" | "convention" | "insight"
- content: 核心 insight (1-2 句话, 中英文均可, 简洁明确)
- tags: 2-4 个关键词标签
- importance: 0.0~1.0 重要性 (重要设计决策=0.9, 一般偏好=0.5, 临时备注=0.2)

只返回有效 JSON 数组, 不要额外解释.

## 示例
```json
[
  {{
    "memory_type": "preference",
    "content": "用户偏好使用组合模式而非继承来复用代码",
    "tags": ["设计模式", "组合优于继承", "类图"],
    "importance": 0.8
  }}
]
```"""


# ---------------------------------------------------------------------------
# MemoryManager
# ---------------------------------------------------------------------------

class MemoryManager:
    """
    记忆系统管理器 — 顶层接口.

    Parameters:
        storage_dir: 记忆文件存储目录
        max_entries: 每个项目的最大记忆条数 (默认 50)

    Usage:
        mgr = MemoryManager("./memories")

        # 记录
        entries = await mgr.remember(
            project_id="blog_system",
            context="优化类图",
            llm_call_type="optimize",
            user_input="提高可扩展性",
            llm_output="...",
            extract_fn=my_chat_fn,
        )

        # 检索
        results = await mgr.recall("blog_system", "如何优化类图设计")

        # 注入
        prompt = mgr.inject_memories(system_prompt, results)
    """

    __slots__ = ("store", "indices", "_index_lock")

    def __init__(self, storage_dir: str = "./memories", max_entries: int = 50):
        self.store = MemoryStore(storage_dir, max_entries)
        # 每项目一个 BM25 索引 (lazy build)
        self.indices: Dict[str, BM25Index] = {}
        self._index_lock = asyncio.Lock()

    # ==================================================================
    # Public API
    # ==================================================================

    # ── remember ──────────────────────────────────────────────────

    async def remember(
        self,
        project_id: str,
        context: str,
        llm_call_type: str,
        user_input: str = "",
        llm_output: str = "",
        user_feedback: Optional[str] = None,
        extract_fn: Optional[ExtractFn] = None,
    ) -> List[MemoryEntry]:
        """
        LLM 调用后提取并存储记忆.

        Args:
            project_id:    项目标识
            context:       触发上下文描述
            llm_call_type: LLM 调用类型 (optimize | generate | pipeline_stage)
            user_input:    用户输入或原始 prompt (截断到 1000 字符)
            llm_output:    LLM 返回内容 (截断到 2000 字符)
            user_feedback: 用户反馈 (accepted | rejected | modified | None=None 表示未确认)
            extract_fn:    外部 LLM 调用函数, 用于自动提取记忆.
                           为 None 时跳过自动提取, 返回空列表.

        Returns:
            新创建的记忆条目列表
        """
        if extract_fn is None:
            logger.info(f"[MemoryManager] extract_fn is None, skipping auto-extract for {project_id}")
            return []

        # 1. 构建提取 prompt
        prompt = EXTRACT_PROMPT.format(
            context=context,
            call_type=llm_call_type,
            user_input=user_input[:1000],
            llm_output=llm_output[:2000],
            user_feedback=user_feedback or "未确认",
        )

        # 2. 调用外部 LLM 提取
        try:
            raw = await extract_fn(prompt)
            if asyncio.iscoroutine(raw):
                raw = await raw
        except Exception as exc:
            logger.error(f"[MemoryManager] extract_fn failed: {exc}")
            return []

        # 3. 解析 JSON
        items = self._parse_extract_result(raw)
        if not items:
            logger.info("[MemoryManager] No insights extracted from LLM response")
            return []

        # 4. 创建 MemoryEntry
        new_entries: List[MemoryEntry] = []
        for item in items:
            try:
                entry = MemoryEntry(
                    project_id=project_id,
                    memory_type=MemoryType(item.get("memory_type", "insight")),
                    context=context,
                    content=item.get("content", ""),
                    tags=item.get("tags", []),
                    importance=float(item.get("importance", 0.5)),
                    user_feedback=user_feedback,
                    source=llm_call_type,
                )
                self.store.add(entry)
                new_entries.append(entry)
            except (ValueError, KeyError) as exc:
                logger.warning(f"[MemoryManager] Skipping invalid memory item: {exc}")

        # 5. 重建 BM25 索引 (增量)
        if new_entries:
            await self._rebuild_index(project_id)

        logger.info(
            f"[MemoryManager] Remembered {len(new_entries)} new insight(s) for project '{project_id}'"
        )
        return new_entries

    # ── recall ───────────────────────────────────────────────────

    async def recall(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        max_tokens: int = 800,
        memory_types: Optional[List[MemoryType]] = None,
    ) -> List[RecallResult]:
        """
        LLM 调用前检索相关记忆.

        Args:
            project_id:   项目标识
            query:        查询文本 (通常是用户需求描述)
            top_k:        返回的最大记忆数
            max_tokens:   总 token 预算上限 (1 token ≈ 2 chars for Chinese)
            memory_types: 按类型过滤 (None = 所有类型)

        Returns:
            RecallResult 列表, 按 BM25 得分降序排列
        """
        # 确保索引存在
        index = await self._get_or_build_index(project_id)
        if index.doc_count == 0:
            return []

        # BM25 检索
        doc_ids_and_scores = index.search(query, top_k=top_k)

        # 构建 RecallResult
        results: List[RecallResult] = []
        total_chars = 0
        char_budget = max_tokens * 2  # 1 token ≈ 2 chars

        for doc_id, score in doc_ids_and_scores:
            entry = self.store.get(project_id, doc_id)
            if entry is None:
                continue

            # 按类型过滤
            if memory_types and entry.memory_type not in memory_types:
                continue

            results.append(RecallResult(entry=entry, score=score))
            total_chars += len(entry.content) + len(entry.context)

            # Token 预算保护
            if total_chars >= char_budget:
                break

        logger.info(
            f"[MemoryManager] Recalled {len(results)} memories for '{project_id}' "
            f"(query: {query[:50]}...)"
        )
        return results

    # ── inject ───────────────────────────────────────────────────

    @staticmethod
    def inject_memories(
        system_prompt: str,
        recall_results: List[RecallResult],
        section_title: str = "## 项目历史记忆",
    ) -> str:
        """
        将检索到的记忆注入 system prompt.

        Args:
            system_prompt:  原始 system prompt
            recall_results: recall() 返回的检索结果
            section_title:  记忆章节的标题

        Returns:
            拼接后的 system prompt

        Example:
            >>> enriched = MemoryManager.inject_memories(
            ...     "You are a UML design expert.",
            ...     [RecallResult(entry=..., score=1.23)]
            ... )
            >>> print(enriched)
            You are a UML design expert.

            ## 项目历史记忆
            以下是从过往交互中提取的设计上下文, 请在回答时参考:
            - [preference] 用户偏好组合优于继承 (score: 1.23)
        """
        if not recall_results:
            return system_prompt

        lines = [
            "",
            section_title,
            "以下是从过往交互中提取的设计上下文, 请在回答时参考:",
            "",
        ]
        for i, rr in enumerate(recall_results, 1):
            type_label = {
                MemoryType.PREFERENCE: "偏好",
                MemoryType.DECISION: "决策",
                MemoryType.REJECTION: "拒绝",
                MemoryType.CONVENTION: "规范",
                MemoryType.INSIGHT: "洞察",
            }.get(rr.entry.memory_type, "其他")

            tags_str = f" [{', '.join(rr.entry.tags)}]" if rr.entry.tags else ""
            lines.append(
                f"{i}. [{type_label}]{tags_str} {rr.entry.content} "
                f"_(相关性: {rr.score:.2f})_"
            )

        memory_section = "\n".join(lines)
        return system_prompt.rstrip() + "\n" + memory_section

    # ── forget ───────────────────────────────────────────────────

    async def forget(self, project_id: str, memory_id: str) -> bool:
        """
        删除一条记忆.

        Returns:
            True 若删除成功, False 若记忆不存在.
        """
        ok = self.store.delete(project_id, memory_id)
        if ok:
            await self._rebuild_index(project_id)
            logger.info(f"[MemoryManager] Forgot memory {memory_id[:8]}... from '{project_id}'")
        return ok

    # ── list ─────────────────────────────────────────────────────

    async def list_memories(
        self,
        project_id: str,
        memory_type: Optional[MemoryType] = None,
    ) -> List[MemoryEntry]:
        """
        列出项目的所有记忆.

        Args:
            project_id:  项目标识
            memory_type: 按类型过滤 (None = 所有)

        Returns:
            MemoryEntry 列表 (按时间降序)
        """
        entries = self.store.list_by_project(project_id)
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        return entries

    # ── stats ────────────────────────────────────────────────────

    async def stats(self, project_id: str) -> Dict[str, Any]:
        """获取项目记忆统计."""
        entries = self.store.list_by_project(project_id)
        type_counts: Dict[str, int] = {}
        for e in entries:
            t = e.memory_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        index = self.indices.get(project_id)
        return {
            "project_id": project_id,
            "total_memories": len(entries),
            "by_type": type_counts,
            "indexed_docs": index.doc_count if index else 0,
            "index_vocab": index.vocab_size if index else 0,
        }

    # ==================================================================
    # Internal helpers
    # ==================================================================

    async def _get_or_build_index(self, project_id: str) -> BM25Index:
        """获取或懒构建项目的 BM25 索引."""
        if project_id in self.indices:
            return self.indices[project_id]

        async with self._index_lock:
            # Double-check
            if project_id in self.indices:
                return self.indices[project_id]

            index = BM25Index()
            entries = self.store.list_by_project(project_id)
            for entry in entries:
                # 索引: content + tags + context 合并
                text = f"{entry.content} {' '.join(entry.tags)} {entry.context}"
                index.add(entry.id, text)

            self.indices[project_id] = index
            logger.info(
                f"[MemoryManager] Built index for '{project_id}': "
                f"{index.doc_count} docs, {index.vocab_size} terms"
            )
            return index

    async def _rebuild_index(self, project_id: str) -> None:
        """重建项目的 BM25 索引 (in-place 更新)."""
        async with self._index_lock:
            index = BM25Index()
            entries = self.store.list_by_project(project_id)
            for entry in entries:
                text = f"{entry.content} {' '.join(entry.tags)} {entry.context}"
                index.add(entry.id, text)
            self.indices[project_id] = index

    @staticmethod
    def _parse_extract_result(raw: str) -> List[Dict[str, Any]]:
        """
        解析 LLM 返回的 JSON 提取结果.

        支持:
          - 纯 JSON 数组: [{"memory_type": ...}, ...]
          - Markdown code block: ```json [...] ```
          - 额外文字包裹
        """
        if not raw or not raw.strip():
            return []

        # 尝试提取 ```json ``` 代码块
        m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", raw, re.IGNORECASE)
        if m:
            raw = m.group(1)

        # 尝试找到第一个 [ 和最后一个 ]
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [item for item in parsed if isinstance(item, dict)]
            if isinstance(parsed, dict):
                return [parsed]
        except json.JSONDecodeError as exc:
            logger.warning(f"[MemoryManager] Failed to parse extract JSON: {exc}")
            logger.debug(f"Raw extract response: {raw[:500]}")

        return []
