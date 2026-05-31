---
name: bugfix-uml-designer
description: 记录UML Designer项目开发中遇到的问题及解决方案
metadata: 
  node_type: memory
  type: project
  originSessionId: 0194a1c3-ffe7-43ae-ae97-6e9071116351
---

# UML Designer 项目问题与解决方案汇总

## 问题速查表

| # | 问题 | 根因 | 分类 |
|---|------|------|------|
| 1 | 页面白屏 | `react-shape` 不存在于 X6 核心包 | X6/渲染 |
| 2 | 节点只有黑框无内容 | `attrs.content.html` 设置方式错误 | X6/渲染 |
| 3 | 多个类堆叠在同一位置 | "添加类" 按钮使用固定坐标 (200,200) | 交互 |
| 4 | npm install 版本不兼容 | @antv/x6 插件版本与核心版本不匹配 | 环境 |
| 5 | TypeScript 编译错误 | X6 v2 API 差异（snapline/keyboard/bindKey等） | 环境 |
| 6 | 端口圆点不可见 | ports markup 缺少 circle 定义 | X6/渲染 |
| 7 | pip install pandas 超时 | Python 3.14 无旧版 pandas wheel | 环境 |
| 8 | LLM 优化返回 500 | LLM 输出枚举值/字段名不匹配 Pydantic 模型 | LLM/后端 |
| 9 | 500 错误难调试 | FastAPI 默认不打印完整堆栈 | 后端/调试 |
| 10 | 后端代码修改后未生效 | uvicorn reload 不可靠 | 环境 |
| 11 | 关系类型修改后画布不更新 | 边同步只处理新增，不更新已有边 | X6/同步 |
| 12 | 网格开关无效/不显示 | X6 grid API 调用格式和初始化参数不当 | X6/渲染 |
| 13 | 流水线启动 404 + 422 | pipeline 创建时序错误 + FastAPI 多参数解析失败 | 后端/API |
| 14 | WebSocket 代理 404 | Vite proxy `/api` 缺少 `ws: true` | 环境 |
| 15 | 节点位置抖动 | (补充) 避免不必要的 setPosition/setSize | X6/性能 |
| 16 | `StageName.uml_optimize` 不存在 | Python Enum 成员名需大写 | 后端 |
| 17 | Excel 中文乱码/代理对 | Python 非 UTF-8 模式运行导致 openpyxl 读写中文异常 | 环境/编码 |
| 18 | GitHub push 认证失败 | 密码认证已废弃，需用 SSH Key 或 Personal Access Token | 环境/Git |
| 19 | GitHub 网站无法访问 | 国内网络 DNS 污染/GFW 阻断，需代理或改用 Gitee | 环境/Git |
| 20 | 流水线 Stage 4 不暂停 | `resume_pipeline` 旧代码直接标记SUCCESS跳过 | 后端/流水线 |
| 21 | 进度条完成停在86% | 缺少 `pipeline_complete` 事件，WebSocket直接关闭 | 后端/流水线 |
| 22 | 测试产物不显示 | `resume_pipeline` Stage 5 保存磁盘但未 append artifacts | 后端/流水线 |
| 23 | 源代码产物翻倍 | `resume_pipeline` 被多次调用重复跑 Stage 3 | 后端/流水线 |
| 24 | 优化需求弹窗消失 | 重复的空 `else if` 吞掉了 `request_instructions` 事件 | 前端 |
| 25 | "检视完成继续"无响应 | 多条路径到达Stage 4但未注册等待逻辑 | 后端/流水线 |

---

## 问题1: 页面白屏 - AntV X6 自定义节点注册失败

**现象**: 前端 http://localhost:3000 打开后空白，没有任何内容显示。

**根因**: UMLEditor.tsx 中使用 `Node.registry.register('uml-class', { inherit: 'react-shape' })` 注册自定义节点，但 `react-shape` 是独立包 `@antv/x6-react-shape` 提供的，不在 `@antv/x6` 核心包中，导致注册失败、React 组件树崩溃。

**解决**: 
- 改用 `Graph.registerNode()` 在模块顶层注册（在创建 Graph 实例之前）
- 使用 `inherit: 'rect'` 作为基础形状
- 使用 `foreignObject` + `div` 标记渲染 HTML 内容
- 模式参考 X6 自带的 `text-block` 形状实现

