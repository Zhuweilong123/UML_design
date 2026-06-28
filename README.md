# UML Designer - 智能 UML 设计工具

基于 LLM 的可视化 UML 建模与代码自动化工具。支持类图、时序图、组件图，从设计到代码生成、测试构建、代码优化的全流程闭环。

<video src="UML Designer - 智能 UML 设计工具-演示.mp4" controls width="100%"></video>

## 功能特性

### 多图类型编辑器

| 图类型 | 核心元素 | 交互方式 |
|--------|---------|---------|
| **类图** | 类节点 + 关系连线（6 种） | 双击添加类 / 拖拽端口创建关系 |
| **时序图** | 生命线 + 消息箭头（5 种） | 双击添加生命线 / 点击 A→B 创建消息 |
| **组件图** | 组件节点 + 依赖箭头 | 双击添加组件 / 双击组件内部创建子组件 |

### 核心编辑
- 撤销/重做（50 步，同类操作合并）
- Ctrl+滚轮缩放，空格/中键平移
- 网格吸附与自定义（大小/颜色/粗细）
- Ctrl+C/V 复制粘贴元素，Ctrl+S 保存工程
- 属性编辑：选中元素后在右侧面板编辑

### 项目管理
- `.umlproj` 工程文件：一个工程包含多张不同类型的设计图
- 图标签页一键切换（类图 ↔ 时序图 ↔ 组件图），数据独立互不干扰
- 向下兼容：打开旧 `.uml` 文件自动包装为工程
- 目录选择自动持久化（localStorage）

### LLM 集成
- **全局优化（多图交叉验证）**: LLM 同时分析类图+时序图+组件图，进行跨图一致性校验和协同优化。支持完整模式（一次性返回）和流式模式（动态绘图）
- **动态绘图**: 流式模式下，LLM 逐元素输出 JSON，后端通过 Brace 深度追踪实时提取并分类推送，前端逐元素渲染到画布，实现"边生成边显示"
- **单图优化**: LLM 分析并优化单个图设计（类图/时序图/组件图），生成 diff 对比
- **代码生成**: 调用 DeepSeek 生成 12 种编程语言代码（类图）
- **已有代码适配**: 加载已有源码，LLM 根据 UML 设计适配/优化
- **增量测试更新**: 加载已有测试，LLM 根据用例变更增量修改

### 自动化流水线（7 阶段）

| 阶段 | 说明 |
|------|------|
| 1. 设计优化 | LLM 根据用户需求优化设计 |
| 2. 开发确认 | 人工审查优化结果，接受/拒绝 |
| 3. 代码生成 | 从 UML 生成代码，或适配已有代码 |
| 4. 用例检视 | 加载 Excel 用例库，标记变更 |
| 5. 测试生成 | 增量生成/更新测试代码 |
| 6. 用例调试 | 真实 pytest 执行，修复编译错误 |
| 7. 代码优化 | 基于失败反馈优化源码（最多 3 轮，轮间记忆 + 僵化退出） |

### 安全
- Bearer Token API 鉴权（可配置，本地开发自动跳过）
- 路径安全校验，防目录遍历
- API Key 环境变量隔离

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 18 + TypeScript |
| 图形引擎 | AntV X6 |
| 状态管理 | Zustand |
| UI 组件库 | Ant Design 5 |
| 代码编辑器 | Monaco Editor |
| 后端框架 | FastAPI (Python) |
| LLM | DeepSeek API |
| 测试框架 | pytest (真实子进程执行) |
| 构建工具 | Vite |

## 项目结构

