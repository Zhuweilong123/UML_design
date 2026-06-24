/**
 * Top Toolbar – file operations, LLM actions, view controls.
 */

import React, { useState, useEffect } from 'react';
import {
  Button, Select, Tooltip, Dropdown, Modal, List, message,
  Divider, Input, Form, Slider,
} from 'antd';
import {
  FileAddOutlined, FolderOpenOutlined, SaveOutlined,
  UndoOutlined, RedoOutlined, CodeOutlined, RobotOutlined,
  FileMarkdownOutlined, SettingOutlined, PlayCircleOutlined,
  ZoomInOutlined, ZoomOutOutlined, ExpandOutlined,
  AppstoreOutlined, EyeInvisibleOutlined,
  PlusSquareOutlined, DownOutlined, TableOutlined,
  ProjectOutlined, ApartmentOutlined, ClockCircleOutlined,
  BlockOutlined,
} from '@ant-design/icons';
import { useDiagramStore } from '../../stores/diagramStore';
import { useUiStore } from '../../stores/uiStore';
import {
  saveDiagram, openDiagram, listDiagrams,
  saveProject, openProject, listProjects,
  exportMarkdown, generateCode as apiGenerateCode,
  optimizeUml as apiOptimizeUml, createPipeline,
  browseDirectory, type BrowseResult,
  saveGeneratedCode,
} from '../../services/api';
import './Toolbar.css';

const { TextArea } = Input;

const LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'java', label: 'Java' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'csharp', label: 'C#' },
  { value: 'cpp', label: 'C++' },
  { value: 'go', label: 'Go' },
  { value: 'rust', label: 'Rust' },
  { value: 'ruby', label: 'Ruby' },
  { value: 'swift', label: 'Swift' },
  { value: 'kotlin', label: 'Kotlin' },
  { value: 'php', label: 'PHP' },
];

