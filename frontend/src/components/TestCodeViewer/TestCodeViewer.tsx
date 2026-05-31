/**
 * Test Code Viewer – displays generated test case code (separate from project source).
 */

import React, { useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Tabs, Empty, Button, Tooltip, message } from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import { useUiStore } from '../../stores/uiStore';
import '../CodeViewer/CodeViewer.css';

const LANG_MAP: Record<string, string> = {
  py: 'python', java: 'java', ts: 'typescript', js: 'javascript',
  cs: 'csharp', cpp: 'c++', go: 'go', rs: 'rust', rb: 'ruby',
  swift: 'swift', kt: 'kotlin', php: 'php', txt: 'plaintext',
};

function detectLang(filename: string): string {
  return LANG_MAP[filename.split('.').pop() || 'txt'] || 'plaintext';
}

const TestCodeViewer: React.FC = () => {
  const { generatedTestCode, activeTestFile, setActiveTestFile } = useUiStore();

  const handleCopy = useCallback(() => {
    if (activeTestFile && generatedTestCode?.[activeTestFile]) {
      navigator.clipboard.writeText(generatedTestCode[activeTestFile]);
      message.success('已复制');
    }
  }, [activeTestFile, generatedTestCode]);

  const handleDownload = useCallback(() => {
    if (activeTestFile && generatedTestCode?.[activeTestFile]) {
      const blob = new Blob([generatedTestCode[activeTestFile]], { type: 'text/plain' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = activeTestFile;
      a.click();
    }
  }, [activeTestFile, generatedTestCode]);

  if (!generatedTestCode || Object.keys(generatedTestCode).length === 0) {
    return (
      <div className="code-viewer">
        <Empty description="暂无测试代码" image={Empty.PRESENTED_IMAGE_SIMPLE}>
          <p>在用例检视中点击"全量生成"或"增量生成"</p>
        </Empty>
      </div>
    );
  }

  const files = Object.keys(generatedTestCode);

  return (
    <div className="code-viewer">
      <div className="code-viewer-header">
        <span className="code-file-count">测试 {files.length} 个文件</span>
        <div>
          <Tooltip title="复制"><Button size="small" icon={<CopyOutlined />} onClick={handleCopy} /></Tooltip>
          <Tooltip title="下载"><Button size="small" icon={<DownloadOutlined />} onClick={handleDownload} /></Tooltip>
        </div>
      </div>
      <Tabs
        size="small"
        activeKey={activeTestFile || files[0]}
        onChange={setActiveTestFile}
        items={files.map((f) => ({
          key: f, label: f,
          children: (
            <div className="code-editor-wrapper">
              <Editor height="100%" language={detectLang(f)}
                value={generatedTestCode[f]} theme="vs-dark"
                options={{ readOnly: true, minimap: { enabled: false }, fontSize: 13,
                  lineNumbers: 'on', scrollBeyondLastLine: false, wordWrap: 'on', automaticLayout: true }} />
            </div>
          ),
        }))}
      />
    </div>
  );
};

export default TestCodeViewer;
