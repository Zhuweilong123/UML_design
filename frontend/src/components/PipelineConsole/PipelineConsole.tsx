/**
 * Pipeline Console – real-time display and control of the 7-stage pipeline.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Button, Steps, Tag, message, Alert, Space, Progress, Modal, Input,
} from 'antd';
import {
  PlayCircleOutlined, StopOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
  ReloadOutlined, LoadingOutlined,
} from '@ant-design/icons';
import { useDiagramStore } from '../../stores/diagramStore';
import { useUiStore } from '../../stores/uiStore';
import {
  type PipelineState, StageStatus, StageName, STAGE_LABELS,
} from '../../types/pipeline';
import {
  createPipelineWs, confirmStage, getPipeline, createPipeline,
} from '../../services/api';
import './PipelineConsole.css';

const PipelineConsole: React.FC = () => {
  const { diagram } = useDiagramStore();
  const { selectedLanguage, activePipelineId, setActivePipelineId } = useUiStore();

  const [pipeline, setPipeline] = useState<PipelineState | null>(null);
  const [running, setRunning] = useState(false);
  const [wsError, setWsError] = useState<string | null>(null);
  const [currentAction, setCurrentAction] = useState('');
  const [instructionsVisible, setInstructionsVisible] = useState(false);
  const [pipelineInstructions, setPipelineInstructions] = useState('');
  const [completed, setCompleted] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  // Load existing pipeline (only when not running, avoid conflicts)
  useEffect(() => {
    if (activePipelineId && !running) {
      getPipeline(activePipelineId)
        .then(setPipeline)
        .catch(() => { /* Pipeline not created yet, ignore */ });
    }
  }, [activePipelineId, running, setActivePipelineId]);

  // Submit optimization instructions
  const handleSubmitInstructions = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'submit_instructions',
        instructions: pipelineInstructions,
      }));
      setInstructionsVisible(false);
      setCurrentAction('⏳ 1. UML优化: 正在调用DeepSeek...');
    }
  }, [pipelineInstructions]);

  // Skip instructions (skip Stage 1 entirely)
  const handleSkipInstructions = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'skip_instructions',
      }));
      setInstructionsVisible(false);
      setCurrentAction('⏭ 1. UML优化: 已跳过 → 进入代码生成...');
    }
  }, []);

  // Stop pipeline
  const handleStop = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop' }));
      setCurrentAction('正在停止...');
    }
  }, []);

  // Start pipeline
  const handleStart = useCallback(async () => {
    if (!diagram.classes.length) {
      message.warning('请先添加类到图表中');
      return;
    }

    setRunning(true);
    setCompleted(false);
    setWsError(null);
    setCurrentAction('正在创建流水线...');

    try {
      // 1. Create pipeline via REST first
      const created = await createPipeline(diagram.name, diagram);
      const pipeId = created.pipeline_id;
      setActivePipelineId(pipeId);
      setPipeline(created);
      setCurrentAction('正在连接...');

      // 2. Then open WebSocket for real-time updates
      const ws = createPipelineWs(pipeId, diagram, selectedLanguage, false);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.event === 'stage_update') {
          setPipeline(data.data);
          const stageLabel = STAGE_LABELS[data.stage] || data.stage;
          const statusIconMap: Record<string, string> = {
            running: '⏳', success: '✅', failed: '❌', pending: '⏸', skipped: '⏭',
          };
          const statusIcon = statusIconMap[data.status] || '';
          setCurrentAction(`${statusIcon} ${stageLabel}: ${data.logs || data.status}`);

          // When UML optimize succeeds, switch to diff panel
          if (data.stage === 'uml_optimize' && data.status === 'success') {
            const store = useUiStore.getState();
            store.setRightPanelTab('diff');
            store.setRightPanelVisible(true);
          }
          // When Case Review stage starts, switch main canvas to test cases
          if (data.stage === 'case_review' && data.status === 'running') {
            const store = useUiStore.getState();
            store.setShowTestCaseInCanvas(true);
          }
        } else if (data.event === 'request_case_review') {
          setCurrentAction('⏸ 等待检视用例完成...');
        } else if (data.event === 'request_instructions') {
          // Stage 1 needs optimization instructions
          setPipelineInstructions('');
          setInstructionsVisible(true);
          setCurrentAction('⏳ 等待输入优化需求...');
        } else if (data.event === 'pipeline_complete') {
          message.success('流水线全部完成！');
          setRunning(false);
          setCompleted(true);
          setCurrentAction('全部完成');
        } else if (data.event === 'stopped') {
          message.info('流水线已停止');
          setRunning(false);
          setCurrentAction('已停止');
        } else if (data.event === 'error') {
          setWsError(data.error);
          setRunning(false);
          setCurrentAction('错误: ' + data.error);
        }
      };

      ws.onerror = () => {
        setWsError('WebSocket 连接错误');
        setRunning(false);
      };

      ws.onclose = () => {
        setRunning(false);
        // Don't append "(连接关闭)" if pipeline already completed
        setCurrentAction((prev) => {
          if (prev.includes('全部完成') || prev.includes('已停止')) return prev;
          return prev + ' (连接中断)';
        });
      };
    } catch (e) {
      message.error('创建流水线失败: ' + String(e));
      setRunning(false);
      setCurrentAction('');
    }
  }, [diagram, selectedLanguage, activePipelineId, setActivePipelineId]);

  // Confirm case review (Stage 4)
  const handleConfirmCaseReview = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    const testCases = useUiStore.getState().testCaseData;
    wsRef.current.send(JSON.stringify({
      action: 'confirm_case_review',
      test_cases: testCases,
    }));
    setCurrentAction('✅ 用例检视确认，继续流水线...');
  }, []);

  // Confirm stage (Stage 2)
  const handleConfirm = useCallback((accepted: boolean) => {
    if (!pipeline || !wsRef.current) return;
    const currentStage = pipeline.current_stage;
    wsRef.current.send(JSON.stringify({
      action: 'confirm',
      stage: currentStage,
      accepted,
      comment: accepted ? 'Accepted' : 'Rejected',
    }));
    confirmStage(pipeline.pipeline_id, currentStage, accepted).catch(console.error);
  }, [pipeline]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  // ── Render helpers ──────────────────────────────────
  const isWaitingConfirm = pipeline?.stages.some(
    (s) => s.name === StageName.DEV_CONFIRM && s.status === StageStatus.RUNNING
  );

  const isWaitingCaseReview = pipeline?.stages.some(
    (s) => s.name === StageName.CASE_REVIEW && s.status === StageStatus.RUNNING
  );

  const stageItems = (pipeline?.stages || []).map((stage) => {
    let status: 'wait' | 'process' | 'finish' | 'error' = 'wait';
    if (stage.status === StageStatus.RUNNING) status = 'process';
    if (stage.status === StageStatus.SUCCESS) status = 'finish';
    if (stage.status === StageStatus.FAILED) status = 'error';

    return {
      title: (
        <span>
          {stage.label || STAGE_LABELS[stage.name] || stage.name}
          {stage.status === StageStatus.RUNNING && (
            <LoadingOutlined style={{ marginLeft: 8, color: '#1890ff' }} spin />
          )}
        </span>
      ),
      description: stage.logs ? (
        <span className="stage-logs">{stage.logs}</span>
      ) : undefined,
      status,
    };
  });

  const completedStages = pipeline?.stages.filter(
    (s) => s.status === StageStatus.SUCCESS
  ).length || 0;

  const totalStages = pipeline?.stages.length || 7;

  return (
    <div className="pipeline-console">
      <div className="pipeline-header">
        <h3>自动化流水线</h3>
        <Space>
          {!running && !isWaitingConfirm && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleStart}
            >
              启动流水线
            </Button>
          )}
          {(running || isWaitingConfirm) && (
            <Button
              danger
              icon={<StopOutlined />}
              onClick={handleStop}
            >
              停止
            </Button>
          )}
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              setActivePipelineId(null);
              setPipeline(null);
              setCurrentAction('');
              setWsError(null);
            }}
            size="small"
            disabled={running}
          />
        </Space>
      </div>

      {wsError && (
        <Alert message={wsError} type="error" closable style={{ marginBottom: 12 }} />
      )}

      {/* Live action display */}
      {currentAction && (
        <div className="pipeline-live-action">
          <LoadingOutlined spin={running} style={{ marginRight: 8 }} />
          <span>{currentAction}</span>
        </div>
      )}

      {pipeline && (
        <>
          <div className="pipeline-progress">
            <Progress
              percent={completed ? 100 : Math.round((completedStages / totalStages) * 100)}
              size="small"
              status={running ? 'active' : completed ? 'success' : undefined}
            />
            <span className="round-info">
              优化轮次: {pipeline.optimization_round}/3
              {running && (
                <Tag color="processing" style={{ marginLeft: 8 }}>运行中</Tag>
              )}
            </span>
          </div>

          <Steps
            direction="vertical"
            size="small"
            current={completedStages}
            items={stageItems}
          />

          {isWaitingConfirm && (
            <div className="confirm-card">
              <p>LLM 已完成 UML 优化，是否接受优化结果？</p>
              <Space>
                <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => handleConfirm(true)}>接受</Button>
                <Button danger icon={<CloseCircleOutlined />} onClick={() => handleConfirm(false)}>拒绝</Button>
              </Space>
            </div>
          )}

          {isWaitingCaseReview && (
            <div className="confirm-card" style={{ background: '#e6f7ff', borderColor: '#91d5ff' }}>
              <p>请在主画布中检视并修改测试用例，完成后点击确认继续</p>
              <Space>
                <Button type="primary" icon={<CheckCircleOutlined />} onClick={handleConfirmCaseReview}>
                  检视完成，继续
                </Button>
              </Space>
            </div>
          )}

          {pipeline.code_artifacts.length > 0 && (() => {
            const srcFiles = [...new Set(pipeline.code_artifacts.filter(a =>
              !a.filename.startsWith('test_') && !a.filename.startsWith('test')
            ).map(a => a.filename))];
            const testFiles = [...new Set(pipeline.code_artifacts.filter(a =>
              a.filename.startsWith('test_') || a.filename.startsWith('test')
            ).map(a => a.filename))];
            return (
              <div className="artifacts-list">
                <h4>代码产物</h4>
                <div style={{ marginBottom: 8 }}>
                  <strong style={{ fontSize: 12 }}>源代码 ({srcFiles.length})：</strong>
                  <div>{srcFiles.map((f, i) => <Tag key={'s'+i} color="blue">{f}</Tag>)}</div>
                </div>
                <div>
                  <strong style={{ fontSize: 12 }}>测试代码 ({testFiles.length})：</strong>
                  <div>
                    {testFiles.map((f, i) => <Tag key={'t'+i} color="green">{f}</Tag>)}
                    {testFiles.length === 0 && <span style={{color:'#999',fontSize:11}}>待生成</span>}
                  </div>
                </div>
              </div>
            );
          })()}

          {pipeline.review_log.length > 0 && (
            <div className="review-log">
              <h4>Review 日志</h4>
              {pipeline.review_log.map((entry, idx) => (
                <div key={idx} className="review-entry">
                  <Tag color={entry.accepted ? 'green' : 'red'}>
                    {entry.accepted ? '接受' : '拒绝'}
                  </Tag>
                  <span>{STAGE_LABELS[entry.stage] || entry.stage}</span>
                  {entry.comment && <span className="review-comment">: {entry.comment}</span>}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!pipeline && (
        <div className="pipeline-empty">
          <p>点击"启动流水线"开始七阶段自动化流程：</p>
          <ol>
            {Object.entries(STAGE_LABELS).map(([key, label]) => (
              <li key={key}>{label}</li>
            ))}
          </ol>
        </div>
      )}

      {/* ── Optimization Instructions Modal ──────────── */}
      <Modal
        title="UML 优化需求"
        open={instructionsVisible}
        onCancel={handleSkipInstructions}
        onOk={handleSubmitInstructions}
        okText="提交优化"
        cancelText="跳过"
        width={550}
      >
        <p style={{ marginBottom: 8, color: '#666', fontSize: 13 }}>
          当前类图包含 <strong>{diagram.classes.length}</strong> 个类，
          <strong>{diagram.relations.length}</strong> 条关系。
          请输入优化需求（可选）：
        </p>
        <Input.TextArea
          value={pipelineInstructions}
          onChange={(e) => setPipelineInstructions(e.target.value)}
          placeholder={'例如：\n• 将User和Order改为聚合关系\n• 为Payment添加refund方法\n• 提取公共接口IPayable\n• 优化类的职责划分，减少耦合\n...\n留空则进行通用优化'}
          rows={5}
          autoFocus
        />
      </Modal>
    </div>
  );
};

export default PipelineConsole;