**代码模式**:
```typescript
Graph.registerNode('uml-class', {
  inherit: 'rect',
  markup: [
    { tagName: 'rect', selector: 'body' },
    {
      tagName: 'foreignObject', selector: 'fo',
      children: [
        { tagName: 'div', ns: 'http://www.w3.org/1999/xhtml', selector: 'content' }
      ]
    }
  ],
  attrs: {
    body: { stroke: '#333', strokeWidth: 2, fill: '#fff', rx: 6, ry: 6, magnet: true },
    fo: { refWidth: '100%', refHeight: '100%' },
    content: { html: '' },
  },
});
```

---

## 问题2: 节点 HTML 内容不渲染（只能看到黑框）

**现象**: 类节点只有黑色矩形框，没有文字内容（类名、属性、方法等）。

**根因**: X6 v2.19.2 的 `graph.addNode()` 不支持直接传 `html` 属性（该属性在 TypeScript 类型中不存在，运行时也不生效）。需要使用 X6 的标准模式：在注册节点时定义 `foreignObject` + `div` 的 markup，然后通过 `attrs.content.html` 设置 HTML 内容。

**解决**:
- 在 `Graph.registerNode` 时正确配置 `foreignObject` 和 `div` 的 selector
- 创建节点时使用: `graph.addNode({ attrs: { content: { html: '...' } } })`
- 更新节点时使用: `node.setAttrByPath('content/html', htmlContent)`

---

## 问题3: 多个类堆叠在同一位置

**现象**: 第一个类创建正常，后续创建的类"看不到"（实际堆叠在相同坐标）。

**根因**: "添加类" 按钮的 onClick 使用固定坐标 `{ x: 200, y: 200 }`，所有新类在同一位置。

**解决**:
```typescript
onClick={() => {
  const x = 150 + Math.random() * 400;
  const y = 100 + Math.random() * 300;
  useDiagramStore.getState().addClass({ x, y });
}}
```

---

## 问题4: npm 包版本不兼容

**现象**: `npm install` 失败，报 `ETARGET` 或 `ERESOLVE` 错误。

**根因**:
- `@antv/x6-plugin-clipboard@^2.3.2` 版本不存在
- `@antv/x6-plugin-clipboard@3.0.0` 要求 `@antv/x6@^3.x`，与项目使用的 `@antv/x6@^2.18.1` 不兼容

**解决**:
- 使用 `@antv/x6-plugin-clipboard@^2.1.6`（最新 2.x 版本）
- 各插件版本锁定为实际可用的版本：
  - `@antv/x6`: ^2.18.1
  - `@antv/x6-plugin-history`: ^2.2.4
  - `@antv/x6-plugin-transform`: ^2.1.8
  - `@antv/x6-plugin-selection`: ^2.2.2
  - `@antv/x6-plugin-snapline`: ^2.1.7
  - `@antv/x6-plugin-clipboard`: ^2.1.6
  - `@antv/x6-plugin-export`: ^2.1.6
  - `@antv/x6-plugin-dnd`: ^2.1.1

---

## 问题5: TypeScript 类型错误

**现象**: 多个 TS 编译错误。

**具体错误及修复**:

| 错误 | 修复 |
|------|------|
| `snapline` does not exist in Graph options | 使用 `graph.use(new Snapline())` 插件代替，不在 Graph 构造中设置 |
| `keyboard` does not exist in Graph options | 改用 DOM `addEventListener('keydown', ...)` |
| `bindKey` does not exist on Graph | 同上，用 DOM 事件代替 |
| `GridOutlined` not exported from @ant-design/icons | 改用 `AppstoreOutlined` |
| `Export({ enabled: true })` Expected 0 arguments | 改为 `new Export()` 无参构造 |
| `drawGrid` 参数类型不匹配 | 使用 `(graph as any).drawGrid(...)` 类型断言 |

---

## 问题6: 端口圆点不可见

**现象**: 鼠标悬停在节点上时看不到连接端口。

**根因**: 
1. 未在 `Graph.registerNode` 中正确定义 ports（markup、items）
2. CSS 选择器无法匹配 X6 生成的端口 DOM 结构

