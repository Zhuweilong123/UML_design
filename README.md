# UML Designer - 智能UML类图设计工具

基于 LLM 的智能化 UML 类图设计与代码生成自动化工具。

## 功能特性

### 核心编辑
- **UML类图编辑**: 添加/删除/移动类，支持全量类关系（继承/组合/聚合/关联/实现/依赖）
- **属性编辑**: 类名、构造型（interface/abstract/enum）、属性、方法
- **连接属性**: 多重性、角色名、连接备注
- **撤销/重做**: 50步历史，0.5秒内同类操作自动合并
- **画布操作**: Ctrl+滚轮缩放，空格/中键平移，网格吸附

### LLM 集成
- **代码生成**: 调用 DeepSeek 生成 12 种主流编程语言代码
- **UML优化**: LLM 分析优化类图设计，生成 diff 对比
- **自动化流水线**: 七阶段流水线（UML优化→开发确认→代码生成→用例检视→测试生成→测试执行→代码优化）

### 文件操作
- 新建/打开/保存（.uml JSON 格式）
- 导出 Markdown 设计文档
- Excel 用例库上传解析

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端框架 | React 18 + TypeScript |
| 图形引擎 | AntV X6 |
| 状态管理 | Zustand |
| UI组件库 | Ant Design 5 |
| 代码编辑器 | Monaco Editor |
| 后端框架 | FastAPI (Python) |
| LLM | DeepSeek API |
| 构建工具 | Vite |

## 项目结构

```
uml_designer/
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── Canvas/         # UML 画布编辑器
│   │   │   ├── PropertyPanel/  # 属性编辑面板
│   │   │   ├── Toolbar/        # 工具栏
│   │   │   ├── CodeViewer/     # 代码查看器
│   │   │   ├── PipelineConsole/# 流水线控制台
│   │   │   └── DiffViewer/     # Diff 对比视图
│   │   ├── stores/             # Zustand 状态管理
│   │   ├── services/           # API 服务层
│   │   ├── types/              # TypeScript 类型
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/                # REST API 路由
│   │   ├── core/               # 配置
│   │   ├── models/             # Pydantic 数据模型
│   │   ├── services/           # 业务逻辑层
│   │   └── main.py
│   ├── requirements.txt
│   └── .env
└── README.md
```

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
cd backend
python -m app.main
```

后端运行在 http://localhost:8000，API 文档在 http://localhost:8000/api/docs

### 3. 安装前端依赖

```bash
cd frontend
npm install
```

### 4. 启动前端开发服务器

```bash
cd frontend
npm run dev
```

前端运行在 http://localhost:3000

## 使用指南

1. **添加类**: 双击画布空白区域
2. **创建连接**: 从类节点端口拖拽到目标节点
3. **编辑属性**: 单击类或连接，在右侧面板编辑
4. **生成代码**: 选择语言，点击工具栏"生成代码"按钮
5. **UML优化**: 点击"优化设计"，LLM 分析并生成优化建议
6. **启动流水线**: 点击"流水线"按钮，运行七阶段自动化流程

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

## 环境配置

后端 `.env` 文件配置：

```env
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
MAX_HISTORY_STEPS=50
OPERATION_MERGE_WINDOW_MS=500
```
