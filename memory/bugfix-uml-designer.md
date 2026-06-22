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
| 26 | ReAct 工具调用 coroutine 未 await | Tool.execute lambda 返回协程但引擎未 await | 后端/ReAct |
| 27 | ReAct API 400 错误 | DeepSeek 不支持 OpenAI function calling 的 tool_calls 格式 | 后端/ReAct |
| 28 | 优化仅1轮就停止 | LLM 自称完成但实际未修复，缺少验证机制 | 后端/流水线 |
| 29 | 日志只记录最后一轮 | 优化结果被覆盖，历史未保存 | 后端/流水线 |
| 30 | 文件无法打开（全部 API 失败） | Vite 代理端口 8001，后端监听 8000 — 端口不匹配 | 环境/前端 |
| 31 | 生成的测试用例不包含用例ID | ① Sheet "用例概览" 污染 ② 列索引硬编码 ③ LLM 提示词源码优先于用例 | LLM/后端 |
| 32 | 后端代码修改后不生效 | 多个僵尸 Python 进程占 8000 端口，StatReload 重载不到新代码 | 环境 |
| 33 | Python 3.14 PYTHONUTF8 崩溃 | `set PYTHONUTF8=1` 触发 fatal error，改用 `-X utf8` | 环境/Python |
| 34 | Stage 6/7 LLM 模拟测试不可靠 | `_execute_tests()` LLM猜PASS/FAIL，每次不同 → 改真实pytest subprocess | 后端/流水线 |
| 35 | Stage 6 ReAct 盲修测试 | Action解析失败、工具bug → 去掉ReAct，简化为LLM一次性编译修复 | 后端/流水线 |
| 36 | Path.parent 路径算错 | Python 3.9+ `Path(".").parent` 返回自身 → 全改 `.resolve().parent.parent` | 后端 |
| 37 | 改代码不生效 | `.pyc` 缓存优先源码 → `sys.dont_write_bytecode = True` | 后端/环境 |
| 38 | 测试数量不一致 | `new_test_results[:2000]` 截断 → 去截断、展示上限提到5000 | 后端/流水线 |
| 39 | 失败原因无法提取 | regex 不兼容 `\r\n` + pytest格式 → 三策略递进匹配 | 后端/流水线 |
| 40 | 测试文件保存不清理旧文件 | JSON解析失败fallback存非法.py，旧文件残留被pytest收集 | 后端/流水线 |
| 41 | 最终测试结果和第三轮不一致 | for-else多余的`_execute_tests`覆盖了最后一轮的正确数据 | 后端/流水线 |
| 42 | 前端转圈不停+进度条不到100% | running/completed独立state手动维护，事件时序问题 | 前端 |
| 43 | 后端日志缺少时间戳 | uvicorn/logging默认无`asctime` | 后端/日志 |
| 44 | API Key 硬编码在 config.py 默认值中 | 真实 Key 随代码提交 Git，永久暴露在历史记录 | 安全 |
| 45 | 全端点无鉴权，任何人可调 LLM API | 无认证机制，公网部署后 API 配额可被盗刷 | 安全 |
| 46 | 文件端点目录遍历漏洞 | `/api/files/open` 和 `/browse` 接受任意路径参数，可读取项目外任意文件 | 安全 |
| 47 | FastAPI HTTPBearer 子依赖注入失败 | `Depends` 嵌套闭包时 `request` 参数无法自动注入 | 后端/鉴权 |
| 48 | WebSocket 路由级 Depends 报错 | WebSocket 不支持 HTTP 的 `Depends` 依赖注入机制 | 后端/鉴权 |
| 49 | Windows asyncio subprocess 抛 NotImplementedError | ProactorEventLoop 不支持 `create_subprocess_exec`，pytest 无法真实执行 | 后端/测试 |
| 50 | `__pycache__` 残留导致 pytest 0 tests collected | 旧测试目录的 `.pyc` 缓存引用旧路径，与新位置冲突 | 后端/测试 |
| 51 | Stage 5 JSON 解析失败 | `generate_tests` 等未开 `json_mode`，`clean_llm_json_response` 只处理开头 ``` 的情况 | LLM/后端 |
| 52 | Stage 7 三轮优化无改善 | 优化 prompt 只看错误行不看测试代码，LLM 猜不出缺失函数的签名 | 后端/流水线 |
| 53 | Stage 6 误拦截对象级 AttributeError | `_extract_fatal_errors` 把 `'Foo' object has no attribute 'bar'` 当做编译错误 | 后端/流水线 |
| 54 | 未选目录时保存到旧嵌套路径 | `_save_generated_files` 默认路径含 `{project}/{language}` 子目录，与扁平结构不一致 | 后端/流水线 |
| 55 | 目录选择每次都要重选 | 前端 `pipelineSourceDir/TestDir` 存内存，刷新丢失 | 前端 |

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

## 问题26: ReAct 引擎工具执行 coroutine 未 await

**现象**: 工具调用返回值是 `<coroutine object>` 而不是实际结果字符串，引擎打印 `RuntimeWarning: coroutine was never awaited`。

**根因**: `Tool.execute` 是 lambda 包装的异步函数（如 `_validate_syntax`），lambda 返回的是 coroutine 对象但引擎中直接使用返回值，没有 await。

**解决**:
- `Tool` 新增 `async run(**kwargs)` 方法，内部处理 coroutine vs 普通值：
```python
async def run(self, **kwargs) -> str:
    result = self.execute(**kwargs)
    if asyncio.coroutines.iscoroutine(result):
        result = await result
    return str(result)
