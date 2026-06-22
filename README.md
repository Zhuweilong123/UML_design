# UML Designer - 智能UML类图设计工具

基于 LLM 的智能化 UML 类图设计与代码生成自动化工具。支持从 UML 设计到代码生成、测试构建、代码优化的全流程自动化。

## 功能特性

### 核心编辑
- **UML类图编辑**: 添加/删除/移动类，支持全量类关系（继承/组合/聚合/关联/实现/依赖）
- **属性编辑**: 类名、构造型（interface/abstract/enum）、属性、方法、备注
- **连接属性**: 多重性、角色名、连接备注
- **撤销/重做**: 50步历史，0.5秒内同类操作自动合并
- **画布操作**: Ctrl+滚轮缩放，空格/中键平移，网格吸附与自定义

### 文件操作
- 新建/打开/保存（.uml JSON 格式）
- 导出 Markdown 设计文档
- Excel 用例库上传解析
- 目录浏览（支持本地文件系统任意路径）

### LLM 集成
- **代码生成**: 调用 DeepSeek 生成 12 种主流编程语言代码
- **UML优化**: LLM 分析优化类图设计，生成 diff 对比
- **已有代码适配**: 加载已有源码目录，LLM 根据 UML 设计适配/优化现有代码（迭代开发模式）
- **增量测试更新**: 加载已有测试目录，LLM 根据用例检视变更增量修改测试

### 自动化流水线（7 阶段）

| 阶段 | 说明 |
|------|------|
| 1. UML优化 | LLM 根据用户需求优化 UML 设计 |
| 2. 开发确认 | 人工审查优化结果，接受/拒绝 |
| 3. 代码生成 | 从 UML 生成代码，或适配已有代码到 UML |
| 4. 用例检视 | 加载 Excel 用例库，标记变更用例 |
| 5. 测试生成 | 增量生成/更新测试代码 |
| 6. 用例调试 | 真实 pytest 执行，修复编译错误（不改测试逻辑） |
| 7. 代码优化 | 基于测试失败反馈优化源码（最多 3 轮，回溯保护） |

### 已有项目支持
- 启动流水线时可选已有源码目录和测试代码目录
- 源码目录有文件 → 根据 UML **适配**已有代码（保留业务逻辑）
- 测试目录有文件 → 根据用例变更**增量更新**已有测试
- 目录留空 → 从 UML/用例全新生成（新项目模式）
- 目录选择自动持久化到浏览器（localStorage）

### 安全
- **内部 API 鉴权**: Bearer Token 可配置，本地开发自动跳过
- **路径安全校验**: 文件操作端点防止目录遍历攻击
- **API Key 保护**: 密钥仅从环境变量读取，不硬编码

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 18 + TypeScript |
| 图形引擎 | AntV X6 |
| 状态管理 | Zustand |
| UI组件库 | Ant Design 5 |
| 代码编辑器 | Monaco Editor |
| 后端框架 | FastAPI (Python) |
| LLM | DeepSeek API (兼容 OpenAI SDK) |
| 测试框架 | pytest (真实子进程执行) |
| 构建工具 | Vite |

## 项目结构

```
uml_designer/
├── frontend/                     # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── Canvas/           # UML 画布编辑器 (AntV X6)
│   │   │   ├── PropertyPanel/    # 属性编辑面板
│   │   │   ├── Toolbar/          # 工具栏
│   │   │   ├── CodeViewer/       # 代码查看器 (Monaco)
│   │   │   ├── TestCodeViewer/   # 测试代码查看器
│   │   │   ├── TestCaseViewer/   # 用例检视表格
│   │   │   ├── PipelineConsole/  # 流水线控制台
│   │   │   └── DiffViewer/       # Diff 对比视图
│   │   ├── stores/               # Zustand 状态管理
│   │   ├── services/             # API 服务层
│   │   ├── types/                # TypeScript 类型
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                      # FastAPI 后端
│   ├── app/
│   │   ├── api/                  # REST + WebSocket 路由
│   │   │   ├── files.py          # 文件操作、目录浏览
│   │   │   ├── llm.py            # LLM 调用接口
│   │   │   ├── pipeline.py       # 流水线管理
│   │   │   └── testhub.py        # 用例库管理
│   │   ├── core/
│   │   │   ├── config.py         # 应用配置
│   │   │   ├── auth.py           # API 鉴权
│   │   │   └── security.py       # 路径安全
│   │   ├── models/               # Pydantic 数据模型
│   │   │   ├── uml.py            # UML 类图模型
│   │   │   └── pipeline.py       # 流水线状态模型
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── code_generator.py # 代码生成/适配
│   │   │   ├── llm_service.py    # LLM 调用封装
│   │   │   ├── pipeline_service.py # 流水线编排
│   │   │   ├── file_service.py   # 文件读写
│   │   │   └── tools.py          # JSON 解析工具
│   │   └── main.py
│   ├── requirements.txt
│   └── .env
├── generated/                    # 生成代码输出
│   ├── src/                      # 源代码
│   └── test/                     # 测试代码
├── pipeline_log/                 # 流水线运行报告
├── testHub/                      # Excel 用例库
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

### 3. 启动后端服务

```bash
cd backend
python -m app.main
```

后端运行在 http://localhost:8000，API 文档在 http://localhost:8000/api/docs

### 4. 安装前端依赖

```bash
cd frontend
npm install
```

### 5. 启动前端开发服务器

```bash
cd frontend
npm run dev
```

前端运行在 http://localhost:3000

### 生产部署鉴权

在后端 `.env` 设置 Token，前端 `.env.local` 设置相同值：

```env
# backend/.env
INTERNAL_API_TOKEN=你的随机密钥

# frontend/.env.local
VITE_API_TOKEN=你的随机密钥
```

生成随机密钥：`python -c "import secrets; print(secrets.token_urlsafe(32))"`

## 使用指南

### 基础操作

1. **添加类**: 双击画布空白区域
2. **创建连接**: 从类节点端口拖拽到目标节点
3. **编辑属性**: 单击类或连接，在右侧面板编辑
4. **生成代码**: 选择语言，点击工具栏"生成代码"按钮
5. **UML优化**: 点击"优化设计"，LLM 分析并生成优化建议

### 流水线使用

1. 点击工具栏"流水线"按钮，打开流水线面板
2. **（可选）选择已有项目目录**:
   - 源码目录：已有代码的路径，LLM 会根据 UML 适配
   - 测试目录：已有测试的路径，LLM 会增量更新
   - 留空则从 UML/用例全新生成
3. 点击"启动流水线"
4. 按提示输入优化需求（可跳过）
5. 在 diff 面板审查 UML 优化结果，选择接受或拒绝
6. Stage 4 时在主画布检视测试用例，确认后继续
7. 流水线自动执行测试 → 优化代码 → 生成报告

### 已有项目迭代流程

```
第 N 次运行:
  源码目录: generated/src/    → Stage 3 适配已有代码到 UML
  测试目录: generated/test/   → Stage 5 增量更新已有测试
  → Stage 6 真实 pytest 执行
  → Stage 7 修复失败用例（改源码不改测试）
  → 通过率从 80% → 93% → 98% ...
```

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+Z | 撤销 |
| Ctrl+Y / Ctrl+Shift+Z | 重做 |
| Delete | 删除选中元素 |
| Ctrl+滚轮 | 缩放画布 |
| 空格+拖拽 | 平移画布 |

## 支持的编程语言

Python, Java, TypeScript, JavaScript, C#, C++, Go, Rust, Ruby, Swift, Kotlin, PHP
