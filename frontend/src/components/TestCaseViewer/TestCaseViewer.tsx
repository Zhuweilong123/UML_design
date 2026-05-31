/**
 * Test Case Viewer – load Excel test cases, edit, generate test code.
 * Used in pipeline Stage 4 (Case Review).
 */

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  Button, Tabs, Table, Select, message, Space, Tag, Modal, Input,
  Tooltip, Badge, Divider,
} from 'antd';
import {
  ReloadOutlined, CodeOutlined, PlusOutlined,
  SaveOutlined, FileTextOutlined, FileAddOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { loadTestFile, saveTestFile, generateTestCode, saveTestReview, listTestFiles } from '../../services/api';
import { useUiStore } from '../../stores/uiStore';
import './TestCaseViewer.css';

const { TextArea } = Input;

interface SheetData {
  headers: string[];
  rows: Record<string, string>[];
}

const TestCaseViewer: React.FC = () => {
  const { selectedLanguage, setRightPanelTab, setRightPanelVisible } = useUiStore();

  const [files, setFiles] = useState<Array<{ name: string; path: string }>>([]);
  const [currentFile, setCurrentFile] = useState('');
  const [sheets, setSheets] = useState<Record<string, SheetData>>({});
  const [sheetNames, setSheetNames] = useState<string[]>([]);
  const [activeSheet, setActiveSheet] = useState('');
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [changedCases, setChangedCases] = useState<Array<{sheet: string; row: number; case_id: string; field: string; old_val: string; new_val: string}>>([]);
  const [reviewLog, setReviewLog] = useState<string[]>([]);
  const [logVisible, setLogVisible] = useState(false);

  // Editable cell tracking
  const editedCells = useRef<Set<string>>(new Set());

  // Load files list on mount
  useEffect(() => {
    loadFiles();
  }, []);

  const loadFiles = async () => {
    try {
      const result = await listTestFiles();
      setFiles(result.files || []);
      if (result.files?.length && !currentFile) {
        handleLoadFile(result.files[0].name);
      }
    } catch {
      message.error('加载testHub文件列表失败');
    }
  };

  const handleLoadFile = async (filename: string) => {
    setLoading(true);
    try {
      const data = await loadTestFile(filename);
      setCurrentFile(data.filename);
      setSheets(data.sheets as Record<string, SheetData>);
      setSheetNames(data.sheet_names || []);
      setActiveSheet(data.sheet_names?.[0] || '');
      setChangedCases([]);
      addLog('load', `Loaded: ${filename}`, filename);
    } catch {
      message.error('加载测试文件失败');
    }
    setLoading(false);
  };

  const addLog = (action: string, comment: string, filename?: string, sheet?: string, caseId?: string) => {
    const entry = `[${new Date().toLocaleTimeString()}] ${action}: ${comment}`;
    setReviewLog(prev => [...prev.slice(-99), entry]);
    saveTestReview({
      action, comment, filename: filename || currentFile, sheet: sheet || '', case_id: caseId || '', details: '',
    }).catch(() => {});
  };

  // Handle cell edit
  const handleCellEdit = (rowIndex: number, key: string, newValue: string, row: Record<string, any>) => {
    if (!activeSheet || !sheets[activeSheet]) return;

    const oldValue = row[key] || '';
    if (oldValue === newValue) return;

    // Update sheet data
    const updatedSheets = { ...sheets };
    const rows = [...updatedSheets[activeSheet].rows];
    rows[rowIndex] = { ...rows[rowIndex], [key]: newValue };
    updatedSheets[activeSheet] = { ...updatedSheets[activeSheet], rows };
    setSheets(updatedSheets);

    // Track change
    const caseId = row[sheets[activeSheet].headers[0]] || `row_${rowIndex}`;
    setChangedCases(prev => {
      const existing = prev.find(c => c.sheet === activeSheet && c.row === rowIndex && c.field === key);
      if (existing) {
        return prev.map(c => c === existing ? { ...c, new_val: newValue } : c);
      }
      return [...prev, { sheet: activeSheet, row: rowIndex, case_id: caseId, field: key, old_val: oldValue, new_val: newValue }];
    });

    editedCells.current.add(`${activeSheet}_${rowIndex}_${key}`);
    addLog('edit', `${caseId}: ${key} "${oldValue}" → "${newValue}"`, undefined, activeSheet, caseId);
  };

  // Save changes back to Excel
  const handleSave = async () => {
    if (!currentFile) return;
    setLoading(true);
    try {
      await saveTestFile({ filename: currentFile, sheets });
      message.success('测试用例已保存');
      setChangedCases([]);
      addLog('save', `Saved ${changedCases.length} changes to ${currentFile}`);
    } catch {
      message.error('保存失败');
    }
    setLoading(false);
  };

  // Generate test code
  const handleGenerate = async (mode: 'full' | 'incremental') => {
    setGenerating(true);
    const key = 'testgen';
    message.loading({ content: mode === 'full' ? '全量生成测试代码...' : '增量生成测试代码...', key });
    try {
      const result = await generateTestCode({
        filename: currentFile,
        sheets,
        language: selectedLanguage,
        mode,
        changed_cases: mode === 'incremental' ? changedCases : [],
      });
      const store = useUiStore.getState();
      store.setGeneratedCode(result.files);
      store.setRightPanelTab('code');
      store.setRightPanelVisible(true);
      const count = Object.keys(result.files).length;
      message.success({ content: `${mode === 'full' ? '全量' : '增量'}生成了 ${count} 个测试文件`, key });
      addLog(`generate_${mode}`, `Generated ${count} test files (${mode})`);
    } catch (e) {
      message.error({ content: '测试代码生成失败: ' + String(e), key });
    }
    setGenerating(false);
  };

  // Build table columns from headers
  const buildColumns = (headers: string[]) => {
    return headers.map((h, idx) => ({
      title: h,
      dataIndex: h,
      key: h,
      width: idx === 0 ? 130 : idx <= 2 ? 100 : idx >= 4 ? 280 : 150,
      ellipsis: true,
      render: (text: string, record: any, rowIndex: number) => {
        const cellKey = `${activeSheet}_${rowIndex}_${h}`;
        const isEdited = editedCells.current.has(cellKey);

        return (
          <Tooltip title={text || '(空)'}>
            <div
              style={{
                cursor: 'text',
                minHeight: 22,
                background: isEdited ? '#fff7e6' : undefined,
                padding: '2px 4px',
                borderRadius: 2,
              }}
              contentEditable={false}
              onDoubleClick={(e) => {
                const el = e.currentTarget;
                const origText = text;
                el.contentEditable = 'true';
                el.focus();
                const onBlur = () => {
                  el.contentEditable = 'false';
                  const newText = el.textContent || '';
                  if (newText !== origText) {
                    handleCellEdit(rowIndex, h, newText, record as any);
                  }
                  el.removeEventListener('blur', onBlur);
                };
                el.addEventListener('blur', onBlur);
              }}
            >
              {text || <span style={{ color: '#ccc' }}>(空)</span>}
            </div>
          </Tooltip>
        );
      },
    }));
  };

  const currentSheetData = sheets[activeSheet];
  const columns = currentSheetData ? buildColumns(currentSheetData.headers) : [];
  const dataSource: Record<string, unknown>[] = currentSheetData?.rows.map((r, i) => ({ ...r, _key: i })) || [];

  return (
    <div className="testcase-viewer">
      {/* Header */}
      <div className="testcase-header">
        <h3>用例检视</h3>
        <Space>
          <Select
            value={currentFile}
            onChange={handleLoadFile}
            style={{ width: 250 }}
            options={files.map(f => ({ value: f.name, label: f.name }))}
            placeholder="选择测试文件..."
          />
          <Tooltip title="刷新文件列表">
            <Button icon={<ReloadOutlined />} onClick={loadFiles} size="small" />
          </Tooltip>
          <Divider type="vertical" />

          <Badge count={changedCases.length} size="small" offset={[-4, 4]}>
            <Button
              icon={<SaveOutlined />}
              onClick={handleSave}
              disabled={changedCases.length === 0}
              size="small"
              type={changedCases.length > 0 ? 'primary' : 'default'}
            >
              保存修改 ({changedCases.length})
            </Button>
          </Badge>

          <Divider type="vertical" />

          <Tooltip title="全量生成测试代码">
            <Button
              icon={<FileAddOutlined />}
              onClick={() => handleGenerate('full')}
              loading={generating}
              size="small"
              type="primary"
            >
              全量生成
            </Button>
          </Tooltip>
          <Tooltip title="仅针对变更用例增量生成">
            <Button
              icon={<PlusOutlined />}
              onClick={() => handleGenerate('incremental')}
              loading={generating}
              disabled={changedCases.length === 0}
              size="small"
            >
              增量生成
            </Button>
          </Tooltip>

          <Divider type="vertical" />

          <Tooltip title="操作日志">
            <Badge count={reviewLog.length} size="small">
              <Button
                icon={<HistoryOutlined />}
                onClick={() => setLogVisible(true)}
                size="small"
              />
            </Badge>
          </Tooltip>
        </Space>
      </div>

      {/* Sheet tabs */}
      {sheetNames.length > 0 && (
        <Tabs
          activeKey={activeSheet}
          onChange={(key) => {
            setActiveSheet(key);
            addLog('switch_sheet', `Switched to sheet: ${key}`, undefined, key);
          }}
          size="small"
          items={sheetNames.map(name => ({
            key: name,
            label: name,
          }))}
        />
      )}

      {/* Data table */}
      <div className="testcase-table">
        {currentSheetData ? (
          <Table
            columns={columns}
            dataSource={dataSource}
            rowKey="_key"
            size="small"
            scroll={{ x: 900, y: 'calc(100vh - 320px)' }}
            pagination={false}
            loading={loading}
            bordered
          />
        ) : (
          <div className="testcase-empty">
            {loading ? '加载中...' : '选择测试文件以查看用例'}
          </div>
        )}
      </div>

      {/* Changed cases summary */}
      {changedCases.length > 0 && (
        <div className="testcase-changes">
          <h4>变更记录 ({changedCases.length})</h4>
          <div className="changes-list">
            {changedCases.slice(0, 10).map((c, i) => (
              <Tag key={i} color="orange">
                [{c.sheet}] {c.case_id}: {c.field} "{c.old_val}" → "{c.new_val}"
              </Tag>
            ))}
            {changedCases.length > 10 && <Tag>+{changedCases.length - 10} more</Tag>}
          </div>
        </div>
      )}

      {/* Operation log modal */}
      <Modal
        title="操作日志"
        open={logVisible}
        onCancel={() => setLogVisible(false)}
        footer={<Button onClick={() => setLogVisible(false)}>关闭</Button>}
        width={700}
      >
        <div className="review-log-content">
          {reviewLog.map((entry, i) => (
            <div key={i} className="log-entry">{entry}</div>
          ))}
          {reviewLog.length === 0 && <div style={{ color: '#999' }}>暂无操作记录</div>}
        </div>
      </Modal>
    </div>
  );
};

export default TestCaseViewer;