```
- 引擎统一调用 `await tool.run(**func_args)` 替代原来的直接调用

**Why:** Python 的 coroutine 必须显式 await，lambda 包装的 async 函数不会自动执行。

---

## 问题27: ReAct 引擎 DeepSeek API 400 错误

**现象**: 运行流水线后所有 ReAct 阶段报错：
```
Error code: 400 - "An assistant message with tool_calls must be followed
by tool messages responding to each tool_call_id"
```

**根因**: `deepseek-chat` 模型不兼容 OpenAI 原生 function calling 格式（`tools`/`tool_choice`/`tool_calls`消息）。消息格式不符合 DeepSeek 预期。

**解决**: 改为纯文本方式实现工具调用：
- LLM 输出使用 `THOUGHT:` + `ACTION:` + JSON 代码块格式
- 引擎用正则解析 `ACTION: xxx` 和 JSON 参数
- 工具结果作为普通 user 消息追加，不依赖特殊消息格式

**优势**: 兼容所有 LLM（DeepSeek/GPT/Claude），上下文文件可读性更好，调试更容易。

---

## 问题28: 优化仅1轮就停止（LLM 虚假完成）

**现象**: 跑完3轮优化但实际只有1轮有效，后两轮结果被覆盖。且 LLM 在测试仍有失败时自称"完成"。

**根因**: 
1. `finish_optimization` 的"成功"仅基于 LLM 声称，未重新验证
2. 每轮结果互相覆盖，最终流水线日志只显示最后一轮

**解决**:
- 每轮 ReAct 优化后强制执行 `_execute_tests` 重新分析测试结果
- 检查实际结果中是否有 `FAIL`，有则继续下一轮
- 用 `rounds_history` 列表累积每轮结果，日志中逐轮展示

---

## 问题29: 优化日志只记录最后一轮

**现象**: 流水线日志只显示最后一轮优化结果，无法对比各轮效果。

**解决**: 
- Stage 7 循环中新增 `rounds_history` 列表，每轮追加 `round_record`
- 记录每轮的 ReAct 步骤、通过/失败数、通过率、失败用例
- 日志中逐轮展示详情 + 优化效果对比表（轮次/通过/失败/通过率）

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
21. **LLM 兼容性**: 并非所有模型支持原生 function calling，文本格式更通用
22. **虚假完成检测**: 不能信任 LLM 声称"已完成"，必须用实际测试结果验证
23. **日志累积**: 迭代优化必须累积记录每轮结果，不能互相覆盖
24. **API Key 绝不可硬编码**: 所有密钥必须从环境变量/配置文件读取，代码默认值残留的真实 Key 会随 Git 历史永久泄露
25. **鉴权须在投产前实现**: 即使最简单的 Bearer Token 也比无鉴权好，可按需启用/跳过（本地开发留空）
26. **用户输入路径必须校验**: 所有文件操作端点的路径参数需用 `os.path.commonpath` + `os.path.realpath` 做沙箱限制
27. **Depends 嵌套有坑**: HTTPBearer 等类实例作为子依赖时 `request` 注入失败，改为直接从 Request 对象读取头
28. **WebSocket 不支持路由级 Depends**: 含 WebSocket 的路由需逐 HTTP 路由加 Depends，WebSocket 端点在函数内手工校验
29. **Windows asyncio 子进程用 to_thread**: `create_subprocess_exec` 在 ProactorEventLoop 下有兼容问题，`asyncio.to_thread(subprocess.run)` 更可靠

**Why:** 这些是项目开发中遇到的实际问题，记录了从设计文档到可运行代码的完整调试过程。

**How to apply:**
- 新节点类型参考问题1-2
- npm 版本兼容参考问题4
- X6 Grid API 参考问题12
- LLM 输出归一化参考问题8
- FastAPI 请求体设计参考问题13
- Python UTF-8 编码参考问题17
- 文件路径安全参考问题46
- API 鉴权参考问题44-45, 47-48
- asyncio 子进程参考问题49

---

## 问题30: 文件无法打开 — Vite 代理端口不匹配

**现象**: 点击"打开"按钮后文件列表为空，"加载文件列表失败"；所有 API 请求失败。

**根因**: `vite.config.ts` 代理 `/api` 到 `http://localhost:8001`，但后端在端口 `8000`。前端所有请求被代理到无进程端口。

