"""Pipeline API – manage and run the 7-stage automation pipeline."""

import asyncio
import json
import logging
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.models.uml import UmlDiagram
from app.models.pipeline import (
    ConfirmRequest, PipelineState,
)
from pydantic import BaseModel

from app.services.pipeline_service import (
    create_pipeline, get_pipeline, confirm_stage,
    run_pipeline, resume_pipeline, resume_with_instructions,
    stop_pipeline, _is_stopped, _update_stage, _save_pipeline_log,
)
from app.models.pipeline import StageName, StageStatus

logger = logging.getLogger(__name__)


class CreatePipelineBody(BaseModel):
    diagram_id: str
    auto_confirm: bool = False
    diagram: UmlDiagram

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/create")
async def create_pipeline_endpoint(body: CreatePipelineBody):
    """Create a new pipeline for a diagram."""
    state = create_pipeline(body.diagram_id, body.diagram)
    return {"pipeline": state.model_dump()}


@router.get("/{pipeline_id}")
async def get_pipeline_endpoint(pipeline_id: str):
    """Get pipeline state."""
    state = get_pipeline(pipeline_id)
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"pipeline": state.model_dump()}


@router.post("/{pipeline_id}/confirm")
async def confirm_stage_endpoint(pipeline_id: str, req: ConfirmRequest):
    """Confirm or reject a pipeline stage."""
    state = confirm_stage(pipeline_id, req.stage, req.accepted, req.comment)
    return {"pipeline": state.model_dump()}


@router.post("/{pipeline_id}/resume")
async def resume_pipeline_endpoint(
    pipeline_id: str,
    diagram: UmlDiagram,
    language: str = "python",
):
    """Resume pipeline from dev_confirm stage (after user confirms)."""
    state = get_pipeline(pipeline_id)
    if not state:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    results = []
    async for event in resume_pipeline(pipeline_id, diagram, language, auto_confirm=True):
        results.append(event)
    return {"events": results, "pipeline": get_pipeline(pipeline_id).model_dump()}


