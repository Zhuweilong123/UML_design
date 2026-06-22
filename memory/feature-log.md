---
name: feature-log
description: UML Designer 项目功能迭代记录
metadata:
  type: project
---

# UML Designer 功能迭代记录

> 按实现先后顺序，记录每次功能新增和变更

---

## F01 - 项目初始化（基础架构）

- **描述**: 基于 `uml_design.md` 生成 React+FastAPI 完整项目代码
- **涉及文件**: 全部初始文件（64个）
- **技术栈**: React 18 + AntV X6 + Zustand + Ant Design / FastAPI + Pydantic + DeepSeek

---

## F02 - UML 画布基础编辑

- **描述**: 
  - 双击画布添加 UML 类
  - AntV X6 自定义节点渲染（foreignObject + HTML）
  - 4个方向端口（拖拽创建连线）
  - 撤销/重做（50步，0.5秒同类操作合并）
  - Ctrl+滚轮缩放、空格平移
- **关键文件**: `UMLEditor.tsx`, `diagramStore.ts`, `UMLEditor.css`

---

## F03 - 类属性和连接属性编辑

- **描述**: 右侧属性面板支持编辑类名、构造型、属性、方法、备注，以及连接类型、多重性、角色名
- **关键文件**: `PropertyPanel.tsx`

---

## F04 - 工具栏与文件操作

- **描述**: 
  - 新建/打开/保存 .uml JSON 文件
  - 另存为对话框（自定义文件名）
  - 打开文件支持目录浏览
  - 导出 Markdown 设计文档
- **关键文件**: `Toolbar.tsx`, `file_service.py`, `api/files.py`

---

## F05 - LLM 代码生成

- **描述**: 选择 12 种编程语言，调用 DeepSeek API 生成项目代码
- **关键文件**: `code_generator.py`, `CodeViewer.tsx`

---

## F06 - LLM UML 优化

- **描述**: 
  - 弹窗输入优化需求
  - LLM 分析并返回优化后的 UML + 变更摘要 + diff
  - 对比面板显示 unified diff
  - 画布切换按钮（原始版↔优化版）
  - 评审意见窗口
  - 接受/拒绝二次确认
  - 拒绝后可输入新需求继续优化
  - 评审记录保存到 `dev_review.txt`
- **关键文件**: `DiffViewer.tsx`, `DiffViewer.css`

---

## F07 - 网格系统

- **描述**: 
  - 网格显隐切换
  - 网格设置弹窗：大小、颜色选择器、粗细滑块
  - 所有设置实时生效，保存到 .uml 文件
- **关键文件**: `UMLEditor.tsx`（grid sync useEffect）, `diagramStore.ts`（grid setters）

---

## F08 - 自动化流水线

- **描述**: 七阶段流水线：
  1. UML优化（LLM）
  2. 开发确认（接受/拒绝）
  3. 代码生成
  4. 用例检视
  5. 测试代码增量生成
  6. 用例调试执行
  7. 代码迭代优化（最多3轮）
- **功能点**:
  - WebSocket 实时进度推送
  - 动态状态显示（⏳/✅/❌ + 实时动作描述）
  - Steps 列表 + 进度条
  - 停止按钮
  - 优化需求弹窗（提交/跳过）
  - 用例检视确认卡片
- **关键文件**: `PipelineConsole.tsx`, `pipeline_service.py`, `api/pipeline.py`

---

## F09 - 测试用例管理

- **描述**: 
  - 从 `testHub/` 加载 Excel 测试用例
  - 主画布嵌入显示（嵌入式表格）
  - 工具栏"用例"按钮切换 UML↔用例
  - Sheet 切换、双击编辑、变更追踪
  - 保存修改回 Excel
  - 全量/增量生成测试代码
  - 操作日志记录到 `test_review.txt`
- **关键文件**: `TestCaseViewer.tsx`, `api/testhub.py`, `testhub/gen_testcases.py`

---

## F10 - 代码产物分层与持久化

- **描述**: 
  - 源代码(Stage 3)和测试代码(Stage 5)分开显示
  - 自动保存到 `generated/src/{项目}/{语言}/` 和 `generated/test/{项目}/{语言}/`
  - 侧边栏代码/用例代码分两个 Tab 展示
- **关键文件**: `pipeline_service.py`(_save_generated_files), `TestCodeViewer.tsx`

---

## F11 - 右键面板拆分

