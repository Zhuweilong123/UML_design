# 多图综合 Pipeline 设计方案

> 讨论时间: 2026-06-23
> 状态: 设计阶段（未实现）

## 背景

当前 UML Designer 仅支持类图（Class Diagram）的设计与代码生成。实际开发中还有时序图（Sequence Diagram）、组件图（Component Diagram）等需求。本文档讨论将 Pipeline 从单图驱动升级为多图综合驱动的设计方案。

## 核心思路

多张图不是"各跑各的"，而是**不同视角描述同一个系统**。类图给结构骨架、时序图给行为逻辑、组件图给模块架构。Pipeline 需要打通这些图，综合生成更完整的代码和测试。

## 数据模型

### Project 容器（替代单 Diagram）

```json
{
  "name": "MyProject",
  "version": "1.0",
  "diagrams": [
    { "type": "class",     "data": { "classes": [...], "relations": [...] } },
    { "type": "sequence",  "data": { "lifelines": [...], "messages": [...] } },
    { "type": "component", "data": { "components": [...], "interfaces": [...], "links": [...] } }
  ]
}
```

### 图之间的引用

时序图的生命线通过 ID 引用类图中的类：

```json
{
  "lifelines": [
    { "id": "L1", "class_ref": "class_ota_id" },
    { "id": "L2", "class_ref": "class_crow_id" }
  ],
  "messages": [
    { "from": "L1", "to": "L2", "method": "clear_scheduled_crow", "order": 1 }
  ]
}
```

组件图同理引用类图中的类来定义组件的内部结构。

## 逐阶段设计

### Stage 1 — UML 优化（交叉验证）

当前只优化类图。多图模式下，LLM 同时看到多张图，进行交叉一致性校验：

- **验证示例**：类图 OtaTask 有 `execute()` 方法 → 时序图引用 `OtaTask.execute()` → 组件图中 OtaTask 在 task_module → 三者一致 ✅
- **冲突示例**：类图 SentinelTask 无 `is_running` 属性 → 时序图 `SentinelTask.execute()` 后检查 `self.is_running` → LLM 标记矛盾，修正被错误的图

LLM 输出格式：
```json
{
  "consistency_report": [
    { "severity": "error", "msg": "时序图引用类图不存在的属性", "fix": "..." }
  ],
  "diagrams": { "class": {...}, "sequence": {...} }
}
```

### Stage 3 — 代码生成（综合）

| 图类型 | 贡献 | 示例 |
|--------|------|------|
| 类图 | 类定义骨架（属性+方法签名） | `class OtaTask: def execute(self): pass` |
| 时序图 | 方法体实现（调用链逻辑） | `execute()` 内部: `check_random() → clear_scheduled_crow() → perform_upgrade()` |
| 组件图 | 模块结构（import + 包组织） | `from task_module import CrowTask, BaseTask` |

生成代码时，时序图的方法调用链填充方法体、组件图决定文件组织。每张图生成结构化 Summary 传给 LLM，不传完整 JSON（节省 token）：

```
## 时序图摘要
OtaTask.execute() 调用链: check_random() → clear_scheduled_crow() → perform_upgrade()
CrowTask 被 OtaTask / SentinelTask 调用

## 组件图摘要
OtaTask, CrowTask, BaseTask ∈ task_module
MM_APP → 依赖 task_module
```

### Stage 5 — 测试生成（分层）

| 测试层 | 来源 | 内容 |
|--------|------|------|
| 单元测试 | 类图 | 每个类的每个方法独立测试 |
| 集成测试 | 时序图 | 端到端流程验证（跨类调用链） |
| 架构测试 | 组件图 | 模块依赖正确性、接口契约 |

### Stage 6 — 测试执行（分层）

```
Layer 1: 单元测试  → 先跑（底层，失败率低）
Layer 2: 集成测试  → 通过了再跑（依赖底层正确）
Layer 3: 架构测试  → 最后跑
```

底层挂了不浪费时间跑上层，问题定位更精确。

### Stage 7 — 代码优化（回溯）

失败后 LLM 回溯对应图定位根因：

- 失败：`test_ota_crow_interaction → FAIL`
- 回溯时序图第 3 步：`OtaTask → CrowTask: clear_scheduled_crow()`
- 回溯类图：`CrowTask` 没有 `clear_scheduled_crow()` 方法
- → LLM 知根因在类图缺方法 → 精确修复

另一个路径：
- 类图和时序图都正确 → LLM 推断可能是测试逻辑问题 → 标记用户审查

## 数据流

```
Project
├── class_diagram      ──→ 结构骨架 ──→ 单元测试
├── sequence_diagram   ──→ 方法实现 ──→ 集成测试
└── component_diagram  ──→ 模块架构 ──→ 架构测试
        │                        │
        └────────────────────────┴──→ LLM 交叉验证 + 综合代码生成
```

## 关键设计决策

| 决策 | 方案 |
|------|------|
| 图之间引用 | 通过 ID 引用（timeline.class_ref → class.id） |
| 图可缺失 | 是，只有类图时等于当前单图模式，渐进增强 |
| Prompt 长度控制 | 每张图生成 JSON Summary 而非传全文 |
| 文件格式 | `.uml` → `.umlproj`，向下兼容 |
| 项目结构 | 一个 project 包含多图，而非多个独立文件 |

## 演进路径

```
test11:
Phase 1: 重构数据模型 Project + 多图容器（不影响现有功能）
Phase 2: 增加时序图编辑器 + X6 渲染
Phase 3: 时序图 → 代码生成（方法调用链）
Phase 4: 增加组件图编辑器 + X6 渲染
Phase 5: 多图综合 Pipeline（交叉验证 + 分层测试 + 综合优化）
```
