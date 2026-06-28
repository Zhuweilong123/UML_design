---
name: global-optimize-stream-design
description: 全局优化动态绘图 — 从CSV到JSON元素提取的架构演进、关键设计决策与实现细节
metadata:
  type: reference
---

# 全局优化动态绘图：架构设计与演进

## 概述

"全局优化"功能将类图、时序图、组件图同时发送给 LLM 交叉验证优化。支持两种模式：
- **完整模式**：LLM 返回完整 JSON → 一次性替换所有图
- **流式模式（动态绘图）**：LLM 流式输出 → 逐元素渲染到画布

## 架构演进（三阶段）

### 阶段 1：CSV 逐行模式（问题：输出质量差）

```
LLM → CSV 逐行 → SSE → 前端逐 addClass/addLifeline...
格式: class:id,name,x,y,stereotype
      attr:class_id,name,type,visibility
      message:id,from,to,label,type,order
```

- 优点：天然可增量解析，换行即边界
- 问题：同样需求，完整模式输出 5类+12属性+8方法，流式只有 3类+0属性+0方法
- 根因：CSV 格式约束太强，LLM 倾向最小化输出

### 阶段 2：JSON 流式 + 一次性解析（问题：无动态效果）

```
LLM → JSON 分块 → SSE → 前端累积 → DONE → JSON.parse → setProject
```

- 优点：输出质量与完整模式一致
- 问题：JSON 天然不可增量解析，必须等 `}` 闭合才能 parse，无动态绘图

### 阶段 3：JSON + Brace深度提取（当前方案 ✅）

```
LLM → JSON token流 → _JsonElementExtractor (brace追踪)
    → 深度4→3时提取完整元素 → json.loads() → 分类
    → yield "class:{json}" / "lifeline:{json}" / ...
    → SSE多行格式 → 前端逐元素 parse → addClass/updateClass → 实时渲染
```

- 优点：JSON 的丰富性 + CSV 的增量渲染能力，两者兼得

## 关键设计：Brace深度提取

### JSON 元素深度分析

```
{                                    ← depth 0
  "optimized": {                     ← depth 1
    "class": {                       ← depth 2
      "classes": [                   ← depth 2 (bracket不算)
        {                            ← depth 3→4  ★ 元素开始
          "id": "...",
          "attributes": [            ← depth 4
            {                        ← depth 4→5  (attr，需忽略)
              "name": "..."
            }                        ← 5→4
          ],
        },                           ← 4→3  ★ 元素结束
      ]
    }
  }
}
```

### 提取规则

- 只追踪 `{` `}` 深度（忽略 `[` `]`、字符串内字符）
- 深度 3→4 时记录元素起始位置
- 深度 4→3 时提取完整 `{...}` 文本
- 通过 json.loads + 键名判断类型

### 元素分类逻辑（`_classify`）

| 特征键 | 类型 |
|--------|------|
| `stereotype` | class |
| `from_lifeline` | message |
| `y_start` / `y_end` | fragment |
| `class_ref` + `activations` | lifeline |
| `source` + `target` + `multiplicity_source` | relation |
| `source` + `target` (无 multiplicity) | comp_rel |
| `provided_interfaces` / `parent_id` | component |

## 关键设计：SSE 多行格式

### 问题

提取的 JSON 含 `\n`，单行 `data: {json}\n\n` 会破坏 SSE

### 方案

```python
# API 端点 (llm.py)
for pline in payload.split("\n"):
    yield f"data: {pline}\n"
yield "\n"  # SSE 消息分隔符
```

标准 SSE 多行：每条消息的每一行前缀 `data: `，空行结尾

## 关键设计：前端跨 chunk buffer

### 问题

HTTP chunk 边界可能在任何位置切断 `data:` 行，`text.split('\n')` 只处理当前 chunk

### 方案

```typescript
let textBuffer = '';   // 跨 chunk 积累
let currentData = '';  // 跨 chunk 积累 SSE 消息

while (read chunk) {
    textBuffer += decode(chunk);
    while (true) {
        const nl = textBuffer.indexOf('\n');
        if (nl < 0) break;  // 行不完整，等下一个 chunk
        const line = textBuffer.slice(0, nl);
        textBuffer = textBuffer.slice(nl + 1);
        // 处理完整行...
    }
}
```

## 涉及文件

| 文件 | 角色 |
|------|------|
| `backend/app/services/code_generator.py` | `_JsonElementExtractor` 类 + `optimize_project_stream()` |
| `backend/app/api/llm.py` | SSE 多行格式化 |
| `frontend/src/components/Toolbar/Toolbar.tsx` | `handleStreamResponse()` — 跨 chunk buffer + 逐元素渲染 |
| `frontend/src/stores/diagramStore.ts` | `clampCoord()` 坐标校验 + `recenterCounter` 自动居中 |
| `frontend/src/components/Canvas/SeqEditor.tsx` | `centerContent()` + fragment 最小 y_start |
| `frontend/src/types/sequence.ts` | 消息 Y 位置统一为 `150 + order * 40` |

## 配套修复（元素显示不全）

| 修复 | 位置 | 说明 |
|------|------|------|
| SeqEditor 缺失 centerContent | SeqEditor.tsx:324 | 与其他编辑器对齐 |
| 坐标校验 | diagramStore.ts:addClass/addLifeline/addComponent | clampCoord(50~3000)，确定性网格后备 |
| LLM prompt 坐标保留规则 | code_generator.py:780+ | PRESERVE position/size/x/y 规则 |
| 消息 label/type/order 丢失 | Toolbar.tsx:handleStreamResponse | addMessage 后调用 updateMessage |
| comp_rel 完全丢失 | Toolbar.tsx:handleStreamResponse | 新增 comp_rel 分支 |
| 消息 Y 不一致 | sequence.ts:81 | 统一为 150+order*40 |
| Fragment 被工具栏遮挡 | SeqEditor.tsx:521 | 最小 y_start=80 |
| 流式日志不完整 | code_generator.py:632 | System Prompt + 完整 User Prompt |
