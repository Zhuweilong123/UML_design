"""Pipeline orchestration service – manages the 7-stage automation pipeline."""

import asyncio
import json
from datetime import datetime
from typing import AsyncIterator

from app.models.uml import UmlDiagram
from app.models.pipeline import (
    PipelineState, PipelineStage, StageName, StageStatus, STAGE_LABELS,
    CodeArtifact,
)
from app.services.llm_service import chat
from app.services.code_generator import (
    generate_code, generate_tests, optimize_uml, fix_code,
)

# In-memory store (replace with DB in production)
_pipelines: dict[str, PipelineState] = {}
_stopped: set[str] = set()


async def resume_with_instructions(
    pipeline_id: str,
    diagram: UmlDiagram,
    instructions: str,
    language: str = "python",
) -> AsyncIterator[dict]:
    """Resume pipeline from Stage 1 with optimization instructions."""
    async for event in run_pipeline(
        pipeline_id, diagram, language,
        auto_confirm=False, instructions=instructions,
    ):
        yield event


def stop_pipeline(pipeline_id: str):
    """Signal a pipeline to stop."""
    _stopped.add(pipeline_id)


def _is_stopped(pipeline_id: str) -> bool:
    return pipeline_id in _stopped


def create_pipeline(diagram_id: str, diagram: UmlDiagram) -> PipelineState:
    pipeline_id = f"pipe_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{diagram_id[:8]}"
    stages = [
        PipelineStage(name=StageName.UML_OPTIMIZE, label=STAGE_LABELS["uml_optimize"]),
        PipelineStage(name=StageName.DEV_CONFIRM, label=STAGE_LABELS["dev_confirm"]),
        PipelineStage(name=StageName.CODE_GEN, label=STAGE_LABELS["code_gen"]),
        PipelineStage(name=StageName.CASE_REVIEW, label=STAGE_LABELS["case_review"]),
        PipelineStage(name=StageName.TEST_GEN, label=STAGE_LABELS["test_gen"]),
        PipelineStage(name=StageName.TEST_EXEC, label=STAGE_LABELS["test_exec"]),
        PipelineStage(name=StageName.CODE_OPTIMIZE, label=STAGE_LABELS["code_optimize"]),
    ]
    state = PipelineState(
        pipeline_id=pipeline_id,
        diagram_id=diagram_id,
        current_stage=StageName.UML_OPTIMIZE,
        stages=stages,
    )
    _pipelines[pipeline_id] = state
    return state


def get_pipeline(pipeline_id: str) -> PipelineState | None:
    return _pipelines.get(pipeline_id)


def confirm_stage(pipeline_id: str, stage: StageName, accepted: bool, comment: str = "") -> PipelineState:
    """Handle dev confirmation for a stage."""
    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        raise ValueError(f"Pipeline not found: {pipeline_id}")

    pipeline.review_log.append({
        "stage": stage.value,
        "accepted": accepted,
        "comment": comment,
        "timestamp": datetime.now().isoformat(),
    })

    stg = next((s for s in pipeline.stages if s.name == stage), None)
    if stg:
        if accepted:
            stg.status = StageStatus.SUCCESS
        else:
            stg.status = StageStatus.FAILED
            stg.logs = f"Rejected by user: {comment}" if comment else "Rejected by user"

    return pipeline


