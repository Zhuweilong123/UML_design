"""
数据模型 — 使用 dataclasses (零外部依赖, 避免与项目 Pydantic 版本耦合)

序列化: MemoryEntry.to_dict() / MemoryEntry.from_dict()
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class MemoryType(str, Enum):
    """记忆分类."""
    PREFERENCE  = "preference"   # 用户偏好: "用户喜欢用组合而非继承"
    DECISION    = "decision"     # 设计决策: "UserService 使用了策略模式"
    REJECTION   = "rejection"    # 被拒绝的建议: "不要加 Observer 模式，用户上次拒绝了"
    CONVENTION  = "convention"   # 代码/设计规范: "项目统一使用 MVC 分层"
    INSIGHT     = "insight"      # LLM 总结的通用 insight: "领域模型建议贫血模型"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MemoryEntry:
    """
    一条记忆记录.

    Attributes:
        id:            唯一标识 (UUID)
        project_id:    所属项目标识
        timestamp:     创建时间
        memory_type:   记忆分类
        context:       触发上下文 (当时在做什么操作)
        content:       核心 insight 正文
        tags:          便于关键词匹配的标签
        user_feedback: 用户反馈 (accepted | rejected | modified | None)
        importance:    重要性权重 0.0~1.0 (默认 0.5)
        source:        来源标记 (llm_call_type: optimize | generate | pipeline_stage)
    """
    project_id: str
    memory_type: MemoryType
    context: str
    content: str
    id: str = field(default_factory=lambda: uuid4().hex)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    user_feedback: Optional[str] = None
    importance: float = 0.5
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 dict (用于 JSON 存储)."""
        d = asdict(self)
        d["memory_type"] = self.memory_type.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """从 dict 反序列化."""
        return cls(
            id=data.get("id", uuid4().hex),
            project_id=data["project_id"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            memory_type=MemoryType(data["memory_type"]),
            context=data.get("context", ""),
            content=data.get("content", ""),
            tags=data.get("tags", []),
            user_feedback=data.get("user_feedback"),
            importance=float(data.get("importance", 0.5)),
            source=data.get("source", ""),
        )

    @property
    def age_days(self) -> float:
        """记忆年龄 (天)."""
        try:
            ts = datetime.fromisoformat(self.timestamp)
            delta = datetime.now() - ts
            return max(delta.total_seconds() / 86400.0, 0.0)
        except (ValueError, TypeError):
            return 365.0  # 解析失败当老记忆处理

    def __repr__(self) -> str:
        return (
            f"MemoryEntry(id={self.id[:8]}..., type={self.memory_type.value}, "
            f"project={self.project_id}, importance={self.importance:.2f})"
        )


@dataclass
class RecallResult:
    """
    BM25 检索结果 —— 记忆条目 + 相关性得分.

    Attributes:
        entry: 记忆条目
        score: BM25 相关性得分
    """
    entry: MemoryEntry
    score: float

    def __repr__(self) -> str:
        return f"RecallResult(score={self.score:.4f}, entry={self.entry!r})"