**解决**:
- 在节点注册时明确定义 4 组端口（top/right/bottom/left），每组包含 `markup: [{ tagName: 'circle', selector: 'circle' }]`
- CSS 使用 `.x6-node .x6-port-body circle` 选择器控制端口显隐

**注册配置**:
```typescript
ports: {
  groups: {
    top: {
      position: { name: 'top' },
      markup: [{ tagName: 'circle', selector: 'circle' }],
      attrs: { circle: { r: 6, magnet: true, stroke: '#1890ff', strokeWidth: 2, fill: '#fff' } },
    },
    // ... right, bottom, left 类似
  },
  items: [
    { id: 'pt', group: 'top' },
    { id: 'pr', group: 'right' },
    { id: 'pb', group: 'bottom' },
    { id: 'pl', group: 'left' },
  ],
}
```

**CSS**:
```css
.x6-node .x6-port-body circle { opacity: 0; transition: opacity 0.15s; }
.x6-node:hover .x6-port-body circle { opacity: 1; }
```

---

## 问题7: 后端 Pandas 安装超时

**现象**: `pip install pandas==2.2.0` 从源码编译，过程缓慢超时。

**根因**: Python 3.14 操作系统较新，pandas 2.2.0 没有预编译的 wheel。

**解决**: 使用更宽泛的版本范围或安装有预编译 wheel 的版本。

---

---

## 问题8: LLM 优化 UML 返回 500 错误 — Pydantic 枚举校验失败

**现象**: 点击"优化设计"按钮后报错 `AxiosError: Request failed with status code 500`，后端返回 Pydantic ValidationError。

**根因**: DeepSeek LLM 返回的 JSON 数据不符合后端 Pydantic 模型的枚举约束：
1. `visibility` 字段使用 `"public"`/`"private"` 而不是 `"+"`/`"-"`
2. `stereotype` 字段为空字符串 `""`（LLM 新增类时未设置）
3. 关系 `type` 使用 `"generalization"` 而不是 `"inheritance"`
4. 关系字段名使用 `from`/`to` 而非 `source`/`target`
5. 关系缺少必填的 `id` 字段
6. 关系有多余字段如 `source_mult`、`label` 等

**解决**: 在 `code_generator.py` 中创建 `_normalize_llm_output()` 函数，在 LLM 返回结果传给 Pydantic 之前进行数据规范化：

```python
def _normalize_llm_output(data: dict) -> dict:
    """Normalize LLM output to ensure all enum values and field names match Pydantic model."""

    VIS_MAP = {"public": "+", "private": "-", "protected": "#", ...}
    VALID_STEREOTYPES = {"class", "interface", "abstract", "enum"}
    RELATION_TYPE_MAP = {"generalization": "inheritance", "extends": "inheritance", ...}

    FIELD_ALIASES = {
        "from": "source", "to": "target",
        "source_id": "source", "target_id": "target",
        "source_mult": "multiplicity_source", "target_mult": "multiplicity_target",
        "label": "role_name",
    }

    # Auto-generate missing IDs
    # Remap field aliases
    # Normalize enum values
```

**额外措施**:
- 所有 Pydantic 模型添加 `model_config = {"extra": "ignore"}` 忽略多余字段
- Prompt 中增加 CRITICAL RULES 明确要求 LLM 使用正确格式
- System prompt 强调 `Always use +, -, # for visibility values`

**Why:** LLM 输出格式不可控，需要防御性编程在数据进入 Pydantic 校验之前做容错处理。

**How to apply:** 任何调用 LLM 并解析结构化输出时，都需要类似的归一化层。

---

## 问题9: 后端端点500错误调式方法

**现象**: 前端显示通用 AxiosError 500，无法确定具体错误原因。

**根因**: FastAPI 端点异常被默认处理，只返回 `{"detail": "..."}` 简短信息。需要显式捕获并输出完整堆栈。

**解决**: 在端点上添加 `try/except` + `traceback.print_exc()`：

```python
@router.post("/optimize-uml", response_model=UmlOptimizeResponse)
async def optimize_uml_endpoint(req: UmlOptimizeRequest):
    import traceback
    try:
        ...
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")
```

调试流程：
1. 用 `curl` 发送最小 payload 直接测试后端端点
2. 用 Python 脚本模拟端点内的完整调用链路
3. 逐步增加 payload 复杂度定位问题

