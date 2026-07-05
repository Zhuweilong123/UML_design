# Memory System — LLM 跨会话记忆

基于 **BM25 稀疏向量检索** 的独立记忆系统，为 UML Designer 提供 LLM 跨会话上下文感知能力。

## 核心特性

- **零外部依赖** — 纯 Python 标准库实现，无需向量数据库或 embedding API
- **BM25 检索** — 标准 Okapi BM25 算法，中英文混合分词
- **自动记忆提取** — LLM 交互后自动提取关键 insights 并持久化
- **容量管理** — 按 importance × 时间衰减自动淘汰低价值记忆
- **原子写入** — 防止断电造成数据损坏
- **异步 API** — 兼容 FastAPI，开箱即用

## 目录结构

```
memory_system/
├── __init__.py    # 公开 API (MemoryManager, MemoryEntry, ...)
├── models.py      # 数据模型 (MemoryEntry, RecallResult, MemoryType)
├── tokenizer.py   # 中英混合分词 (中文 bigram + 英文 split)
├── bm25.py        # BM25 索引 (倒排索引 + IDF + TF 归一化)
├── store.py       # 持久化存储 (JSON + 原子写 + 容量淘汰)
├── manager.py     # MemoryManager 顶层接口
├── demo.py        # 独立演示脚本
└── README.md      # 本文档
```

## 快速开始

### 运行演示

```bash
cd memory_system
python demo.py
```

演示会模拟 3 轮 LLM 交互 → 记忆提取 → 检索 → 注入的完整流程。

### 基础用法

```python
from memory_system import MemoryManager

# 初始化
manager = MemoryManager(storage_dir="./memories")

# ── 1. LLM 调用后: 提取并存储记忆 ──
entries = await manager.remember(
    project_id="blog_system",
    context="用户请求优化类图，提高可扩展性",
    llm_call_type="optimize",
    user_input="请优化 Blog 系统的类图设计",
    llm_output="...",       # LLM 返回内容
    user_feedback="accepted",
    extract_fn=my_llm_chat, # 你的 LLM 调用函数
)

# ── 2. LLM 调用前: 检索相关记忆 ──
results = await manager.recall(
    project_id="blog_system",
    query="如何优化时序图中的认证流程",
    top_k=5,
    max_tokens=800,
)

# ── 3. 注入到 system prompt ──
enriched_prompt = manager.inject_memories(
    system_prompt="你是 UML 设计专家...",
    recall_results=results,
)

# 使用 enriched_prompt 发起 LLM 调用
response = await chat(system_prompt=enriched_prompt, ...)
```

## 集成到 UML Designer

### Step 1: 初始化 (backend/app/main.py 或 startup 事件)

```python
from memory_system import MemoryManager
from app.services.llm_service import chat

manager = MemoryManager(storage_dir="./project_memories", max_entries=50)

async def extract_fn(prompt: str) -> str:
    return await chat(prompt, temperature=0.3, max_tokens=500)
```

### Step 2: LLM 调用后记录

在 `code_generator.py` / `pipeline_service.py` 等调用 LLM 的地方:

```python
await manager.remember(
    project_id=diagram.name,
    context=f"用户请求{'优化' if is_optimize else '生成代码'}",
    llm_call_type="optimize" if is_optimize else "generate",
    user_input=user_prompt,
    llm_output=llm_response,
    user_feedback=user_feedback,
    extract_fn=extract_fn,
)
```

### Step 3: LLM 调用前检索并注入

```python
results = await manager.recall(
    project_id=diagram.name,
    query=user_instructions,
    top_k=5,
)
enriched_system = manager.inject_memories(
    build_system_prompt(diagram),
    results,
)
response = await chat(prompt=user_prompt, system_prompt=enriched_system)
```

## API 参考

### MemoryManager

| 方法 | 说明 |
|------|------|
| `remember()` | LLM 调用后提取并存储记忆 |
| `recall()` | 根据查询检索相关记忆 |
| `inject_memories()` | 将记忆注入 system prompt |
| `forget()` | 删除指定记忆 |
| `list_memories()` | 列出项目所有记忆 |
| `stats()` | 获取记忆统计信息 |

### 记忆类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `preference` | 用户偏好 | "用户喜欢组合优于继承" |
| `decision` | 设计决策 | "BlogService 使用策略模式" |
| `rejection` | 被拒绝的方案 | "不要用 Session 认证" |
| `convention` | 代码规范 | "项目统一使用 MVC 分层" |
| `insight` | 通用洞察 | "领域模型倾向贫血模型" |

### BM25 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `k1` | 1.5 | 词频饱和度 (1.2~2.0) |
| `b` | 0.75 | 文档长度归一化 (0.5~1.0) |

## 设计决策

1. **为什么不用向量数据库?** — 这是桌面工具的配套模块，需要零配置、零依赖。BM25 对中文关键词匹配足够好，且无需额外 embedding API 调用成本。

2. **为什么用 bigram 而不是分词库?** — bigram 是语言无关的，对代码片段、中英混合、专有名词都有较好效果，且零依赖。

3. **为什么记忆提取需要外部 LLM?** — 记忆系统本身不依赖特定 LLM，通过 `extract_fn` 回调解耦。集成时传入 `chat()` 即可，也可用更便宜的模型做提取。

4. **Token 预算如何控制?** — `recall()` 的 `max_tokens` 参数控制注入的字符量 (1 token ≈ 2 chars)，默认 800 tokens。
