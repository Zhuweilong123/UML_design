/**
 * Main App Component – layout with toolbar, canvas, and right panel.
 */

import React, { useCallback } from 'react';
import { Layout, Tabs, Button, Tooltip } from 'antd';
import {
  SettingOutlined, CodeOutlined, PlayCircleOutlined,
  DiffOutlined, CloseOutlined, FileTextOutlined,
} from '@ant-design/icons';
import UMLEditor from './components/Canvas/UMLEditor';
import Toolbar from './components/Toolbar/Toolbar';
import PropertyPanel from './components/PropertyPanel/PropertyPanel';
import CodeViewer from './components/CodeViewer/CodeViewer';
import PipelineConsole from './components/PipelineConsole/PipelineConsole';
import DiffViewer from './components/DiffViewer/DiffViewer';
import TestCaseViewer from './components/TestCaseViewer/TestCaseViewer';
import { useUiStore, type RightPanelTab } from './stores/uiStore';
import './App.css';

const { Sider, Content } = Layout;

const App: React.FC = () => {
  const {
    rightPanelVisible, rightPanelTab, rightPanelWidth,
    setRightPanelTab, setRightPanelWidth, toggleRightPanel,
    codeGenLoading,
  } = useUiStore();

  const handleResize = useCallback((_e: React.MouseEvent, direction: string, ref: HTMLElement) => {
    if (direction === 'left') {
      const handleMove = (moveEvent: MouseEvent) => {
        const newWidth = window.innerWidth - moveEvent.clientX;
        setRightPanelWidth(Math.max(280, Math.min(800, newWidth)));
      };
      const handleUp = () => {
        document.removeEventListener('mousemove', handleMove);
        document.removeEventListener('mouseup', handleUp);
      };
      document.addEventListener('mousemove', handleMove);
      document.addEventListener('mouseup', handleUp);
    }
  }, [setRightPanelWidth]);

  const tabItems = [
    {
      key: 'properties' as RightPanelTab,
      label: (
        <Tooltip title="属性">
          <SettingOutlined />
        </Tooltip>
      ),
      children: <PropertyPanel />,
    },
    {
      key: 'code' as RightPanelTab,
      label: (
        <Tooltip title="代码">
          <CodeOutlined />
        </Tooltip>
      ),
      children: <CodeViewer />,
    },
    {
      key: 'pipeline' as RightPanelTab,
      label: (
        <Tooltip title="流水线">
          <PlayCircleOutlined />
        </Tooltip>
      ),
      children: <PipelineConsole />,
    },
    {
      key: 'diff' as RightPanelTab,
      label: (
        <Tooltip title="对比">
          <DiffOutlined />
        </Tooltip>
      ),
      children: <DiffViewer />,
    },
    {
      key: 'testcase' as RightPanelTab,
      label: (
        <Tooltip title="用例检视">
          <FileTextOutlined />
        </Tooltip>
      ),
      children: <TestCaseViewer />,
    },
  ];

  return (
    <Layout className="app-layout">
      {/* Toolbar */}
      <Toolbar />

      {/* Main Area */}
      <Layout className="app-main">
        <Content className="app-content">
          <UMLEditor />
          {/* Status bar */}
          <div className="status-bar">
            <span>双击画布添加类 | 拖拽端口创建连接 | Ctrl+滚轮缩放 | 空格平移</span>
            <span>Ctrl+Z 撤销 | Ctrl+Y 重做</span>
          </div>
        </Content>

        {/* Resize Handle */}
        {rightPanelVisible && (
          <div
            className="resize-handle"
            onMouseDown={(e) => handleResize(e, 'left', e.currentTarget)}
          />
        )}

        {/* Right Panel */}
        {rightPanelVisible && (
          <div className="right-panel" style={{ width: rightPanelWidth }}>
            <div className="right-panel-tabs">
              <Tabs
                activeKey={rightPanelTab}
                onChange={(key) => setRightPanelTab(key as RightPanelTab)}
                size="small"
                tabBarExtraContent={
                  <Button
                    type="text"
                    size="small"
                    icon={<CloseOutlined />}
                    onClick={toggleRightPanel}
                  />
                }
                items={tabItems}
              />
            </div>
          </div>
        )}
      </Layout>
    </Layout>
  );
};

export default App;
