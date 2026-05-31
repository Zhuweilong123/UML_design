/**
 * Code Viewer – Monaco editor for displaying generated code.
 */

import React, { useCallback } from 'react';
import Editor from '@monaco-editor/react';
import { Tabs, Empty, Button, Tooltip, message } from 'antd';
import { CopyOutlined, DownloadOutlined } from '@ant-design/icons';
import { useUiStore } from '../../stores/uiStore';
import './CodeViewer.css';

const LANGUAGE_MAP: Record<string, string> = {
  py: 'python',
  java: 'java',
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  cs: 'csharp',
  cpp: 'c++',
  hpp: 'c++',
  h: 'c++',
  go: 'go',
  rs: 'rust',
  rb: 'ruby',
  swift: 'swift',
  kt: 'kotlin',
  php: 'php',
  txt: 'plaintext',
};

function detectLanguage(filename: string): string {
  const ext = filename.split('.').pop() || 'txt';
  return LANGUAGE_MAP[ext] || 'plaintext';
}

const CodeViewer: React.FC = () => {
  const {
    generatedCode, activeCodeFile, setActiveCodeFile,
  } = useUiStore();

  const handleCopy = useCallback(() => {
    if (activeCodeFile && generatedCode?.[activeCodeFile]) {
      navigator.clipboard.writeText(generatedCode[activeCodeFile]);
      message.success('已复制到剪贴板');
    }
  }, [activeCodeFile, generatedCode]);

  const handleDownload = useCallback(() => {
    if (activeCodeFile && generatedCode?.[activeCodeFile]) {
      const blob = new Blob([generatedCode[activeCodeFile]], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = activeCodeFile;
      a.click();
      URL.revokeObjectURL(url);
    }
  }, [activeCodeFile, generatedCode]);

  if (!generatedCode || Object.keys(generatedCode).length === 0) {
    return (
      <div className="code-viewer">
        <Empty description="暂无生成的代码" image={Empty.PRESENTED_IMAGE_SIMPLE}>
          <p>使用工具栏中的"生成代码"按钮通过 LLM 生成代码</p>
        </Empty>
      </div>
    );
  }

  const fileNames = Object.keys(generatedCode);

  return (
    <div className="code-viewer">
      <div className="code-viewer-header">
        <span className="code-file-count">{fileNames.length} 个文件 · 已保存至 generated/ 目录</span>
        <div>
          <Tooltip title="复制当前文件">
            <Button size="small" icon={<CopyOutlined />} onClick={handleCopy} />
          </Tooltip>
          <Tooltip title="下载当前文件">
            <Button size="small" icon={<DownloadOutlined />} onClick={handleDownload} />
          </Tooltip>
        </div>
      </div>
      <Tabs
        size="small"
        activeKey={activeCodeFile || fileNames[0]}
        onChange={setActiveCodeFile}
        items={fileNames.map((fname) => ({
          key: fname,
          label: fname,
          children: (
            <div className="code-editor-wrapper">
              <Editor
                height="100%"
                language={detectLanguage(fname)}
                value={generatedCode[fname]}
                theme="vs-dark"
                options={{
                  readOnly: true,
                  minimap: { enabled: false },
                  fontSize: 13,
                  lineNumbers: 'on',
                  scrollBeyondLastLine: false,
                  wordWrap: 'on',
                  automaticLayout: true,
                }}
              />
            </div>
          ),
        }))}
      />
    </div>
  );
};

export default CodeViewer;