**解决**: 改 `target` 为 `http://localhost:8000`。Vite 配置不支持 HMR，必须重启 dev server。

---

## 问题31: 生成的测试用例不包含用例ID

**现象**: 流水线 Stage 5 生成测试函数名为通用名（如 `test_initialization`），没有用例ID。

**根因（三层）**:
1. Sheet 污染: Excel 首个 Sheet "用例概览" 无"用例ID"列，旧代码 `headers[0]` 误取为ID
2. 列索引硬编码: `TestCaseViewer.tsx` 和 `testhub.py` 都用 `headers[0]/[1]/[2]/[4]/[5]` 硬编码
3. 提示词结构: `_build_test_prompt()` 源码放在用例需求之前，LLM 忽略用例ID

**解决**:
1. 前端 `findCol(headers, keywords)` 按关键词匹配列名，无ID列Sheet跳过
2. 后端 `_find_col()` 同理
3. 提示词重构: 用例需求置顶 + `TC-OTA-001 → def test_TC_OTA_001_xxx()` 强制映射示例 + 源码降级

---

## 问题32: 后端代码修改后不生效 — 僵尸进程

**现象**: 修改后端文件后流水线行为不变，新增日志不输出。

**根因**: 多个 Python 进程同时占 8000 端口，旧僵尸进程处理实际请求。`netstat -ano | findstr :8000` 显示两个 PID。

**解决**: `taskkill /F /IM python.exe` 全杀后重启。

---

## 问题33: Python 3.14 PYTHONUTF8 崩溃

**现象**: `Fatal Python error: preconfig_init_utf8_mode: invalid PYTHONUTF8 environment variable value`

**根因**: `set PYTHONUTF8=1` 在 Python 3.14 被拒绝。

**解决**: 改用 `python -X utf8`。同时修复 `start.bat`: `%~dp0` 替代硬编码、移除全杀进程、`npm run dev`。

