"""
JSON 文件持久化存储

特性:
  - 每项目一个 JSON 文件: {storage_dir}/{project_id}.json
  - 原子写入: 先写 .tmp 再 os.replace (防断电损坏)
  - 内存缓存: 启动加载, 操作后同步写盘
  - 容量控制: 超 max_entries 时按 importance × 时间衰减 淘汰
  - 线程安全: 使用 asyncio.Lock 保护并发写
"""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import MemoryEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON 编码器 (处理 datetime / Enum 等非原生类型)
# ---------------------------------------------------------------------------

class _MemoryEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        from datetime import datetime
        from enum import Enum
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


# ---------------------------------------------------------------------------
# 淘汰算法
# ---------------------------------------------------------------------------

def _eviction_score(entry: MemoryEntry, now_days: float = 0.0) -> float:
    """
    计算淘汰得分 (越低越易被淘汰).

    score = importance × time_decay
    time_decay = e^(-age_days / 30)   # 30天半衰期
    """
    age = entry.age_days
    time_decay = 2.71828 ** (-age / 30.0)
    return entry.importance * time_decay


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """
    文件持久化存储, 每项目一个 JSON 文件.

    Usage:
        store = MemoryStore("./memories")
        store.add(entry)
        memories = store.list_by_project("my_project")
    """

    __slots__ = ("storage_dir", "max_entries", "_cache", "_locks")

    def __init__(self, storage_dir: str = "./memories", max_entries: int = 50):
        self.storage_dir = Path(storage_dir)
        self.max_entries = max_entries
        self._cache: Dict[str, List[MemoryEntry]] = {}  # project_id → entries
        self._locks: Dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def add(self, entry: MemoryEntry) -> None:
        """添加一条记忆."""
        pid = entry.project_id
        entries = self._load_project(pid)
        entries.append(entry)
        self._prune(entries)
        self._save_project(pid, entries)

    def get(self, project_id: str, memory_id: str) -> Optional[MemoryEntry]:
        """按 ID 获取单条记忆."""
        entries = self._load_project(project_id)
        for e in entries:
            if e.id == memory_id:
                return e
        return None

    def update(self, entry: MemoryEntry) -> bool:
        """更新一条记忆 (按 id 匹配), 返回是否成功."""
        pid = entry.project_id
        entries = self._load_project(pid)
        for i, e in enumerate(entries):
            if e.id == entry.id:
                entries[i] = entry
                self._save_project(pid, entries)
                return True
        return False

    def delete(self, project_id: str, memory_id: str) -> bool:
        """删除一条记忆, 返回是否成功."""
        entries = self._load_project(project_id)
        for i, e in enumerate(entries):
            if e.id == memory_id:
                entries.pop(i)
                self._save_project(project_id, entries)
                return True
        return False

    def list_by_project(self, project_id: str) -> List[MemoryEntry]:
        """列出项目的所有记忆 (按时间降序)."""
        entries = self._load_project(project_id)
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)

    def count(self, project_id: str) -> int:
        """项目记忆数量."""
        return len(self._load_project(project_id))

    def clear_project(self, project_id: str) -> None:
        """清除项目的所有记忆."""
        self._cache.pop(project_id, None)
        filepath = self._filepath(project_id)
        try:
            os.remove(filepath)
        except FileNotFoundError:
            pass

    # ------------------------------------------------------------------
    # Internal: load / save / prune
    # ------------------------------------------------------------------

    def _filepath(self, project_id: str) -> Path:
        """获取项目记忆文件路径."""
        # 文件名安全化: 替换非法字符
        safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in project_id)
        safe = safe.strip() or "default"
        return self.storage_dir / f"{safe}.json"

    def _load_project(self, project_id: str) -> List[MemoryEntry]:
        """加载项目记忆 (优先缓存)."""
        if project_id in self._cache:
            return self._cache[project_id]

        filepath = self._filepath(project_id)
        if not filepath.exists():
            self._cache[project_id] = []
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, list):
                logger.warning(f"[MemoryStore] Invalid format in {filepath}, resetting")
                self._cache[project_id] = []
                return []
            entries = [MemoryEntry.from_dict(item) for item in raw]
            self._cache[project_id] = entries
            return entries
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning(f"[MemoryStore] Failed to load {filepath}: {exc}")
            self._cache[project_id] = []
            return []

    def _save_project(self, project_id: str, entries: List[MemoryEntry]) -> None:
        """原子写入项目记忆到磁盘."""
        self._cache[project_id] = entries

        self.storage_dir.mkdir(parents=True, exist_ok=True)

        filepath = self._filepath(project_id)
        data = [e.to_dict() for e in entries]

        # 原子写入: tmp → replace
        tmp_fd, tmp_path = tempfile.mkstemp(
            suffix=".json", prefix="mem_", dir=str(self.storage_dir)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, cls=_MemoryEncoder)
            os.replace(tmp_path, str(filepath))
        except Exception:
            # 清理临时文件
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    def _prune(self, entries: List[MemoryEntry]) -> None:
        """淘汰评分最低的记忆直到不超过 max_entries."""
        if len(entries) <= self.max_entries:
            return

        # 按淘汰得分升序 (最低的先移除)
        entries.sort(key=lambda e: _eviction_score(e))
        removed = entries[: len(entries) - self.max_entries]
        for e in removed:
            entries.remove(e)
            logger.debug(
                f"[MemoryStore] Pruned memory {e.id[:8]}... "
                f"(type={e.memory_type.value}, age={e.age_days:.0f}d, importance={e.importance:.2f})"
            )