@router.websocket("/ws/{pipeline_id}")
async def pipeline_websocket(ws: WebSocket, pipeline_id: str):
    """WebSocket endpoint for real-time pipeline progress."""
    await ws.accept()

    # Read diagram from the first message
    data = await ws.receive_text()
    msg = json.loads(data)
    diagram = UmlDiagram(**msg.get("diagram", {}))
    language = msg.get("language", "python")
    auto_confirm = msg.get("auto_confirm", False)

    state = get_pipeline(pipeline_id) or create_pipeline(pipeline_id, diagram)

    # Background task to listen for stop messages
    stop_requested = False

    async def listen_for_commands():
        nonlocal stop_requested
        try:
            while True:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
                msg = json.loads(raw)
                if msg.get("action") == "stop":
                    stop_requested = True
                    stop_pipeline(pipeline_id)
                    await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                    return
                elif msg.get("action") == "confirm":
                    confirm_stage(
                        pipeline_id,
                        msg.get("stage", "dev_confirm"),
                        msg.get("accepted", False),
                        msg.get("comment", ""),
                    )
                    async for resume_event in resume_pipeline(
                        pipeline_id, diagram, language, auto_confirm=True
                    ):
                        if _is_stopped(pipeline_id):
                            await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                            return
                        await ws.send_json(resume_event)
                        if resume_event.get("event") == "request_case_review":
                            await wait_for_case_review()
                            return
                    break
                elif msg.get("action") == "confirm_case_review":
                    pipeline = get_pipeline(pipeline_id)
                    if pipeline:
                        for s in pipeline.stages:
                            if s.name == StageName.CASE_REVIEW:
                                s.status = StageStatus.SUCCESS
                        # Store test case data from frontend for Stage 5
                        test_cases_data = msg.get("test_cases", "")
                        pipeline.stages[3].result = {"test_cases": test_cases_data}
                        await ws.send_json(await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.SUCCESS, "User confirmed"))
                    async for resume_event in resume_pipeline(pipeline_id, diagram, language, auto_confirm=True, skip_case_review=True, skip_code_gen=True):
                        if _is_stopped(pipeline_id):
                            await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                            return
                        await ws.send_json(resume_event)
                    break
        except asyncio.TimeoutError:
            pass
        except WebSocketDisconnect:
            pass

    # Track whether we need instructions
    instructions = ""

    async def wait_for_instructions():
        """Wait for user to provide optimization instructions."""
        nonlocal instructions
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                if msg.get("action") == "stop":
                    stop_pipeline(pipeline_id)
                    await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                    return False
                elif msg.get("action") == "submit_instructions":
                    instructions = msg.get("instructions", "")
                    async for resume_event in resume_with_instructions(
                        pipeline_id, diagram, instructions, language
                    ):
                        if _is_stopped(pipeline_id):
                            await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                            return False
                        await ws.send_json(resume_event)
                        if resume_event.get("stage") == "dev_confirm":
                            return True  # continue to wait_for_confirm
                    return False
                elif msg.get("action") == "skip_instructions":
                    # Skip Stage 1-2, jump to Stage 3-7, handle case_review pause
                    pipeline = get_pipeline(pipeline_id)
                    if pipeline:
                        yield_event = await _update_stage(pipeline, StageName.UML_OPTIMIZE, StageStatus.SKIPPED, "Skipped by user")
                        await ws.send_json(yield_event)
                        yield_event = await _update_stage(pipeline, StageName.DEV_CONFIRM, StageStatus.SUCCESS, "Auto-confirmed (skipped optimization)")
                        await ws.send_json(yield_event)
                        async for resume_event in resume_pipeline(pipeline_id, diagram, language, auto_confirm=True):
                            if _is_stopped(pipeline_id):
                                await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                                return False
                            await ws.send_json(resume_event)
                            # If case_review requested, wait inline
                            if resume_event.get("event") == "request_case_review":
                                await wait_for_case_review()
                                return False
                    return False
        except WebSocketDisconnect:
            return False

    async def wait_for_case_review():
        """Wait for user to confirm case review."""
        try:
            while True:
                raw = await ws.receive_text()
                msg = json.loads(raw)
                if msg.get("action") == "stop":
                    stop_pipeline(pipeline_id)
                    await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                    return
                elif msg.get("action") == "confirm_case_review":
                    # Mark case_review as success, store test cases, and continue
                    pipeline = get_pipeline(pipeline_id)
                    if pipeline:
                        for s in pipeline.stages:
                            if s.name == StageName.CASE_REVIEW:
                                s.status = StageStatus.SUCCESS
                        # Store test case data from frontend for Stage 5
                        tc = msg.get("test_cases", "")
                        logger.info(f"[Pipeline] confirm_case_review received: test_cases length={len(tc)}, preview={tc[:200] if tc else '(EMPTY)'}")
                        pipeline.stages[3].result = {"test_cases": tc}
                        logger.info(f"[Pipeline] Stored test_cases in stages[3].result: {len(tc)} chars")
                        await ws.send_json(await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.SUCCESS, "User confirmed"))
                    # Resume from Stage 5 (Test Gen), skip case review
                    async for resume_event in resume_pipeline(pipeline_id, diagram, language, auto_confirm=True, skip_case_review=True, skip_code_gen=True):
                        if _is_stopped(pipeline_id):
                            await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                            return
                        await ws.send_json(resume_event)
                    return
        except WebSocketDisconnect:
            pass

    try:
        async for event in run_pipeline(pipeline_id, diagram, language, auto_confirm):
            if stop_requested or _is_stopped(pipeline_id):
                await ws.send_json({"event": "stopped", "pipeline_id": pipeline_id})
                break
            await ws.send_json(event)

            # Save incremental log after key stage completions
            if event.get("event") == "stage_update" and event.get("status") in ("success", "failed"):
                stage_name = event.get("stage", "")
                if stage_name in ("code_gen", "test_gen", "test_exec", "code_optimize"):
                    p = get_pipeline(pipeline_id)
                    if p:
                        try:
                            _save_pipeline_log(p, diagram, language)
                        except Exception:
                            pass

            # If waiting for instructions, pause and collect
            if event.get("event") == "request_instructions":
                need_confirm = await wait_for_instructions()
                if need_confirm:
                    await listen_for_commands()
                break

            # If waiting for dev_confirm, start listening for commands
            if event.get("stage") == "dev_confirm" and not auto_confirm:
                await listen_for_commands()
                break

            # If waiting for case_review, wait for user to confirm
            if event.get("event") == "request_case_review":
                await wait_for_case_review()
                break

        # Save pipeline log before completing
        pipeline = get_pipeline(pipeline_id)
        if pipeline:
            try:
                _save_pipeline_log(pipeline, diagram, language)
            except Exception as log_e:
                logger.warning(f"[Pipeline] Failed to save log: {log_e}")

        # Pipeline completed successfully
        await ws.send_json({"event": "pipeline_complete", "pipeline_id": pipeline_id, "message": "流水线执行完成"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await ws.send_json({"event": "error", "error": str(e)})