---

## 问题34: Stage 6/7 LLM 模拟测试结果不可靠

**现象**: Stage 7 代码优化三轮，通过率在 4%~42% 随机跳变，有时负优化。

**根因**: `_execute_tests()` 把测试代码发给 LLM 让它"猜" PASS/FAIL。LLM 无 Python 运行时，结果完全随机。

**解决**: 用 `asyncio.create_subprocess_exec` 跑真实 `pytest -v --tb=short`，PYTHONPATH 确保 import。pytest 不可用时回退 LLM 模拟。

## 问题35: Stage 6 用 ReAct 盲修测试代码

**现象**: Stage 6 跑 2 轮 ReAct，大量 "No action parsed" 解析失败。

**根因**: ReAct action 解析（`_parse_action`）对 DeepSeek 格式匹配差；`diff_code` lambda 参数 bug。

**解决**: 去掉 `ReActEngine`/`ReActResult`。简化为：pytest → 提取编译错误 → LLM 一次性修复 → 重跑，最多2轮。失败阻断。

## 问题36: `Path(".").parent` 在 Python 3.13 不往上走

**现象**: "Test directory empty or missing"，文件明明存在。

**根因**: Python 3.9+ `Path(".").parent` 返回 `"."` 自身。`.parent.parent` 路径算错。

**解决**: 全部改为 `.resolve().parent.parent`，先展开绝对路径再取父目录。

## 问题37: `__pycache__` 导致改代码不生效

**现象**: 改后端代码重启后行为不变。

**根因**: `.pyc` 缓存优先于源码，修改 `.py` 后缓存未失效。

**解决**: `main.py` 加 `sys.dont_write_bytecode = True` 禁止生成 `.pyc`。

## 问题38: 测试结果截断导致数量不一致

**现象**: "47 通过 / 47 总计" 但 "全部通过 (39 个)"，数量矛盾。

**根因**: `new_test_results[:2000]` — 47 条 ~3055 字符被截到 2000。"47" 用预计算整数，"(39)" 从截断文本实时统计。

**解决**: 轮次记录去截断，Stage 6 展示上限提到 5000。

## 问题39: pytest 失败原因无法提取

**现象**: 日志只显示 "Test: xxx -> FAIL"，无失败原因。

**根因**: `_extract_failure_reason()` regex 不兼容 Windows `\r\n` 和 pytest `--tb=short` 的 `FAILURES` 段落。

**解决**: 三策略递进匹配 `E   ErrorType: message`，regex 全用 `\r?\n`。

---

## 新需求: 流水线日志文件级统计

Stage 7 每轮末尾加各文件 PASS/FAIL 表格。`_build_per_file_stats()` 按用例 ID 前缀（`TC_BASE`→BaseTask...）映射模块名，统计每文件通过率。

## 新需求: 后端日志加时间戳

`main.py` 配置 `logging.basicConfig(format="%(asctime)s | ...")` + 覆盖 uvicorn `LOGGING_CONFIG`。

## 新需求: UML 类图备注传递到代码生成

`_build_class_prompt` 加入 `c.note`（Business Rules）、关系元数据。`optimize_uml` 加规则保留 note。`_build_test_prompt` 加 `_extract_api_signatures()` 提取源码 API 签名。

---

## 问题40: 测试文件保存不清理旧文件导致残留

**现象**: 最新生成的测试用例是有问题的（LLM JSON 解析失败，原始响应被存成 .py），但 pytest 竟然跑起来了，显示 46 PASS。