- **描述**: 侧边栏 Tab 重新划分：
  | Tab | 内容 |
  |-----|------|
  | 属性 | 类和关系属性编辑 |
  | 代码 | 项目源代码（Monaco Editor） |
  | 流水线 | 流水线控制台 |
  | 对比 | UML 优化 diff |
  | 用例代码 | 测试用例代码 |
- **关键文件**: `App.tsx`, `uiStore.ts`

---

## F12 - 一键启动脚本

- **描述**: `start.bat` 双击启动前后端，自动打开两个终端窗口
- **关键文件**: `start.bat`, `backend/run.bat`

---

## F13 - GitHub 版本管理

- **描述**: 
  - `.gitignore` 配置
  - Git init + commit "uml设计工具1.0版本"
  - 推送到 GitHub 仓库
- **关键文件**: `.gitignore`

---

## F14 - 用例检视嵌入式展示

- **描述**: 
  - 用例检视从侧边栏移到主画布区域全屏展示
  - 工具栏"用例"按钮切换 UML↔用例视图
  - 流水线 Stage 4 自动切换到用例视图并暂停
  - 支持 Sheet 切换、单元格编辑、变更追踪、保存
- **关键文件**: `TestCaseViewer.tsx`, `App.tsx`, `uiStore.ts`

---

## F15 - 代码沙箱执行方案（规划）

- **描述**: 
  - Docker 隔离执行生成的代码和测试
  - 支持 5 种语言镜像（Python/Java/C++/Go/JS）
  - 安全措施：内存限制、网络隔离、只读文件系统
  - 预计工作量 2.5 天
- **状态**: 📋 规划中（D033）
- **关键文件**: `project_demand/sandbox_plan.md`

---

## F16 - ReAct 自动化代码优化引擎

- **描述**: 
  - Reasoning + Acting 循环：分析→执行→观察→修复
  - 5 个工具：语法验证、错误分析、执行模拟、diff对比、完成信号
  - 集成到流水线 Stage 6（测试修复）和 Stage 7（源码优化）
  - DeepSeek function calling 原生支持
  - 最大 5 轮推理循环
- **关键文件**: `react_engine.py`, `tools.py`, `pipeline_service.py`

---

## 功能统计

| 编号 | 功能 | 分类 |
|------|------|------|
| F01 | 项目初始化 | 架构 |
| F02 | UML 画布编辑 | 编辑器 |
| F03 | 属性面板 | 编辑器 |
| F04 | 文件操作 | 存储 |
| F05 | LLM 代码生成 | AI |
| F06 | LLM UML 优化 | AI |
| F07 | 网格系统 | 编辑器 |
| F08 | 自动化流水线 | 流水线 |
| F09 | 测试用例管理 | 测试 |
| F10 | 代码持久化 | 存储 |
| F11 | 面板拆分 | UI |
| F12 | 启动脚本 | 工具 |
| F13 | Git 管理 | 工具 |
| F14 | 用例检视嵌入式展示 | UI |
| F15 | 代码沙箱方案(规划) | 架构 |
| F16 | ReAct 代码优化引擎 | AI |
| F17 | Excel用例生成测试代码 | AI |
| F18 | JSON Mode 强制结构化输出 | AI |
| F19 | ReAct 上下文自动保存 | 日志 |
| F20 | 流水线优化逐轮详情 | 日志 |
| F21 | API 鉴权 (Bearer Token) | 安全 |
| F22 | 路径安全校验 | 安全 |
| F23 | 真实 pytest 线程执行 | 测试 |
| F24 | 已有项目目录支持（源码+测试） | 流水线 |
| F25 | 目录选择持久化 (localStorage) | 前端 |
| F26 | LLM JSON 解析增强 | LLM |
| F27 | Stage 7 测试上下文感知 | 流水线 |
| F28 | Stage 6 编译错误精确分类 | 流水线 |
| F29 | 默认路径扁平化 | 后端 |

**总计: 29 项功能迭代**

---

## F21 - API 鉴权（Bearer Token 可配置）

- **描述**:
  - 后端新增 `require_auth` 依赖，从 `Authorization: Bearer <token>` 读取令牌
  - 与 `.env` 中的 `INTERNAL_API_TOKEN` 对比，匹配放行，不匹配返回 403
  - Token 未配置时自动跳过（本地开发兼容）
  - LLM、Pipeline、TestHub、Files 写端点全部受保护
  - 前端 `VITE_API_TOKEN` 环境变量驱动 axios 全局 header + WebSocket query param