**Why:** 前端 axios catch 只能看到 500，后端日志才是调试关键。

---

## 问题10: 后端代码修改后未生效

**现象**: 修改了后端代码文件，但 API 行为未改变。

**根因**: `uvicorn --reload` 的热更新有时不可靠，特别是修改了导入的深层模块时可能不会触发热重载。

**解决**:
- 手动 `taskkill //F //IM python.exe` 杀死所有 Python 进程
- 重新启动 `python -m app.main`

**Why:** 热加载检测基于文件修改时间，但 Windows 上文件系统事件可能延迟。

---

---

## 问题11: 关系类型修改后画布不更新

**现象**: 在右侧属性面板修改连接的关系类型（如 association→composition），画布上的边标签和线型不变。

**根因**: UMLEditor 的 sync useEffect 中，边的同步代码 `if (existingEdgeIds.has(rel.id)) return;` 直接跳过了已存在的边，只添加新边不更新旧边。

**解决**: 将边的同步逻辑改为同时处理新增和更新：
```typescript
if (existingEdgeIds.has(rel.id)) {
  // Update existing edge: labels, dash style, arrow style
  const edge = graph.getCellById(rel.id) as Edge;
  edge.setLabels(labelText ? [labelText] : []);
  edge.setAttrByPath('line/strokeDasharray', isDashed ? '5,5' : '');
  edge.setAttrByPath('line/targetMarker/name', arrowStyle);
} else {
  // Add new edge
  graph.addEdge({...});
}
```

**Why:** 数据双向同步必须同时处理增删改，只处理增和删会导致编辑操作被静默忽略。

---

## 问题12: 网格开关无效、网格不显示

**现象**: 点击网格开关按钮后画布网格不变，有时从头到尾都看不到网格。

**根因**: 
1. Graph 初始化时 `grid` 选项缺少 `visible: true` 显式声明
2. 网格同步 useEffect 使用 `(graph as any).drawGrid()` 但参数格式在 X6 v2 中有严格要求
3. `drawGrid()` 的 `args` 参数在指定 `type: 'dot'` 时需要数组格式，不指定 type 时直接传对象

**解决**:
- 初始化: `grid: { size: 20, visible: true, args: { color: '...', thickness: 1 } }`（不指定type，使用默认dot preset）
- 同步: 使用 X6 原生方法 `graph.showGrid()` / `graph.hideGrid()` / `graph.setGridSize()`
- `drawGrid` 仅用于颜色/粗细变更，不传 type 参数简化路径

**X6 Grid API 关键方法**（运行时存在但不在 TS 类型中）:
- `graph.showGrid()` / `graph.hideGrid()` — 显隐切换
- `graph.setGridSize(n)` — 改变网格大小
- `graph.drawGrid(options)` — 重绘网格
- `graph.clearGrid()` — 清除网格

**Why:** X6 v2.19.2 的 TypeScript 类型定义不完整，grid 大部分方法需要在 `(graph as any)` 下调用。

---

## 问题13: 流水线 WebSocket 404 + REST 422

**现象**: 启动流水线时报：
- `GET /api/pipeline/pipe_xxx → 404`（pipeline 未找到）
- `POST /api/pipeline/create → 422`（请求体格式错误）

**根因**:
1. **404**: 前端 useEffect 在 WebSocket 连接之前就通过 REST 查询 pipeline 状态，但 pipeline 只在 WebSocket handler 内创建，此时尚不存在
2. **422**: FastAPI 端点 `create_pipeline_endpoint(req: PipelineCreateRequest, diagram: UmlDiagram)` 接收两个独立 Pydantic 模型参数，但前端发送 `{ diagram_id, ...diagram flat fields }` 扁平结构，FastAPI 无法正确解析

**解决**:
- **404**: 启动前先通过 REST 创建 pipeline，再开 WebSocket；useEffect 改为忽略 404 错误
- **422**: 创建组合请求模型 `CreatePipelineBody` 包含嵌套 `diagram` 字段
```python
class CreatePipelineBody(BaseModel):
    diagram_id: str
    auto_confirm: bool = False
    diagram: UmlDiagram
```
前端发送 `{ diagram_id, diagram: {...} }` 嵌套格式