**根因**: 
1. `generate_tests()` 的 `except JSONDecodeError` fallback 把 LLM 原始 JSON 响应存为 `test_main.py`（内容以 ```json 开头，不是合法 Python）
2. `_save_generated_files()` 只写新文件不删旧文件，上次残留的有效 `.py` 文件被 pytest 收集执行

**解决**: 
1. `generate_tests`/`generate_code` 的 JSON 解析失败 fallback 改为返回空 `{}`，记录 warning 日志
2. `_save_generated_files` 写测试文件前 `shutil.rmtree(test_dir)` 清空目录
3. `generate_tests`/`generate_code` 返回空时 Stage 3/5 标 FAILED 并阻断
4. `_execute_tests` 目录为空时直接报错，不用 LLM 模拟

**Why:** 三条防线确保：要么成功生成、要么明确失败，不存在"看起来跑了其实是旧数据"的假象。

## 问题41: 最终测试结果和第三轮不一致

**现象**: 流水线日志 Round 3 显示 49% 通过率，但"最终测试结果"显示 21%。

**根因**: Stage 7 的 for-else 结构中，`else` 分支在 3 轮循环结束后额外调用了一次 `_execute_tests`，将 `pipeline.stages[5].result["test_results"]` 覆盖为新值。这次额外的 pytest 调用结果与第三轮不同（21% vs 49%），导致 `_save_pipeline_log` 读到的最终数据被污染。

**解决**: 删除 `else` 分支中多余的 `_execute_tests` 调用。"最终测试结果"直接用最后一轮的数据，不需要额外跑一次 pytest。

**Why:** for-else 被误用为"兜底调用"，但数据已在循环内正确保存，else 的重复调用反而覆盖了正确结果。

## 问题42: 前端流水线完成后转圈不停 + 进度条不到100%

**现象**: Stage 7 全部完成后 Loading 图标一直转；进度条停在 86% 不达 100%。

**根因**: 
1. `running`/`completed` 是独立 state，靠 WS 事件回调手动切换。`pipeline_complete` 将 `manualRunning` 置 false 后，`completed = manualRunning && allStagesTerminal` 跟着变 false
2. `completedStages` 只计 `SUCCESS` 不计 `SKIPPED`/`FAILED`（Stage 1 被跳过 → 6/7 = 86%）

**解决**: `running` 和 `showCompleted` 从 pipeline 阶段状态直接推导，不依赖 `manualRunning`。`completedStages` 计入 `SKIPPED`/`FAILED`。

**Why:** 派生状态（derived state）优于手动维护的独立状态，避免事件时序问题导致的不一致。

## 问题43: 后端日志缺少时间戳

**现象**: 后端 uvicorn 和 logging 输出没有任何时间信息。

**根因**: uvicorn 默认日志格式和 Python `logging` 默认格式都不含 `%(asctime)s`。

**解决**: `main.py` 配置 `logging.basicConfig(format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")` + 覆盖 uvicorn `LOGGING_CONFIG` 的 formatter。

**Why:** 无时间戳导致无法追踪问题发生时间、无法关联流水线日志和后端日志。

---

## 问题44: API Key 硬编码在 config.py 默认值中

**现象**: Git 仓库历史中包含真实的 DeepSeek API Key `sk-3b6b0eaa3b374234a8047e0c60844b24`。

**根因**: `backend/app/core/config.py` 中 `deepseek_api_key: str = "sk-3b6b0eaa..."` 写死了真实 Key 作为默认值。即使 `.env` 被 `.gitignore` 排除，代码本身被提交到 Git 后 Key 永久暴露在历史记录中。

**解决**:
1. 移除默认值，改为 `Field(...)` 强制从 `.env` 读取（无 .env 时启动即报错，不会静默用旧 Key）
2. 添加 `field_validator` 检测已知泄露的前缀（`sk-3b6b0eaa` 等），命中则打印 WARNING
3. **需要手动去 DeepSeek 后台轮换 Key**（代码修复不会自动撤销已泄露的 Key）

```python
# 修复前
deepseek_api_key: str = "sk-3b6b0eaa..."  # ❌ 硬编码

# 修复后
deepseek_api_key: str = Field(..., description="必须从 .env 读取")  # ✅ 无默认值
```

**涉及文件**: `backend/app/core/config.py`

**Why:** 这是 P0 安全问题，泄露的 API Key 可被任何人用于调用 DeepSeek API，产生费用。

---

## 问题45: 全端点无鉴权

**现象**: 所有 API 端点（LLM 代码生成/聊天、流水线操作、文件写入）无需任何认证即可访问。

**根因**: 项目设计阶段未实现认证层，直接暴露所有端点。任何人知道服务地址就能调用 DeepSeek API 消耗配额。

**解决**: 新建 `backend/app/core/auth.py` 实现 Bearer Token 鉴权：

```python
async def require_auth(request: Request):
    settings = get_settings()
    if not settings.internal_api_token:
        return  # 本地开发：未配置则跳过
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(401)
    if not hmac.compare_digest(token, settings.internal_api_token):
        raise HTTPException(403)
```

**受保护端点**: `/api/llm/*`（路由级）、`/api/pipeline/*`（逐路由）、`/api/testhub/*`（路由级）、`/api/files/(save|upload|save-review|save-generated)`（逐路由）

**不受保护**: `/api/files/(list|open|browse|new|export)`（可公开读取）、`/api/health`

**配置**: 后端 `.env` 设 `INTERNAL_API_TOKEN=xxx`，前端 `.env.local` 设 `VITE_API_TOKEN=xxx`（两值相同）。都留空则鉴权跳过。

**涉及文件**: `backend/app/core/auth.py`, `backend/app/main.py`, `backend/app/api/files.py`, `backend/app/api/pipeline.py`, `frontend/src/services/api.ts`

**Why:** 防止未授权访问消耗 LLM API 配额或篡改文件。

---

## 问题46: 文件端点目录遍历漏洞

**现象**: `/api/files/open?filepath=/etc/passwd` 可读取系统任意文件；`/api/files/browse?path=../../` 可遍历任意目录。

**根因**: `open_file` 和 `browse_directory` 直接使用用户传入的路径参数，未做任何安全检查。

**解决**:
1. 新增 `_safe_path()` 函数：将用户路径解析后与项目根目录做 `os.path.commonpath` 前缀检查，不在项目内则返回 403
2. `open_file` 额外限制只能打开 `.uml` 文件
3. `upload_excel` 用 `os.path.basename()` 剥离路径 + 拒绝 `.` 开头的隐藏文件
4. `save_file` 用 `_sanitize_path_segment()` 净化文件名中的 `../` 和特殊字符
5. `save_generated_code` 对 `project_name` 和 `language` 字段做相同净化

```python
def _safe_path(user_path: str) -> str:
    project_root = os.path.abspath(os.path.join(settings.uml_dir, "..", ".."))
    candidate = os.path.abspath(os.path.join(project_root, user_path))
    real = os.path.realpath(candidate)  # 解析符号链接
    if os.path.commonpath([real, os.path.realpath(project_root)]) != os.path.realpath(project_root):
        raise HTTPException(403)
    return real
```

**涉及文件**: `backend/app/api/files.py`

**Why:** 不限制路径范围会暴露整个文件系统，攻击者可读取配置文件（含 API Key）、系统文件等敏感信息。

---

## 问题47: FastAPI HTTPBearer 子依赖注入失败

**现象**: 启动后端后流水线相关请求报 `TypeError: HTTPBearer.__call__() missing 1 required positional argument: 'request'`。

**根因**: 最初用 `HTTPBearer` 类实例作为子依赖：
```python
_security = HTTPBearer(auto_error=False)
async def get_token(creds = Depends(_security)):  # ❌ 子依赖中 request 注入失败
    ...
```
FastAPI 在处理 `Depends` 嵌套时，`HTTPBearer.__call__()` 需要的 `request` 参数无法自动注入到子依赖中。

**解决**: 放弃 `HTTPBearer`，直接从 `Request` 对象读取 `Authorization` 头：
```python
async def require_auth(request: Request):
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ")
    ...
```

**涉及文件**: `backend/app/core/auth.py`

**Why:** FastAPI 的 `Depends` 嵌套有局限性，类实例的 `__call__` 作为子依赖时参数解析路径与顶层不同。

---

## 问题48: WebSocket 路由级 Depends 与 HTTP 不兼容

**现象**: `Depends(require_auth)` 在包括 WebSocket 端点的路由上使用时，WebSocket 握手阶段报 `TypeError: require_auth() missing 1 required positional argument: 'request'`。

**根因**: FastAPI 的 `Depends` 依赖注入机制是为 HTTP 端点设计的，WebSocket 端点使用不同的依赖解析路径。路由级 `dependencies=[Depends(require_auth)]` 会对该路由下所有端点（包括 WebSocket）生效，导致 WebSocket 端点尝试注入 `request` 时失败。

**解决**: 
1. 从路由级移除 `Depends`
2. 为每个 HTTP 路由单独添加 `@router.post("...", dependencies=[Depends(require_auth)])`
3. WebSocket 端点用手工校验：`if not hmac.compare_digest(token, settings.internal_api_token): ws.close()`

**涉及文件**: `backend/app/main.py`, `backend/app/api/pipeline.py`

**Why:** WebSocket 和 HTTP 是两套不同的 ASGI 协议，FastAPI 的依赖注入对两者的支持程度不同。

---

## 问题49: Windows asyncio.create_subprocess_exec NotImplementedError

**现象**: 流水线 Stage 6 执行测试时报 `NotImplementedError`，回退到 LLM 模拟测试（凭空猜 PASS/FAIL），导致测试结果不准确、优化方向错误。

**根因**: Windows 默认的 `ProactorEventLoop` 不完全支持 `asyncio.create_subprocess_exec`，某些场景下抛 `NotImplementedError`。这是 Python asyncio 在 Windows 上的已知限制。

**解决**: 用 `asyncio.to_thread()` + 同步 `subprocess.run()` 替代：
```python
# 修复前
proc = await asyncio.create_subprocess_exec(*cmd, ...)  # ❌ Windows 报错

# 修复后
result = await asyncio.to_thread(subprocess.run, cmd, ...)  # ✅ 线程池中同步执行
```

**日志区分**: 
- 真实 pytest: `[TestExec] ========== Running real pytest ==========`
- LLM 模拟: `[TestExec] ========== LLM SIMULATION MODE (not real pytest!) ==========`（WARNING 级别，醒目分隔线）

**涉及文件**: `backend/app/services/pipeline_service.py`

**Why:** 真实 pytest 执行是流水线 Stage 6/7 的核心，LLM 模拟结果不可靠，会导致代码优化方向完全错误。

---

## 问题50: `__pycache__` 残留导致 pytest 0 tests collected

**现象**: 流水线 Stage 6 报 `import file mismatch: imported module has __file__ at old/path which is not the same as new/path`，collect 0 个测试。

**根因**: 旧测试在 `generated/test/Untitled/python/` 被删除，但 `__pycache__` 残留的 `.pyc` 仍然指向旧路径。pytest 的 import 缓存优先命中 `.pyc`，发现路径不匹配就报错跳过。

**解决**: 
1. `_execute_tests` 跑 pytest 前自动遍历测试目录和源码目录，删除所有 `__pycache__/` 子目录
2. 手动清理旧 `generated/test/Untitled/` 和 `generated/src/Untitled*/` 目录

**涉及文件**: `backend/app/services/pipeline_service.py`

**Why:** Python 的 `.pyc` 缓存记录了文件的绝对路径，文件迁移后缓存失效但不会被自动清理。

---

## 问题51: Stage 5 JSON 解析失败导致流水线中断

**现象**: `generate_tests` 报 "LLM returned no valid test files"，Stage 5 FAILED。

**根因（两层）**:
1. `generate_tests`、`adapt_code_to_uml`、`update_tests_incremental` 调用 LLM 时**没有** `json_mode=True`，LLM 可能返回解释文字+JSON 混排
2. `clean_llm_json_response` 只能处理以 ` ``` ` 开头的响应，处理不了文本中间夹 JSON 的情况

**解决**:
1. 三个函数全部加上 `json_mode=True`
2. `clean_llm_json_response` 重写：三层回退 — ` ```json ``` ` 代码块 → ` ``` ``` ` 通用代码块 → 括号配对提取 `{...}`

**涉及文件**: `backend/app/services/code_generator.py`, `backend/app/services/tools.py`

**Why:** `json_mode` 是 DeepSeek 的强制结构化输出开关，不开则 LLM 输出格式不可控。

---

## 问题52: Stage 7 三轮优化完全无改善

**现象**: 3 轮优化后通过率完全不变，失败的用例始终是同样的几个。

**根因**: `_optimize_source_from_tests` 的 prompt 只传了失败行（如 `AttributeError: module does not have 'some_func'`），LLM 看不到测试代码，猜不出缺失函数的签名和语义，只能反复改一些无关代码。

**解决**: prompt 中加入完整测试代码（上限 4000 字符），LLM 能看到测试怎么调用缺失函数，就能正确添加。同时加 `json_mode=True`。

**核心原则**: Stage 7 只改源码、不改测试 — LLM 可以通过测试代码了解 API 期望，但不能修改测试文件。

**涉及文件**: `backend/app/services/pipeline_service.py`

**Why:** 只看报错不看测试，等于蒙着眼睛修代码。

---

## 问题53: Stage 6 误拦截对象级 AttributeError

**现象**: `'CrowTask' object has no attribute 'clear_scheduled_crow'` 被 Stage 6 当做编译错误拦截并尝试修复，但 LLM 修了 2 轮改不好，Stage 6 FAILED 阻断流水线。

**根因**: `_extract_fatal_errors` 的 fatal 关键词包含 `"has no attribute"`，不区分模块级和对象级。模块级（`module 'X' has no attribute`）是编译错误该修；对象级（`'Foo' object has no attribute`）是源码缺方法，应交给 Stage 7。

**解决**: 精炼关键词 — 排除 `' object has no attribute`，保留 `"does not have the attribute"`（模块级）和 `module` 相关模式。

**涉及文件**: `backend/app/services/pipeline_service.py`

**Why:** Stage 6 的职责是"让代码能跑起来"，不是"让代码逻辑正确"。

---

## 问题54: 未选目录时路径回退到旧嵌套结构

**现象**: 用户选 `generated/test` 作为测试目录，但 `generated/test/Untitled/python/` 下又生成了新文件。

**根因（多处）**:
1. `_save_generated_files` 的 Stage 6 保存调用漏了 `target_test_dir` 参数
2. 默认保存路径用了 `generated/{src,test}/{project}/{language}/` 嵌套结构，与用户选择扁平 `generated/{src,test}/` 时不统一

**解决**:
1. 补上漏掉的 `target_test_dir=test_dir` 参数
2. 将默认路径统一为 `generated/src/` 和 `generated/test/`（扁平），去掉 project/language 子目录

**涉及文件**: `backend/app/services/pipeline_service.py`

**Why:** 路径不一致导致文件散落多处，pytest 可能收集不到或收集错误的文件。

---

## 问题55: 目录选择刷新后丢失

**现象**: 每次页面刷新或关闭重开，源码/测试目录都要重新选择。

**根因**: `pipelineSourceDir` 和 `pipelineTestDir` 只存在 Zustand 内存中，刷新即丢失。

**解决**: 默认值从 `localStorage` 读取，setter 同步写入 `localStorage`。目录选择框从"仅空状态可见"改为"非运行状态始终可见"。

**涉及文件**: `frontend/src/stores/uiStore.ts`, `frontend/src/components/PipelineConsole/PipelineConsole.tsx`

**Why:** 开发场景下浏览器经常需要重启，目录选择应该持久化。`localStorage` 是最简单的持久化方案。