async def run_pipeline(
    pipeline_id: str,
    diagram: UmlDiagram,
    language: str = "python",
    auto_confirm: bool = False,
    test_cases: list[dict] | None = None,
    instructions: str = "",
) -> AsyncIterator[dict]:
    """Run the 7-stage pipeline, yielding progress updates."""
    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        raise ValueError(f"Pipeline not found: {pipeline_id}")

    optimized_diagram = diagram
    current_code: dict[str, str] = {}
    test_files: dict[str, str] = {}
    test_results = ""

    # --- Stage 1: UML Optimize ---
    if _is_stopped(pipeline_id): return
    yield await _update_stage(pipeline, StageName.UML_OPTIMIZE, StageStatus.RUNNING,
                               "Requesting optimization instructions...")

    # If no instructions provided, yield a request event and wait
    if not instructions:
        yield {
            "event": "request_instructions",
            "pipeline_id": pipeline_id,
            "stage": StageName.UML_OPTIMIZE.value,
            "message": "请输入优化需求（可选留空跳过）",
        }
        return  # Wait for instructions via WebSocket, then resume

    try:
        opt_result = await optimize_uml(diagram, instructions)
        optimized_data = opt_result.get("optimized", diagram.model_dump())
        if isinstance(optimized_data, dict):
            optimized_diagram = UmlDiagram(**optimized_data)
        pipeline.stages[0].result = opt_result
        pipeline.stages[0].logs = opt_result.get("changes_summary", "")
        yield await _update_stage(pipeline, StageName.UML_OPTIMIZE, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.UML_OPTIMIZE, StageStatus.FAILED, str(e))
        if not auto_confirm:
            return

    # --- Stage 2: Dev Confirm ---
    if auto_confirm:
        yield await _update_stage(pipeline, StageName.DEV_CONFIRM, StageStatus.SUCCESS)
    else:
        yield await _update_stage(pipeline, StageName.DEV_CONFIRM, StageStatus.RUNNING,
                                  "Waiting for user confirmation...")
        # In auto mode, we skip; in manual mode, pipeline pauses here
        return  # Wait for confirm_stage() call to resume

    # --- Stage 3: Code Gen ---
    yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.RUNNING)
    try:
        current_code = await generate_code(optimized_diagram, language)
        for fname, content in current_code.items():
            pipeline.code_artifacts.append(CodeArtifact(
                language=language, filename=fname, content=content,
            ))
        pipeline.stages[2].result = {"files": list(current_code.keys())}
        yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.FAILED, str(e))
        return

    # --- Stage 4: Case Review ---
    yield await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.RUNNING)
    try:
        case_count = len(test_cases) if test_cases else 0
        pipeline.stages[3].logs = f"Loaded {case_count} test cases"
        pipeline.stages[3].result = {"case_count": case_count, "cases": test_cases or []}
        yield await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.FAILED, str(e))

    # --- Stage 5: Test Gen ---
    yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.RUNNING)
    try:
        test_files = await generate_tests(current_code, language)
        for fname, content in test_files.items():
            pipeline.code_artifacts.append(CodeArtifact(
                language=language, filename=fname, content=content, version=1,
            ))
        pipeline.stages[4].result = {"test_files": list(test_files.keys())}
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.FAILED, str(e))

    # --- Stage 6: Test Exec ---
    yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.RUNNING)
    try:
        test_results = await _execute_tests(test_files, language)
        pipeline.stages[5].result = {"results": test_results}
        yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.SUCCESS)
    except Exception as e:
        test_results = str(e)
        yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.FAILED, str(e))

    # --- Stage 7: Code Optimize (max 3 rounds) ---
    for round_num in range(1, 4):
        pipeline.optimization_round = round_num
        yield await _update_stage(
            pipeline, StageName.CODE_OPTIMIZE, StageStatus.RUNNING,
            f"Optimization round {round_num}/3",
        )
        try:
            current_code = await fix_code(current_code, test_results, language)
            # Re-run tests
            test_files = await generate_tests(current_code, language)
            test_results = await _execute_tests(test_files, language)
            if "FAIL" not in test_results and "fail" not in test_results.lower():
                yield await _update_stage(
                    pipeline, StageName.CODE_OPTIMIZE, StageStatus.SUCCESS,
                    f"All tests passed after round {round_num}",
                )
                break
            yield await _update_stage(
                pipeline, StageName.CODE_OPTIMIZE, StageStatus.RUNNING,
                f"Round {round_num} complete, still failing tests",
            )
        except Exception as e:
            yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.FAILED, str(e))
            break
    else:
        yield await _update_stage(
            pipeline, StageName.CODE_OPTIMIZE, StageStatus.SUCCESS,
            "Max optimization rounds reached",
        )