**Why:** FastAPI 单个 JSON body 无法自动拆分为多个 Pydantic 参数，需要嵌套模型。

---

## 问题14: Vite WebSocket 代理未配置

**现象**: WebSocket 连接到 `ws://localhost:3000/api/pipeline/ws/{id}` 返回 404。

**根因**: Vite 代理配置中 `/api` 规则缺少 `ws: true`，导致 WebSocket 升级请求被当作普通 HTTP 处理。

**解决**: 在 vite.config.ts 的 `/api` 代理规则中添加 `ws: true`：
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    ws: true,  // 允许 WebSocket 升级
  },
}
```
注意: Vite 配置修改后需要重启 dev server（`taskkill //F //IM node.exe`）。

**Why:** WebSocket 通过 HTTP Upgrade 机制建立连接，代理必须显式支持。

---

## 问题15: 画布上类节点位置堆叠

**(补充)** 节点同步也需要防止位置抖动。节点位置和尺寸更新应只在值实际变化时才调用 `setPosition`/`setSize`，避免每帧都触发 setter 导致性能问题。

---

## 问题16: Python Enum 属性大小写错误

**现象**: `type object 'StageName' has no attribute 'uml_optimize'` 运行时错误。

**根因**: Python `str, Enum` 类属性区分大小写。`StageName.UML_OPTIMIZE`（大写）是正确的，`StageName.uml_optimize`（小写）不存在。

**解决**: 统一使用 `StageName.UML_OPTIMIZE`、`StageStatus.SKIPPED` 等大写形式访问枚举成员。

**Why:** Python 的 Enum 成员名遵从 Python 变量命名规范（大写），即使值是小写字符串。

---

---

## 问题17: Excel 中文乱码 — Python UTF-8 模式

**现象**: 
- 终端运行 `python testHub/gen_testcases.py` 生成 Excel，中文 sheet 名称显示为乱码
- 后端 API 返回的 JSON 中中文变成代理对（`\udca7\udc88`）
- 前端加载测试用例文件后显示乱码

**根因**: Windows 中文版 Python 默认使用 GBK 编码（而非 UTF-8）。`gen_testcases.py` 文件中包含中文字符串（如"用例概览"），Python 在非 UTF-8 模式下解释为 GBK 乱码，写入 Excel 后数据永久损坏。

**解决**:
1. **Python 脚本**：首行添加 `# -*- coding: utf-8 -*-` 声明源文件编码
2. **启动 Python**：设置环境变量 `PYTHONUTF8=1` 强制 UTF-8 模式
3. **后端启动**：`start.bat` 中 `set PYTHONUTF8=1 & python -m app.main`
4. **验证方法**：检查原始 JSON 字节是否为合法 UTF-8 序列

```bash
# 正确启动方式
export PYTHONUTF8=1 && python testHub/gen_testcases.py
```

**注意**: `PYTHONUTF8` 必须在 Python 进程启动前设置，`os.environ.setdefault()` 在运行时设置无效。

**Why:** Python 3.7+ 引入了 UTF-8 模式（PEP 540），Windows 需要显式开启。否则 locale.getpreferredencoding() 返回 GBK。

---

## 问题18: GitHub push 认证失败

**现象**: 
```bash
$ git push -u origin master
remote: Invalid username or token.
Password authentication is not supported for Git operations.
fatal: Authentication failed
```

**根因**: GitHub 自 2021 年 8 月起废弃了密码认证，所有 Git 操作必须使用 SSH Key 或 Personal Access Token (PAT)。

**解决**:
- **SSH Key**（推荐）：`ssh-keygen` 生成密钥 → GitHub Settings → SSH Keys 添加公钥 → 远程地址改为 `git@github.com:user/repo.git`
- **PAT Token**：GitHub Settings → Developer settings → Personal Access Token → 生成 token → 远程地址 `https://token@github.com/user/repo.git`

```bash
# SSH 方式
git remote set-url origin git@github.com:Zhuweilong123/UML_design.git

# Token 方式
git remote set-url origin https://<token>@github.com/Zhuweilong123/UML_design.git
```

**Why:** 密码认证安全性不足，GitHub 强制使用更安全的认证方式。

---