```
uml_designer/
├── frontend/                       # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── Canvas/
│   │   │   │   ├── UMLEditor.tsx   # 类图编辑器
│   │   │   │   ├── SeqEditor.tsx   # 时序图编辑器
│   │   │   │   └── CompEditor.tsx  # 组件图编辑器
│   │   │   ├── PropertyPanel/      # 属性编辑面板
│   │   │   ├── Toolbar/            # 工具栏
│   │   │   ├── CodeViewer/         # 代码查看器 (Monaco)
│   │   │   ├── TestCodeViewer/     # 测试代码查看器
│   │   │   ├── TestCaseViewer/     # 用例检视表格
│   │   │   ├── PipelineConsole/    # 流水线控制台
│   │   │   └── DiffViewer/         # Diff 对比视图
│   │   ├── stores/                 # Zustand 状态管理
│   │   ├── services/               # API 服务层
│   │   ├── types/                  # TypeScript 类型 (uml, sequence, component, pipeline)
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                        # FastAPI 后端
│   ├── app/
│   │   ├── api/                    # REST + WebSocket 路由
│   │   ├── core/                   # 配置 / 鉴权 / 安全
│   │   ├── models/                 # Pydantic 数据模型 (UML, Sequence, Component, Pipeline)
│   │   ├── services/               # LLM / 代码生成 / 流水线 / 文件服务
│   │   └── main.py
│   ├── requirements.txt
│   └── .env
├── generated/                      # 代码输出 (src/ + test/)
├── pipeline_log/                   # LLM 交互日志（Prompt + Response 完整记录）
├── testHub/                        # Excel 用例库
├── project_demand/                 # 设计文档
├── memory/                         # 知识归档（问题修复 + 功能迭代 + 架构设计）
└── README.md
```

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `backend/.env`：

```env
DEEPSEEK_API_KEY=你的DeepSeek密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
INTERNAL_API_TOKEN=          # 可选，设置后启用 API 鉴权
```

### 3. 启动后端

```bash
cd backend
python -m app.main          # http://localhost:8000 | API 文档: /api/docs
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

### 生产部署鉴权

```env
# backend/.env
INTERNAL_API_TOKEN=你的随机密钥

# frontend/.env.local
VITE_API_TOKEN=你的随机密钥
```

生成随机密钥：`python -c "import secrets; print(secrets.token_urlsafe(32))"`

## 使用指南

### 项目管理

1. 工具栏"+"下拉 → 添加类图/时序图/组件图
2. 图标签页切换当前编辑的图
3. Ctrl+S 保存为 `.umlproj` 工程文件
4. 工具栏"打开" → 浏览并打开已有工程

### 类图
- **添加类**: 双击画布空白区域
- **创建关系**: 从节点端口拖拽到目标节点
- **编辑属性**: 单击类或关系，右侧面板编辑

### 时序图
- **添加生命线**: 双击画布空白区域
- **创建消息**: 点击生命线 A → 再点生命线 B
- **自反消息**: 点击同一生命线两次
- **编辑消息**: 点击消息线，右侧面板修改类型和备注

### 组件图
- **添加顶层组件**: 双击画布空白区域
- **添加子组件**: 双击父组件内部
- **创建依赖**: 从节点端口拖拽到目标节点
- **调整大小**: 拖拽组件边角

### 全局优化

1. 工具栏点击"全局优化"按钮（紫色图标）
2. 输入优化需求（可选），勾选"动态绘图"启用流式实时渲染
3. 完整模式：LLM 返回后一次性更新三张图
4. 流式模式：LLM 实时逐元素输出，画布边生成边渲染

### 流水线

1. 右侧面板切换到"流水线"标签
2. 可选选择已有源码/测试目录（留空则全新生成）
3. 点击"启动流水线"，按提示操作

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Ctrl+C | 复制选中元素 |
| Ctrl+V | 粘贴 |
| Ctrl+S | 保存工程 |
| Delete | 删除选中元素 |
| Ctrl+滚轮 | 缩放画布 |
| 空格+拖拽 | 平移画布 |

## 支持的编程语言

Python, Java, TypeScript, JavaScript, C#, C++, Go, Rust, Ruby, Swift, Kotlin, PHP
