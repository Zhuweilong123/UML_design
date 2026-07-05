"""
Memory System — 基于 BM25 稀疏向量的 LLM 跨会话记忆系统

核心组件:
  - MemoryManager: 顶层 API (remember / recall / inject / forget)
  - BM25Index:     BM25 检索索引
  - MemoryStore:   JSON 文件持久化
  - MemoryEntry:   记忆数据模型
  - tokenize():    中英混合分词

快速使用:
    from memory_system import MemoryManager, MemoryEntry, MemoryType, RecallResult

    manager = MemoryManager(storage_dir="./my_memories")

    # LLM 调用后记录
    entries = await manager.remember(
        project_id="blog_app",
        context="优化类图设计",
        llm_call_type="optimize",
        user_input="提高系统可扩展性",
        llm_output=llm_response,
        extract_fn=my_chat_fn,
    )

    # LLM 调用前检索
    results = await manager.recall("blog_app", "如何优化类图")

    # 注入 system prompt
    prompt = manager.inject_memories(system_prompt, results)
"""

from .manager import MemoryManager
from .models import MemoryEntry, MemoryType, RecallResult
from .bm25 import BM25Index
from .store import MemoryStore
from .tokenizer import tokenize, tokenize_for_index

__all__ = [
    "MemoryManager",
    "MemoryEntry",
    "MemoryType",
    "RecallResult",
    "BM25Index",
    "MemoryStore",
    "tokenize",
    "tokenize_for_index",
]

__version__ = "1.0.0"