## 问题19: 国内访问 GitHub 网络问题

**现象**: GitHub 网站打不开、加载极慢，但 `curl https://github.com` 返回 200。

**根因**: 国内网络对 GitHub 的 DNS 污染和间歇性阻断。有时能 ping 通但 web UI 加载超时，Git 命令行操作也可能失败。

**解决**:
1. **配置 Git 代理**（如有梯子）：
   ```bash
   git config --global http.proxy http://127.0.0.1:7890
   git config --global https.proxy http://127.0.0.1:7890
   ```
2. **使用 Gitee 码云**：国内镜像仓库，访问稳定
3. **修改 hosts**：添加 GitHub 的最新 IP 映射
4. **使用 gh CLI**：`winget install GitHub.cli` 后用 `gh auth login` 认证

**诊断命令**:
```bash
curl -s -o /dev/null -w "%{http_code}" https://github.com --connect-timeout 5
```

**Why:** GFW 策略对 GitHub 的阻断时强时弱，需要多种应对方案。

---

## 问题20: 流水线 Stage 4（用例检视）不暂停

**现象**: 自动化流水线到达 Stage 4 后不停留，直接跳过到 Stage 5。

**根因**: `resume_pipeline` 中的 Stage 4 代码为旧版，直接 `yield SUCCESS` 跳过了，没有像 `run_pipeline` 那样 yield `request_case_review` 并 return 暂停。

**解决**: 
- `resume_pipeline` 的 Stage 4 改为和 `run_pipeline` 一致：先 yield RUNNING，再 yield `request_case_review` 事件，最后 return 等待
- WebSocket handler 中所有可能到达 Stage 4 的路径（`skip_instructions`、`listen_for_commands`、main loop）都注册了 `wait_for_case_review()` 等待逻辑
- 确认后通过 `confirm_case_review` action 恢复，传 `skip_case_review=True` 跳过重复暂停

**Why:** 多条代码路径（提交优化/跳过/接受拒绝）都能到达 Stage 4，每条路径都需要注册对应的暂停逻辑。

---

## 问题21: 流水线完成后进度条停在 86%

**现象**: 所有阶段执行完毕，但进度条显示 86%（6/7），未到 100%。

**根因**: 
1. `resume_pipeline` 最后阶段（code_optimize）成功完成后，WebSocket 主循环自然退出，但未发送"完成"信号
2. WebSocket 关闭后前端 `onclose` 追加"(连接关闭)"文字

**解决**:
- 后端主循环结束后发送 `pipeline_complete` 事件
- 前端收到后设置 `completed=true`，进度条强制 100% 并变绿
- `ws.onclose` 对已完成/已停止的流水线不再追加"(连接关闭)"

---

## 问题22: 代码产物中测试代码不显示

**现象**: 流水线侧边栏"测试代码"始终显示"待生成"，但磁盘 `generated/test/` 目录下已有文件。

**根因**: `resume_pipeline` 的 Stage 5 代码调用了 `generate_tests()` 和 `_save_generated_files()`，但**没有将测试文件添加到 `pipeline.code_artifacts`**。只有 `run_pipeline` 的 Stage 5 有 append 逻辑。

**解决**: 在 `resume_pipeline` Stage 5 添加：
```python
for fname, content in test_files.items():
    pipeline.code_artifacts.append(CodeArtifact(
        language=language, filename=fname, content=content, version=2,
    ))
```
同时使用 `version=2` 标记测试产物，`version=1` 标记源代码产物，前端通过文件名前缀 `test_` 分类显示。

---

## 问题23: 源代码产物重复显示

**现象**: 代码产物中相同源文件出现两次。

**根因**: `resume_pipeline` 在两条路径中被调用：
1. 从 dev_confirm 恢复 → 跑 Stage 3（生成源代码）
2. 从 case_review 确认 → 又跑 Stage 3（再次生成源代码）

两次调用都会 `pipeline.code_artifacts.append()`，导致重复。

**解决**: 添加 `skip_code_gen` 参数：
- 从 dev_confirm 恢复时：`skip_code_gen=False`（首次生成源代码）
- 从 case_review 确认时：`skip_code_gen=True`（复用已有源代码，直接跳到 Stage 5）

