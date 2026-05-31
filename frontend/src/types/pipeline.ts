/** Pipeline types – mirrors backend pipeline models */

export enum StageStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  SUCCESS = 'success',
  FAILED = 'failed',
  SKIPPED = 'skipped',
}

export enum StageName {
  UML_OPTIMIZE = 'uml_optimize',
  DEV_CONFIRM = 'dev_confirm',
  CODE_GEN = 'code_gen',
  CASE_REVIEW = 'case_review',
  TEST_GEN = 'test_gen',
  TEST_EXEC = 'test_exec',
  CODE_OPTIMIZE = 'code_optimize',
}

export const STAGE_LABELS: Record<string, string> = {
  uml_optimize: '1. UML优化',
  dev_confirm: '2. 开发确认',
  code_gen: '3. 代码生成',
  case_review: '4. 用例检视',
  test_gen: '5. 测试用例增量生成',
  test_exec: '6. 用例调试执行',
  code_optimize: '7. 代码迭代优化',
};

export interface PipelineStage {
  name: StageName;
  label: string;
  status: StageStatus;
  result?: Record<string, unknown>;
  logs: string;
}

export interface CodeArtifact {
  language: string;
  filename: string;
  content: string;
  version: number;
}

export interface PipelineState {
  pipeline_id: string;
  diagram_id: string;
  current_stage: StageName;
  stages: PipelineStage[];
  code_artifacts: CodeArtifact[];
  optimization_round: number;
  review_log: Array<{
    stage: string;
    accepted: boolean;
    comment: string;
    timestamp: string;
  }>;
}