const Toolbar: React.FC = () => {
  const {
    diagram, project, isModified, undoStack, redoStack,
    undo, redo, setDiagram, newDiagram: clearDiagram,
    setProject, newProject, setActiveDiagram, addDiagram,
    toggleGrid, setGridSize, setGridColor, setGridThickness,
    setCurrentFilepath, currentFilepath,
  } = useDiagramStore();

  const {
    selectedLanguage,
    setSelectedLanguage, setGeneratedCode, setRightPanelTab,
    setRightPanelVisible, setCodeGenLoading,
    setOptimizationResult,
    setActivePipelineId, fileDialogVisible, setFileDialogVisible,
    showTestCaseInCanvas, toggleTestCaseInCanvas,
  } = useUiStore();

  const [fileList, setFileList] = useState<Array<{
    name: string; path: string; size: number; modified: string;
  }>>([]);

  // ── Save As dialog ──────────────────────────────────
  const [saveAsVisible, setSaveAsVisible] = useState(false);
  const [saveFilename, setSaveFilename] = useState('');
  const [saving, setSaving] = useState(false);

  // ── Optimize dialog ─────────────────────────────────
  const [optimizeVisible, setOptimizeVisible] = useState(false);
  const [optimizeInstructions, setOptimizeInstructions] = useState('');
  const [optimizing, setOptimizing] = useState(false);
  const [gridSettingsVisible, setGridSettingsVisible] = useState(false);

  // ── Ctrl+S global save ──────────────────────────────
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [currentFilepath, project, isModified]); // eslint-disable-line

  // ── File operations ─────────────────────────────────
  const handleNew = () => {
    const doNew = () => {
      newProject();
      message.success('已创建新项目');
    };
    if (isModified) {
      Modal.confirm({
        title: '未保存的更改',
        content: '当前项目有未保存的更改，确定要新建吗？',
        onOk: doNew,
        okText: '确定新建',
        cancelText: '取消',
      });
    } else {
      doNew();
    }
  };

  const [browseData, setBrowseData] = useState<BrowseResult | null>(null);
  const [currentBrowsePath, setCurrentBrowsePath] = useState('');

  const handleOpen = async (path?: string) => {
    setFileDialogVisible(true);
    try {
      const result = await browseDirectory(path || currentBrowsePath || '');
      setBrowseData(result);
      setCurrentBrowsePath(result.current);
    } catch {
      message.error('加载文件列表失败');
    }
  };

  const handleBrowseDir = (dirPath: string) => {
    handleOpen(dirPath);
  };

  const handleBrowseParent = () => {
    if (browseData?.parent) {
      handleOpen(browseData.parent);
    }
  };

  const handleOpenFile = async (path: string, isProject: boolean) => {
    try {
      if (isProject) {
        const proj = await openProject(path);
        setProject(proj);
        setCurrentFilepath(path);
        setFileDialogVisible(false);
        message.success(`项目已打开: ${proj.name} (${proj.diagrams.length} 张图)`);
      } else {
        const d = await openDiagram(path);
        setDiagram(d);
        setCurrentFilepath(path);
        setFileDialogVisible(false);
        message.success('文件已打开');
      }
    } catch {
      message.error('打开文件失败');
    }
  };

  // Quick save (always saves as .umlproj project)
  const handleSave = async () => {
    if (!currentFilepath) {
      openSaveAs();
      return;
    }
    try {
      const result = await saveProject(project, currentFilepath);
      setCurrentFilepath(result.filepath);
      message.success(`项目已保存: ${result.filename}`);
    } catch {
      message.error('保存失败');
    }
  };

  // Open Save As dialog
  const openSaveAs = async () => {
    setSaveFilename(project.name || 'Untitled');
    try {
      const result = await browseDirectory('');
      setBrowseData(result);
      setFileList(result.files || []);
    } catch { /* ignore */ }
    setSaveAsVisible(true);
  };

  const handleSaveAs = async () => {
    setSaving(true);
    try {
      const fname = saveFilename.trim() || project.name || 'Untitled';
      // Always save as project (.umlproj)
      const result = await saveProject(project, fname);
      setCurrentFilepath(result.filepath);
      setSaveAsVisible(false);
      message.success(`项目已保存: ${result.filename}`);
    } catch {
      message.error('保存失败');
    }
    setSaving(false);
  };

  const handleExportMd = async () => {
    try {
      const md = await exportMarkdown(diagram);
      const blob = new Blob([md], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${diagram.name}_design.md`;
      a.click();
      URL.revokeObjectURL(url);
      message.success('Markdown 文档已导出');
    } catch {
      message.error('导出失败');
    }
  };

  // ── LLM operations ──────────────────────────────────
  const handleGenerateCode = async () => {
    const dt = diagram.diagram_type || 'class';
    if (dt !== 'class') {
      message.warning('代码生成目前仅支持类图');
      return;
    }
    setCodeGenLoading(true);
    message.loading({ content: '正在生成代码...', key: 'codegen' });
    try {
      const result = await apiGenerateCode(diagram, selectedLanguage);
      setGeneratedCode(result.files);
      setRightPanelTab('code');
      setRightPanelVisible(true);
      saveGeneratedCode({
        project_name: diagram.name, language: selectedLanguage,
        source_files: result.files, test_files: {},
      }).catch(() => {});
      message.success({ content: `已生成 ${Object.keys(result.files).length} 个文件 → generated/src`, key: 'codegen', duration: 5 });
    } catch (e) {
      message.error({ content: '代码生成失败: ' + String(e), key: 'codegen' });
    }
    setCodeGenLoading(false);
  };

  // Open optimize dialog first, then send to LLM
  const handleOptimizeClick = () => {
    const dt = diagram.diagram_type || 'class';
    const data = dt === 'sequence'
      ? (diagram.lifelines || [])
      : diagram.classes;
    if (!data.length) {
      message.warning(dt === 'sequence' ? '请先添加生命线到时序图中' : '请先添加类到图表中');
      return;
    }
    setOptimizeInstructions('');
    setOptimizeVisible(true);
  };

  const handleOptimizeConfirm = async () => {
    setOptimizing(true);
    const dt = diagram.diagram_type || 'class';
    message.loading({ content: dt === 'sequence' ? 'LLM 正在分析优化时序图...' : 'LLM 正在分析优化 UML...', key: 'optimize' });
    try {
      const result = await apiOptimizeUml(diagram, optimizeInstructions);
      setOptimizationResult(result.original, result.optimized, result.changes_summary, optimizeInstructions);
      setRightPanelTab('diff');
      setRightPanelVisible(true);
      setOptimizeVisible(false);
      message.success({ content: 'UML 优化完成，请在对比面板查看', key: 'optimize' });
    } catch (e) {
      message.error({ content: 'UML 优化失败: ' + String(e), key: 'optimize' });
    }
    setOptimizing(false);
  };

  const handleStartPipeline = async () => {
    if (!diagram.classes.length) {
      message.warning('请先添加类到图表中');
      return;
    }
    try {
      const pipeline = await createPipeline(diagram.name, diagram);
      setActivePipelineId(pipeline.pipeline_id);
      setRightPanelTab('pipeline');
      setRightPanelVisible(true);
      message.info('流水线已创建，请在流水线面板中启动');
    } catch (e) {
      message.error('创建流水线失败: ' + String(e));
    }
  };

  // ── View controls ───────────────────────────────────
  const handleZoomIn = () => useDiagramStore.getState().setZoom(diagram.zoom * 1.2);
  const handleZoomOut = () => useDiagramStore.getState().setZoom(diagram.zoom / 1.2);
  const handleZoomReset = () => useDiagramStore.getState().setZoom(1.0);

  const saveMenuItems = [
    { key: 'save', label: `保存${isModified ? ' ●' : ''}`, onClick: handleSave },
    { key: 'saveas', label: '另存为...', onClick: openSaveAs },
  ];

  return (
    <div className="toolbar">
      <div className="toolbar-left">
        {/* File Ops */}
        <Tooltip title="新建">
          <Button icon={<FileAddOutlined />} onClick={handleNew} />
        </Tooltip>
        <Tooltip title="打开">
          <Button icon={<FolderOpenOutlined />} onClick={() => handleOpen()} />
        </Tooltip>

        <Dropdown menu={{ items: saveMenuItems }} trigger={['click']}>
          <Button icon={<SaveOutlined />}>
            {isModified ? '● ' : ''}保存 <DownOutlined />
          </Button>
        </Dropdown>

        <Divider type="vertical" />

        {/* Diagram tabs — switch between diagrams */}
        {project.diagrams.map((d, i) => {
          const isActive = i === project.active_diagram_index;
          const type = d.diagram_type || 'class';
          const icon = type === 'sequence'
            ? <ClockCircleOutlined />
            : type === 'component'
            ? <BlockOutlined />
            : <ApartmentOutlined />;
          const typeLabel = type === 'sequence' ? '时序图' : type === 'component' ? '组件图' : '类图';
          // Only show custom name if user explicitly renamed it (not auto-generated pattern)
          const isAutoName = !d.name || d.name === 'Untitled' || /^(class|sequence|component)_\d+$/.test(d.name);
          const label = isAutoName ? typeLabel : d.name;
          const tip = isAutoName ? `${typeLabel}（${d.name}）` : `${d.name}（${typeLabel}）`;
          return (
            <Tooltip key={i} title={tip}>
              <Button
                type={isActive ? 'primary' : 'default'}
                icon={icon}
                onClick={() => setActiveDiagram(i)}
                style={{ marginRight: 2 }}
              >
                {label}
              </Button>
            </Tooltip>
          );
        })}

        <Tooltip title="添加新图">
          <Dropdown menu={{
            items: [
              { key: 'class', label: '添加类图', icon: <ApartmentOutlined />,
                onClick: () => addDiagram('class') },
              { key: 'sequence', label: '添加时序图', icon: <ClockCircleOutlined />,
                onClick: () => addDiagram('sequence') },
              { key: 'component', label: '添加组件图', icon: <BlockOutlined />,
                onClick: () => addDiagram('component') },
            ],
          }} trigger={['click']}>
            <Button icon={<PlusSquareOutlined />} />
          </Dropdown>
        </Tooltip>

        <Divider type="vertical" />

        {/* Undo/Redo */}
        <Tooltip title="撤销 Ctrl+Z">
          <Button icon={<UndoOutlined />} disabled={undoStack.length === 0} onClick={undo} />
        </Tooltip>
        <Tooltip title="重做 Ctrl+Y">
          <Button icon={<RedoOutlined />} disabled={redoStack.length === 0} onClick={redo} />
        </Tooltip>

        <Divider type="vertical" />

        {/* LLM */}
        <Select
          value={selectedLanguage}
          onChange={setSelectedLanguage}
          style={{ width: 110 }}
          options={LANGUAGES}
          size="small"
        />
        <Tooltip title="LLM 生成代码">
          <Button icon={<CodeOutlined />} onClick={handleGenerateCode}>
            生成代码
          </Button>
        </Tooltip>
        <Tooltip title="LLM 优化 UML 设计 (会弹窗收集需求)">
          <Button icon={<RobotOutlined />} onClick={handleOptimizeClick}>
            优化设计
          </Button>
        </Tooltip>
        <Tooltip title="启动自动化流水线">
          <Button icon={<PlayCircleOutlined />} onClick={handleStartPipeline}>
            流水线
          </Button>
        </Tooltip>

        <Divider type="vertical" />

        {/* Export */}
        <Tooltip title="导出 Markdown 设计文档">
          <Button icon={<FileMarkdownOutlined />} onClick={handleExportMd}>
            导出MD
          </Button>
        </Tooltip>
      </div>

      <div className="toolbar-right">
        <Tooltip title="显示/隐藏网格">
          <Button
            icon={diagram.grid_visible ? <AppstoreOutlined /> : <EyeInvisibleOutlined />}
            onClick={toggleGrid}
          />
        </Tooltip>

        <Tooltip title="网格设置">
          <Button
            icon={<SettingOutlined />}
            onClick={() => setGridSettingsVisible(true)}
          >
            {diagram.grid_size}px
          </Button>
        </Tooltip>

        <Divider type="vertical" />

        <Divider type="vertical" />

        <Tooltip title={showTestCaseInCanvas ? '返回UML画布' : '用例检视'}>
          <Button
            icon={<TableOutlined />}
            type={showTestCaseInCanvas ? 'primary' : 'default'}
            onClick={toggleTestCaseInCanvas}
          >
            用例
          </Button>
        </Tooltip>

        <Tooltip title="缩小">
          <Button icon={<ZoomOutOutlined />} onClick={handleZoomOut} />
        </Tooltip>
        <span className="zoom-label">{Math.round(diagram.zoom * 100)}%</span>
        <Tooltip title="放大">
          <Button icon={<ZoomInOutlined />} onClick={handleZoomIn} />
        </Tooltip>
        <Tooltip title="重置缩放">
          <Button icon={<ExpandOutlined />} onClick={handleZoomReset} />
        </Tooltip>
      </div>

      {/* ── File Open Dialog with folder browsing ────── */}
      <Modal
        title="打开 UML 文件"
        open={fileDialogVisible}
        onCancel={() => setFileDialogVisible(false)}
        footer={null}
        width={600}
      >
        {/* Breadcrumb / navigation */}
        <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Button size="small" onClick={handleBrowseParent}
            disabled={!browseData?.parent}>
            上级目录
          </Button>
          <span style={{ fontSize: 12, color: '#666', wordBreak: 'break-all' }}>
            {browseData?.current || ''}
          </span>
        </div>

        <List
          loading={false}
          locale={{ emptyText: '暂无保存的文件' }}
          size="small"
          style={{ maxHeight: 400, overflow: 'auto' }}
        >
          {/* Directories first */}
          {browseData?.dirs?.map((dir) => (
            <List.Item
              key={dir.path}
              onClick={() => handleBrowseDir(dir.path)}
              style={{ cursor: 'pointer', background: '#fafafa' }}
            >
              <List.Item.Meta
                avatar={<FolderOpenOutlined style={{ fontSize: 18, color: '#faad14' }} />}
                title={<span style={{ fontSize: 13 }}>📁 {dir.name}</span>}
              />
            </List.Item>
          ))}
          {/* Project files (.umlproj) — shown first */}
          {browseData?.files?.filter(f => f.type === 'project').map((item) => (
            <List.Item
              key={item.path}
              onClick={() => handleOpenFile(item.path, true)}
              style={{ cursor: 'pointer', background: '#f0f5ff' }}
            >
              <List.Item.Meta
                avatar={<ProjectOutlined style={{ fontSize: 18, color: '#1890ff' }} />}
                title={<span style={{ fontSize: 13 }}>📦 {item.name}</span>}
                description={
                  <span style={{ fontSize: 11 }}>
                    {new Date(item.modified).toLocaleString()} | {(item.size / 1024).toFixed(1)} KB
                  </span>
                }
              />
            </List.Item>
          ))}
          {/* Single diagram files (.uml) */}
          {browseData?.files?.filter(f => f.type !== 'project').map((item) => (
            <List.Item
              key={item.path}
              onClick={() => handleOpenFile(item.path, false)}
              style={{ cursor: 'pointer' }}
            >
              <List.Item.Meta
                title={<span style={{ fontSize: 13 }}>📄 {item.name}</span>}
                description={
                  <span style={{ fontSize: 11 }}>
                    {new Date(item.modified).toLocaleString()} | {(item.size / 1024).toFixed(1)} KB
                  </span>
                }
              />
            </List.Item>
          ))}
        </List>
      </Modal>

      {/* ── Save As Dialog ───────────────────────────── */}
      <Modal
        title="另存为"
        open={saveAsVisible}
        onCancel={() => setSaveAsVisible(false)}
        onOk={handleSaveAs}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        width={550}
      >
        <Form layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="文件名 (.umlproj)">
            <Input
              value={saveFilename}
              onChange={(e) => setSaveFilename(e.target.value)}
              suffix=".umlproj"
              placeholder="输入项目名称..."
              autoFocus
            />
          </Form.Item>
        </Form>

        <Divider orientation="left" plain style={{ fontSize: 12 }}>
          已有项目文件（保存在 {currentFilepath || 'uml_files/'}）
        </Divider>

        <List
          loading={false}
          dataSource={fileList.slice(0, 8)}
          locale={{ emptyText: '暂无已保存的项目' }}
          size="small"
          renderItem={(item) => (
            <List.Item
              onClick={() => setSaveFilename(item.name.replace('.umlproj', '').replace('.uml', ''))}
              style={{ cursor: 'pointer' }}
            >
              <List.Item.Meta
                title={<span style={{ fontSize: 12 }}>{item.name}</span>}
                description={
                  <span style={{ fontSize: 11 }}>
                    {new Date(item.modified).toLocaleString()} | {(item.size / 1024).toFixed(1)} KB
                  </span>
                }
              />
            </List.Item>
          )}
        />
      </Modal>

      {/* ── Optimize UML Dialog ──────────────────────── */}
      <Modal
        title={diagram.diagram_type === 'sequence' ? '时序图优化' : 'UML 设计优化'}
        open={optimizeVisible}
        onCancel={() => setOptimizeVisible(false)}
        onOk={handleOptimizeConfirm}
        confirmLoading={optimizing}
        okText="提交优化"
        cancelText="取消"
        width={600}
      >
        <p style={{ marginBottom: 8, color: '#666', fontSize: 13 }}>
          {diagram.diagram_type === 'sequence'
            ? <>当前时序图包含 <strong>{(diagram.lifelines || []).length}</strong> 个生命线，<strong>{(diagram.messages || []).length}</strong> 条消息。</>
            : <>当前类图包含 <strong>{diagram.classes.length}</strong> 个类，<strong>{diagram.relations.length}</strong> 条关系。</>
          }
          请输入你的优化需求，LLM 将结合当前设计和你的需求进行优化：
        </p>
        <TextArea
          value={optimizeInstructions}
          onChange={(e) => setOptimizeInstructions(e.target.value)}
          placeholder={diagram.diagram_type === 'sequence'
            ? '例如：\n• 为OtaTask和CrowTask之间增加异常处理消息\n• 补充缺失的返回消息\n• 调整消息调用顺序使其更合理\n• 为关键消息添加功能备注\n...'
            : '例如：\n• 将User和Order改为聚合关系\n• 为Payment添加refund方法\n• 提取公共接口IPayable\n• 优化类的职责划分，减少耦合\n• 应用工厂模式改造创建逻辑\n...'}
          rows={6}
          autoFocus
        />
      </Modal>

      {/* ── Grid Settings Modal ──────────────────────── */}
      <Modal
        title="网格设置"
        open={gridSettingsVisible}
        onCancel={() => setGridSettingsVisible(false)}
        onOk={() => setGridSettingsVisible(false)}
        okText="确定"
        cancelText="取消"
        width={420}
      >
        <Form layout="vertical" style={{ marginTop: 12 }}>
          <Form.Item label="网格大小">
            <Select
              value={diagram.grid_size}
              onChange={(v) => setGridSize(v)}
              options={[
                { value: 5, label: '5px' },
                { value: 10, label: '10px' },
                { value: 20, label: '20px' },
                { value: 50, label: '50px' },
              ]}
            />
          </Form.Item>

          <Form.Item label="线条颜色">
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="color"
                value={diagram.grid_color || '#e0e0e0'}
                onChange={(e) => setGridColor(e.target.value)}
                style={{ width: 40, height: 32, border: '1px solid #d9d9d9', borderRadius: 4, cursor: 'pointer' }}
              />
              <Input
                value={diagram.grid_color || '#e0e0e0'}
                onChange={(e) => setGridColor(e.target.value)}
                style={{ width: 100 }}
                placeholder="#e0e0e0"
              />
              <span style={{ fontSize: 12, color: '#888' }}>选择或输入颜色</span>
            </div>
          </Form.Item>

          <Form.Item label="线条粗细">
            <Slider
              min={1}
              max={5}
              value={diagram.grid_thickness || 1}
              onChange={(v) => setGridThickness(v)}
              marks={{ 1: '细', 3: '中', 5: '粗' }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Toolbar;