**Why:** 流水线暂停-恢复机制中，恢复函数可能被多次调用，需要标志位跳过已完成的阶段。

---

## 问题24: 优化需求弹窗消失

**现象**: 流水线启动后不弹出优化需求输入框，直接跳过。

**根因**: 在 `ws.onmessage` 中添加 `request_case_review` 处理时，误复制了一行空的 `else if (data.event === 'request_instructions') {}`，导致真正的 `request_instructions` 处理逻辑被跳过。

**解决**: 删除重复的空行。

**Why:** 重复的 if-else 分支中 JS 只会进入第一个匹配的分支。

---

## 问题25: "检视完成，继续"按钮无响应

**现象**: Stage 4 暂停后点击"检视完成，继续"按钮，流水线不继续运行。

**根因**: `confirm_case_review` 消息通过 WebSocket 发送后，主循环已退出（因为 `break`），消息无人接收。多条到达 Stage 4 的路径中只有部分注册了接收逻辑。

**解决**: 
- 在 `wait_for_instructions`（skip_instructions handler）和 `listen_for_commands`（confirm handler）中都注册了 `confirm_case_review` 处理
- 统一调用 `resume_pipeline(skip_case_review=True, skip_code_gen=True)` 恢复流水线

---

## 关键技术要点总结

1. **AntV X6 v2 自定义节点**: 使用 `Graph.registerNode()`（不是 `Node.registry.register()`），在创建 Graph 之前调用
2. **HTML 渲染**: 通过 `foreignObject` + `div` markup，使用 `attrs.content.html` 和 `node.setAttrByPath('content/html', ...)` 设置内容
3. **端口**: 在节点定义中配置 `ports` 属性，使用 CSS 控制显隐
4. **键盘快捷键**: 使用 DOM 事件而非 X6 的 `bindKey`
5. **撤销/重做**: 通过 History 插件 + Zustand 状态快照实现
6. **npm 兼容性**: 使用 `--legacy-peer-deps` 或精确版本号解决依赖冲突
7. **LLM 输出容错**: 必须对 LLM 返回的结构化数据做字段名映射、枚举值归一化、缺失字段填充
8. **Pydantic 防御**: 所有模型加 `model_config = {"extra": "ignore"}`，组合请求体用嵌套模型
9. **后端调试**: 端点加 try/except + traceback，先用 curl 隔离测试
10. **双向数据同步**: 增删改都要处理，不能只处理新增和删除
11. **X6 运行时 API**: 许多方法在 TS 类型定义中缺失，需要 `(graph as any)` 调用
12. **FastAPI 请求体**: 单个 JSON body → 单个 Pydantic 模型，多个参数需嵌套
13. **Vite 代理**: WebSocket 需要 `ws: true`
14. **Python Enum**: 枚举成员名大写
15. **Python 编码**: Windows 必须 `PYTHONUTF8=1`，脚本声明 `# -*- coding: utf-8 -*-`
16. **GitHub 认证**: 不再支持密码，必须用 SSH Key 或 PAT Token
17. **Git 代理**: 国内网络需 `git config http.proxy` 或换 Gitee
18. **流水线暂停-恢复**: 多条代码路径可能到达同一阶段，每条都要注册暂停/恢复逻辑
19. **skip 标志位**: 恢复函数要支持跳过已完成阶段，避免重复执行
20. **WebSocket 生命周期**: 流水线完成/暂停/错误时都要发送明确事件，不能让前端靠 onclose 推断状态

**Why:** 这些是项目开发中遇到的实际问题，记录了从设计文档到可运行代码的完整调试过程。

**How to apply:** 
- 新节点类型开发参考问题1-2的代码模式
- npm 包更新时参考问题4的版本兼容性
- X6 API 使用参考问题5的类型修正 + 问题12的 grid API
- 端口和连线功能参考问题6 + 问题11的双向同步
- LLM 集成时必须参考问题8做输出归一化
- FastAPI 端点设计参考问题13的组合请求体模式
- Python 编码参考问题17的 PYTHONUTF8 方案
- GitHub 推送参考问题18-19的认证和代理
- 端口和连线功能参考问题6 + 问题11的双向同步
- LLM 集成时必须参考问题8做输出归一化
- FastAPI 端点设计参考问题13的组合请求体模式