- **关键文件**: `backend/app/core/auth.py`, `backend/app/main.py`, `frontend/src/services/api.ts`

---

## F22 - 路径安全校验（防目录遍历）

- **描述**:
  - `_safe_path()` 函数：解析用户路径 → 解析符号链接 → 与项目根做 `commonpath` 前缀检查
  - `open_file`: 限制只能打开 `.uml` 文件且路径在项目内
  - `browse_directory`: 父目录导航也受限在项目内
  - `upload_excel/save_file/save_generated_code`: 文件名/项目名/语言名净化
- **关键文件**: `backend/app/api/files.py`

---

## F23 - 真实 pytest 线程执行（替代 asyncio 子进程）

- **描述**:
  - Windows 上 `asyncio.create_subprocess_exec` 抛 `NotImplementedError`
  - 改用 `asyncio.to_thread()` + 同步 `subprocess.run()` 在线程池中执行 pytest
  - 日志明确标注 `LLM SIMULATION MODE` vs `Running real pytest`
  - 同时捕获 `NotImplementedError` 作为额外回退保护
- **关键文件**: `backend/app/services/pipeline_service.py`

---

## F24 - 已有项目目录支持

- **描述**:
  - 流水线启动前可选择已有的源码目录和测试代码目录
  - 源码目录有文件 → Stage 3 调用 `adapt_code_to_uml` 根据 UML 适配已有代码
  - 源码目录空 → Stage 3 从 UML 全新生成（原行为）
  - 测试目录有文件 → Stage 5 调用 `update_tests_incremental` 根据用例检视增量更新
  - 测试目录空 → Stage 5 从用例全新生成（原行为）
  - 支持任意磁盘路径，浏览时不做项目边界限制
  - 用户目录不会被 `shutil.rmtree` 清空
- **关键文件**: `backend/app/core/security.py`, `backend/app/services/pipeline_service.py`, `backend/app/services/code_generator.py`, `backend/app/api/pipeline.py`, `backend/app/api/files.py`, `frontend/src/components/PipelineConsole/PipelineConsole.tsx`

---

## F25 - 目录选择持久化

- **描述**:
  - `pipelineSourceDir` 和 `pipelineTestDir` 通过 `localStorage` 持久化
  - 页面刷新、关闭重开后自动恢复上次选择
  - 目录选择框从"仅空状态可见"改为"非运行状态始终可见"
- **关键文件**: `frontend/src/stores/uiStore.ts`, `frontend/src/components/PipelineConsole/PipelineConsole.tsx`

---

## F26 - LLM JSON 解析增强

- **描述**:
  - `clean_llm_json_response` 三层回退提取：```` ```json ``` ```` → ```` ``` ```` → 括号配对 `{...}`
  - `generate_tests`、`adapt_code_to_uml`、`update_tests_incremental` 加 `json_mode=True`
  - `_optimize_source_from_tests` 加 `json_mode=True`
- **关键文件**: `backend/app/services/tools.py`, `backend/app/services/code_generator.py`

---

## F27 - Stage 7 测试上下文感知

- **描述**:
  - `_optimize_source_from_tests` 的 LLM prompt 现在包含完整测试代码（上限 4000 字符）
  - LLM 能从测试代码了解缺失函数的签名和语义，正确添加实现
  - 保留"只改源码不改测试"原则
- **关键文件**: `backend/app/services/pipeline_service.py`

---

## F28 - Stage 6 编译错误精确分类

- **描述**:
  - `_extract_fatal_errors` 区分模块级和对象级 `AttributeError`
  - 模块级（`module 'X' has no attribute`）→ Stage 6 修复（import 路径错误）
  - 对象级（`'Foo' object has no attribute`）→ 交给 Stage 7（源码缺方法）
  - 避免 Stage 6 误拦截并阻断流水线
- **关键文件**: `backend/app/services/pipeline_service.py`

---

## F29 - 默认路径扁平化

- **描述**:
  - `_save_generated_files` 和 `_execute_tests` 默认路径从 `generated/{src,test}/{project}/{language}/` 改为 `generated/{src,test}/`
  - 与用户选择自定义目录时的扁平结构保持一致
  - 删除了所有旧嵌套目录残留
- **关键文件**: `backend/app/services/pipeline_service.py`
