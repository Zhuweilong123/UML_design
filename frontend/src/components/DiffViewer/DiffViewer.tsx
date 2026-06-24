/**
 * Diff Viewer – diff display, canvas toggle, review, continue optimization.
 */

import React, { useEffect, useMemo, useState } from 'react';
import { Empty, Button, message, Tag, Input, Modal } from 'antd';
import {
  CheckCircleOutlined, CloseCircleOutlined,
  SwapOutlined, FileTextOutlined, ReloadOutlined,
} from '@ant-design/icons';
import Editor from '@monaco-editor/react';
import * as Diff from 'diff';
import { useUiStore } from '../../stores/uiStore';
import { useDiagramStore } from '../../stores/diagramStore';
import { saveReview, optimizeUml as apiOptimizeUml } from '../../services/api';
import './DiffViewer.css';

const { TextArea } = Input;

const DiffViewer: React.FC = () => {
  const { setDiagram, diagram } = useDiagramStore();
  const {
    originalCode, optimizedCode, diffContent,
    originalDiagram, optimizedDiagram,
    showingOptimized, toggleShowingVersion,
    setRightPanelTab, setOptimizationResult,
    optimizeInstructions,
  } = useUiStore();

  const [reviewComment, setReviewComment] = useState('');
  const [saving, setSaving] = useState(false);
  const [resolved, setResolved] = useState(false);
  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [rejectInstructions, setRejectInstructions] = useState('');
  const [reoptimizing, setReoptimizing] = useState(false);

  // When new optimization result arrives, reset to fresh state
  useEffect(() => {
    setResolved(false);
    setReviewComment('');
    setSaving(false);
    setReoptimizing(false);
    setRejectModalVisible(false);
  }, [optimizedCode]);

  // Toggle canvas between original and optimized
  const handleToggleCanvas = () => {
    if (showingOptimized) {
      if (originalDiagram) setDiagram(originalDiagram);
    } else {
      if (optimizedDiagram) setDiagram(optimizedDiagram);
    }
    toggleShowingVersion();
  };

  // Accept: show confirmation dialog first
  const handleAcceptClick = () => {
    Modal.confirm({
      title: '确认接受优化',
      content: '接受后画布将更新为优化版本，评审记录将保存到 dev_review.txt。确定接受吗？',
      okText: '确定接受',
      cancelText: '取消',
      onOk: handleAcceptConfirm,
    });
  };

  const handleAcceptConfirm = async () => {
    if (!optimizedDiagram) return;
    setSaving(true);
    try {
      setDiagram(optimizedDiagram);
      await saveReview({
        action: 'accept',
        comment: reviewComment,
        requirements: optimizeInstructions,
        original_name: originalDiagram?.name || '',
        optimized_name: optimizedDiagram.name || '',
        timestamp: new Date().toISOString(),
      });
      message.success('已接受优化结果，评审已保存到 dev_review.txt');
      setResolved(true);
      setRightPanelTab('properties');
    } catch (e) {
      message.error('保存评审失败: ' + String(e));
    }
    setSaving(false);
  };

  // Reject: open dialog with new optimization input
  const handleRejectClick = () => {
    setRejectInstructions('');
    setRejectModalVisible(true);
  };

  const handleCancelReject = () => {
    setRejectModalVisible(false);
  };

  const handleContinueOptimize = async () => {
    if (!originalDiagram) return;
    setReoptimizing(true);
    const dt = originalDiagram?.diagram_type || 'class';
    message.loading({ content: dt === 'sequence' ? 'LLM 正在重新优化时序图...' : 'LLM 正在重新优化 UML...', key: 'reoptimize' });
    try {
      const result = await apiOptimizeUml(originalDiagram, rejectInstructions);
      // Save the reject review first
      await saveReview({
        action: 'reject',
        comment: rejectInstructions || reviewComment || '(继续优化)',
        requirements: optimizeInstructions,
        original_name: originalDiagram.name || '',
        optimized_name: optimizedDiagram?.name || '',
        timestamp: new Date().toISOString(),
      });
      // Update with new optimized result
      setOptimizationResult(result.original, result.optimized, result.changes_summary, rejectInstructions);
      setRejectModalVisible(false);
      setResolved(false); // allow new accept/reject on the fresh result
      setReviewComment('');
      message.success({ content: '重新优化完成，请查看新结果', key: 'reoptimize' });
    } catch (e) {
      message.error({ content: '重新优化失败: ' + String(e), key: 'reoptimize' });
    }
    setReoptimizing(false);
  };

  const handleCancelOptimize = async () => {
    // Just save review and close, no further optimization
    setSaving(true);
    try {
      await saveReview({
        action: 'reject',
        comment: reviewComment,
        requirements: optimizeInstructions,
        original_name: originalDiagram?.name || '',
        optimized_name: optimizedDiagram?.name || '',
        timestamp: new Date().toISOString(),
      });
      if (showingOptimized && originalDiagram) {
        setDiagram(originalDiagram);
        toggleShowingVersion();
      }
      message.info('已拒绝优化结果，评审已保存到 dev_review.txt');
      setResolved(true);
      setRejectModalVisible(false);
      setRightPanelTab('properties');
    } catch (e) {
      message.error('保存评审失败: ' + String(e));
    }
    setSaving(false);
  };

  // Generate unified diff text
  const unifiedDiff = useMemo(() => {
    if (!originalCode || !optimizedCode) return '';
    const origKey = Object.keys(originalCode)[0];
    const optKey = Object.keys(optimizedCode)[0];
    if (!origKey || !optKey) return '';

    const orig = originalCode[origKey] || '';
    const opt = optimizedCode[optKey] || '';

    let origFormatted = orig;
    let optFormatted = opt;
    try {
      origFormatted = JSON.stringify(JSON.parse(orig), null, 2);
      optFormatted = JSON.stringify(JSON.parse(opt), null, 2);
    } catch {}

    const dt = originalDiagram?.diagram_type || 'class';
    const diagramLabel = dt === 'sequence' ? 'Sequence Diagram' : 'UML Diagram';
    return Diff.createPatch(diagramLabel, origFormatted, optFormatted,
      'Original', 'Optimized');
  }, [originalCode, optimizedCode]);

  if (!originalCode || !optimizedCode) {
    return (
      <div className="diff-viewer">
        <Empty description="暂无对比数据" image={Empty.PRESENTED_IMAGE_SIMPLE}>
          <p>使用"优化设计"功能生成设计优化对比</p>
        </Empty>
      </div>
    );
  }

  const buttonsDisabled = resolved && !reoptimizing;

  return (
    <div className="diff-viewer">
      {/* Header with toggle */}
      <div className="diff-header">
        <h3>{originalDiagram?.diagram_type === 'sequence' ? '时序图优化对比' : 'UML 优化对比'}</h3>
        <Button
          icon={<SwapOutlined />}
          size="small"
          type={showingOptimized ? 'primary' : 'default'}
          onClick={handleToggleCanvas}
        >
          {showingOptimized ? '画布: 优化版' : '画布: 原始版'}
        </Button>
      </div>

      {/* Toggle hint */}
      <div className="diff-toggle-hint">
        <Tag color={showingOptimized ? 'blue' : 'default'}>
          当前画布显示: {showingOptimized ? '优化后版本 (可编辑)' : '原始版本'}
        </Tag>
        <span style={{ fontSize: 11, color: '#888' }}>
          点击右侧按钮切换画布上的新旧版本，方便对比
        </span>
      </div>

      {/* Diff summary */}
      {diffContent && (
        <div className="diff-summary">
          <Tag color="blue">变更摘要</Tag>
          <p>{diffContent}</p>
        </div>
      )}

      {/* Diff editor */}
      <div className="diff-editor-wrapper">
        <Editor
          height="100%"
          language="diff"
          value={unifiedDiff}
          theme="vs-dark"
          options={{
            readOnly: true,
            minimap: { enabled: false },
            fontSize: 12,
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            wordWrap: 'on',
            automaticLayout: true,
          }}
        />
      </div>

      {/* Review comments */}
      <div className="diff-review">
        <div className="diff-review-header">
          <FileTextOutlined />
          <span>评审意见</span>
        </div>
        <TextArea
          value={reviewComment}
          onChange={(e) => setReviewComment(e.target.value)}
          placeholder={'输入评审意见...\n例如：\n• 组合关系改得好\n• 需要补充User的validate方法\n• 建议保留原来的Order类名'}
          rows={3}
          disabled={resolved}
        />
      </div>

      {/* Accept / Reject buttons */}
      <div className="diff-actions">
        <Button
          type="primary"
          icon={<CheckCircleOutlined />}
          onClick={handleAcceptClick}
          loading={saving}
          disabled={buttonsDisabled || saving || reoptimizing}
          block
        >
          {resolved ? '已完成评审' : '接受优化（保存评审）'}
        </Button>
        <Button
          danger
          icon={<CloseCircleOutlined />}
          onClick={handleRejectClick}
          loading={false}
          disabled={buttonsDisabled || saving || reoptimizing}
          block
        >
          {resolved ? '已完成评审' : '拒绝优化'}
        </Button>
      </div>
      <div style={{ fontSize: 10, color: '#999', textAlign: 'center', marginTop: 4 }}>
        评审记录将保存在 backend/dev_review.txt
        {resolved && ' | 评审已完成，如需重新优化请点击"优化设计"按钮'}
      </div>

      {/* Reject → Continue Optimize Modal */}
      <Modal
        title="拒绝优化 — 输入新的优化需求"
        open={rejectModalVisible}
        onOk={handleContinueOptimize}
        onCancel={handleCancelOptimize}
        confirmLoading={reoptimizing}
        okText="继续优化"
        cancelText="放弃优化"
        width={550}
        footer={[
          <Button key="cancel" onClick={handleCancelReject}>
            取消
          </Button>,
          <Button
            key="discard"
            danger
            onClick={handleCancelOptimize}
            loading={saving}
          >
            放弃优化
          </Button>,
          <Button
            key="continue"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={handleContinueOptimize}
            loading={reoptimizing}
          >
            继续优化
          </Button>,
        ]}
      >
        <p style={{ marginBottom: 8, color: '#666', fontSize: 13 }}>
          已拒绝当前优化结果。你可以输入新的优化需求让 LLM 重新优化：
        </p>
        <TextArea
          value={rejectInstructions}
          onChange={(e) => setRejectInstructions(e.target.value)}
          placeholder={'输入新的优化需求，如：\n• 请重点优化类的职责划分\n• 改为使用策略模式\n• 补充缺失的getter/setter方法\n...'}
          rows={5}
          autoFocus
        />
        <div style={{ fontSize: 11, color: '#999', marginTop: 6 }}>
          点击"继续优化"将保存本次评审并提交新的优化请求；点击"放弃优化"直接取消。
        </div>
      </Modal>
    </div>
  );
};

export default DiffViewer;
