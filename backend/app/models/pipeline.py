"""Pipeline models – 7-stage automation pipeline."""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageName(str, Enum):
    UML_OPTIMIZE = "uml_optimize"
    DEV_CONFIRM = "dev_confirm"
    CODE_GEN = "code_gen"
    CASE_REVIEW = "case_review"
    TEST_GEN = "test_gen"
    TEST_EXEC = "test_exec"
    CODE_OPTIMIZE = "code_optimize"


STAGE_LABELS: dict[str, str] = {
    "uml_optimize": "1. UML优化",
    "dev_confirm": "2. 开发确认",
    "code_gen": "3. 代码生成",
    "case_review": "4. 用例检视",
    "test_gen": "5. 用例生成与校验",
    "code_optimize": "6. 测试执行与代码优化",
}


class PipelineStage(BaseModel):
    name: StageName
    label: str = ""
    status: StageStatus = StageStatus.PENDING
    result: Optional[dict] = None
    logs: str = ""


class CodeArtifact(BaseModel):
    language: str
    filename: str
    content: str
    version: int = 1


class PipelineState(BaseModel):
    pipeline_id: str
    diagram_id: str
    current_stage: StageName
    stages: list[PipelineStage] = Field(default_factory=list)
    code_artifacts: list[CodeArtifact] = Field(default_factory=list)
    optimization_round: int = 0  # max 3 rounds for code_optimize
    review_log: list[dict] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    pipeline_id: str
    stage: StageName
    accepted: bool
    comment: str = ""
