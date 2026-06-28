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

## 代码优化（5项）

| 优化 | 效果 |
|------|------|
| 提取 `_build_global_prompt()` | `optimize_project` 和 `optimize_project_stream` 共享 prompt 构建，消除 ~80 行重复。同时修复流式 prompt `{{{{` 双花括号 bug |
| 前端 dispatch table | `handleStreamResponse` 8 分支 if-else → `Record<type, handler>` + `lastOf<T>` 辅助函数 |
| 移除 `_section` 死代码 | section 追踪原本未使用，优化后 `_classify` 用 `self._section` 区分 relation/comp_rel |
| 移除 `flush()` | 所有元素已由 `feed()` 提取，`flush()` 永不执行 |
| Buffer 保留窗口 | `trim` 从 `self._buf[self._pos:]` 改为保留 512 字符窗口，防止字符串跨 chunk 时开头 `"` 丢失 |

## 关键 Bug 修复

| Bug | 根因 | 修复 |
|-----|------|------|
| `comp_rel` 误分类为 `relation` | buffer trim 截断字符串开头 `"`，`_update_section` 向后扫描找到错误的 key，`_section` 永远停在 `"class"` | trim 保留 512 字符窗口，确保跨 chunk 字符串的起始 `"` 仍在 buffer 中 |
| `__didFirstSync` 被 StrictMode 浪费 | 第一次 mount 的 sync 把 ref 设为 true，remount 后 graph B 的 sync 看到 ref 已为 true 跳过居中 | cleanup 中 `_didFirstSync.current = false` 重置 |
| `_didFirstSync` 在 Nodes=0 时触发 | `switchTo` 触发编辑器挂载时 `addClass` 尚未执行，sync 时 graph 为空 | 增加 `graph.getNodes().length > 0` 条件 |
| `setTimeout` 闭包捕获已销毁 graph | React StrictMode mount-unmount-remount，timer 触发时闭包中 graph 已 dispose | 改用 `graphRef.current` 实时获取当前 graph |
| SSE 多行 JSON 被 chunk 截断 | HTTP chunk 边界切断 `data:` 行，`currentData` 在 for 循环内每次重置 | `textBuffer` + `currentData` 移到 while 外层持久化 |

## 视图居中方案

### 两次居中策略

| 时机 | 触发 | 条件 |
|------|------|------|
| 首帧（流式中途） | sync 后 `_didFirstSync` | `graph.getNodes().length > 0` |
| 完成（流式结束） | DONE → `triggerRecenter()` → `recenterCounter` watcher | counter > 0 |
| 加载项目 | `setProject()` 自动递增 `recenterCounter` | — |

### 侧边栏感知

```
centerContent() → 在完整容器中居中
if (内容宽度 < 可见区宽度 - 40px):
    translate(tx - sidebarW/2) → 左移半个边栏 → 在可见区域居中
else:
    不左移 → 内容已撑满，防止左边溢出
```

`可见区宽度 = graph.options.width - useUiStore.getState().rightPanelWidth`

### 关键技术点

- 所有 `setTimeout` 回调必须用 `graphRef.current` 而非闭包变量（React StrictMode 兼容）
- `centerContent` 的 padding 参数不可靠，改为手动 `translate(tx - sidebarW/2)`
- 内容宽度接近可见区时跳过左移，避免负 tx 导致右侧留白

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

## 涉及文件

| 文件 | 角色 |
|------|------|
| `backend/app/services/code_generator.py` | `_build_global_prompt()` 共享构建器 + `_JsonElementExtractor` brace深度提取器 + `optimize_project_stream()` |
| `backend/app/api/llm.py` | SSE 多行格式化（`payload.split("\n")` 每行前缀 `data: `） |
| `frontend/src/components/Toolbar/Toolbar.tsx` | `handleStreamResponse()` — 跨 chunk buffer + dispatch table 逐元素渲染 |
| `frontend/src/stores/diagramStore.ts` | `clampCoord()` 坐标校验 + `recenterCounter` + `triggerRecenter()` + `setProject` 自动居中 |
| `frontend/src/components/Canvas/SeqEditor.tsx` | 两次居中 + 侧边栏感知 + fragment 最小 y_start |
| `frontend/src/components/Canvas/UMLEditor.tsx` | 同上 |
| `frontend/src/components/Canvas/CompEditor.tsx` | 同上 |
| `frontend/src/types/sequence.ts` | 消息 Y 统一为 150+order*40 |