async def _update_stage(
    pipeline: PipelineState,
    stage_name: StageName,
    status: StageStatus,
    logs: str = "",
    stopped: bool = False,
) -> dict:
    """Update a pipeline stage and return a progress event."""
    pipeline.current_stage = stage_name
    for stage in pipeline.stages:
        if stage.name == stage_name:
            stage.status = status
            if logs:
                stage.logs = logs
    return {
        "event": "stage_update",
        "pipeline_id": pipeline.pipeline_id,
        "stage": stage_name.value,
        "status": status.value,
        "logs": logs,
        "data": pipeline.model_dump(),
    }


async def _execute_tests(test_files: dict[str, str], language: str) -> str:
    """Simulate test execution (in production: Docker sandbox)."""
    # In a real implementation, this would spin up a Docker container and run tests.
    # For now we ask the LLM to simulate test results.
    test_code = "\n\n".join(
        f"### {fname}\n```\n{content}\n```"
        for fname, content in test_files.items()
    )
    prompt = f"""Analyze the following {language} test code and predict the test execution results.
For each test, indicate PASS or FAIL with a brief reason.
Be realistic – identify likely failures, edge cases, missing imports, etc.

{test_code}

Output format:
```
Test: test_name_1 -> PASS
Test: test_name_2 -> FAIL (reason)
...
Summary: X passed, Y failed
```
"""
    return await chat(prompt, system_prompt="You are a test execution simulator.", temperature=0.3)


async def resume_pipeline(
    pipeline_id: str,
    diagram: UmlDiagram,
    language: str = "python",
    auto_confirm: bool = True,
) -> AsyncIterator[dict]:
    """Resume pipeline from the dev_confirm stage."""
    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        raise ValueError(f"Pipeline not found: {pipeline_id}")

    # Continue from stage 3 onward
    current_code: dict[str, str] = {}
    test_files: dict[str, str] = {}

    # Use optimized diagram if available from stage 1
    opt_result = pipeline.stages[0].result or {}
    optimized_data = opt_result.get("optimized")
    optimized_diagram = UmlDiagram(**optimized_data) if optimized_data else diagram

    # --- Stage 3: Code Gen ---
    yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.RUNNING)
    try:
        current_code = await generate_code(optimized_diagram, language)
        for fname, content in current_code.items():
            pipeline.code_artifacts.append(CodeArtifact(
                language=language, filename=fname, content=content,
            ))
        pipeline.stages[2].result = {"files": list(current_code.keys())}
        yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.FAILED, str(e))
        return

    # --- Stage 4: Case Review ---
    yield await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.SUCCESS)

    # --- Stage 5: Test Gen ---
    yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.RUNNING)
    try:
        test_files = await generate_tests(current_code, language)
        pipeline.stages[4].result = {"test_files": list(test_files.keys())}
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.FAILED, str(e))
        return

    # --- Stage 6: Test Exec ---
    yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.RUNNING)
    try:
        test_results = await _execute_tests(test_files, language)
        pipeline.stages[5].result = {"results": test_results}
        yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.SUCCESS)
    except Exception as e:
        test_results = str(e)
        yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.FAILED, str(e))
        return

    # --- Stage 7: Code Optimize (max 3 rounds) ---
    for round_num in range(1, 4):
        pipeline.optimization_round = round_num
        yield await _update_stage(
            pipeline, StageName.CODE_OPTIMIZE, StageStatus.RUNNING,
            f"Optimization round {round_num}/3",
        )
        try:
            current_code = await fix_code(current_code, test_results, language)
            test_files = await generate_tests(current_code, language)
            test_results = await _execute_tests(test_files, language)
            if "FAIL" not in test_results and "fail" not in test_results.lower():
                yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.SUCCESS)
                break
        except Exception as e:
            yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.FAILED, str(e))
            break
    else:
        yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.SUCCESS)
