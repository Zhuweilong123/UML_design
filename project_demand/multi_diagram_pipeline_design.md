# 多图综合 Pipeline 设计方案

> 设计时间: 2026-06-23
> 实施完成: 2026-06-25
> 状态: ✅ 已实现

## 背景

将 UML Designer 从单图（类图）驱动升级为多图（类图 + 时序图 + 组件图）综合驱动。多张图代表系统的不同视角，Pipeline 打通它们，生成更完整的代码和测试。

## 核心思路

多张图不是"各跑各的"，而是**不同视角描述同一个系统**。类图给结构骨架、时序图给行为逻辑、组件图给模块架构。

## 数据模型 — 已实现

### Project 容器

```json
{
  "name": "MyProject",
  "version": "1.0",
  "diagrams": [
    { "diagram_type": "class",     "classes": [...], "relations": [...] },
    { "diagram_type": "sequence",  "lifelines": [...], "messages": [...] },
    { "diagram_type": "component", "components": [...], "comp_relations": [...] }
  ],
  "active_diagram_index": 0
}
```

- 文件格式: `.umlproj`（向下兼容 `.uml`）
- 标签页切换三种图类型
- `SeqLifeline.class_ref` 可引用类图中的类 ID

## 逐阶段实现

### Stage 1 — UML 优化（单图）✅

当前优化针对活跃图类型，`optimize_uml` 根据 `diagram_type` 自动切换 prompt 和校验规则：
- `class` → 类图规则（visibility/stereotype/relation type）
- `sequence` → 时序图规则（lifeline/message/order/note）
- `component` → 组件图规则（component/interface/dependency）

交叉验证（多图一致性校验）——设计文档中规划，尚未实现。

### Stage 3 — 代码生成（综合）✅

Pipeline 启动时自动从 Project 提取类图 + 时序图 + 组件图，调用 `generate_integrated_code()`：

| 图类型 | 贡献 | 实现 |
|--------|------|------|
| 类图 | 类定义骨架（属性+方法签名） | 必选，没有类图无法启动 |
| 时序图 | 方法体实现（消息→调用链） | 可选，存在时方法体不再空 `pass` |
| 组件图 | 模块结构（import + 依赖关系） | 可选，提供组件名和接口信息 |

Prompt 结构：
```
## Class Diagram (structure)
{classes JSON}

## Sequence Diagram (method call chains)
OtaTask → CrowTask: clear_scheduled_crow() [sync]  ── 业务备注

## Component Diagram (module architecture)
AuthService provides: [IAuth] requires: [ILogger]
```

- Prompt 完整保存在 `pipeline_log/llm_prompt_{ts}.md`
- 要求"每个类单独一个文件"，不合并

### Stage 5 — 测试生成 ✅

当前仍为单图测试生成（类图→单元测试），时序图→集成测试 和 组件图→架构测试 待实现。

### Stage 6 — 测试执行 ✅

真实 pytest 执行（`asyncio.to_thread` + `subprocess.run`），编译错误自动修复（只修 import/syntax，不改逻辑）。

### Stage 7 — 代码优化 ✅

- 源码级优化（只改源码不改测试）
- 轮间记忆传递（上轮修复了什么、仍失败什么）
- 僵化检测（同样失败 2 轮 → 提前退出提示人工审查）
- 回溯定位（失败→对应图）——设计中，待实现

## 数据流

```
Project
├── class_diagram      ──→ 类骨架 ──→ 单元测试
├── sequence_diagram   ──→ 方法体 ──→ 集成测试（待实现）
└── component_diagram  ──→ 模块结构 ──→ 架构测试（待实现）
        │                     │
        └─────────────────────┴──→ generate_integrated_code()
```

## 关键设计决策

| 决策 | 状态 |
|------|------|
| 图之间引用 | `SeqLifeline.class_ref` → `UmlClass.id` ✅ |
| 图可缺失 | 类图必选，时序图/组件图可选渐进增强 ✅ |
| Prompt 长度控制 | 传结构化摘要（消息列表、组件列表），非完整 JSON ✅ |
| 文件格式 | `.umlproj` 向下兼容 `.uml` ✅ |
| 项目结构 | Project 包含多图，标签页切换 ✅ |
| Prompt 日志 | 完整 prompt 保存到 `pipeline_log/` ✅ |

## 演进路径

```
✅ Phase 1: 重构数据模型 Project + 多图容器
✅ Phase 2: 增加时序图编辑器 + X6 渲染
✅ Phase 3: 时序图 → 代码生成（方法调用链）
✅ Phase 4: 增加组件图编辑器 + X6 渲染
✅ Phase 5: 多图综合 Pipeline（综合代码生成 + 轮间记忆 + 僵化退出）
📋 待实现: 交叉一致性验证 / 分层测试 / 集成测试生成 / 回溯定位
```
