"""Pipeline orchestration service – manages the 7-stage automation pipeline."""

import asyncio
import json
from datetime import datetime
from typing import AsyncIterator

import os
from app.models.uml import UmlDiagram
from app.models.pipeline import (
    PipelineState, PipelineStage, StageName, StageStatus, STAGE_LABELS,
    CodeArtifact,
)
from app.services.llm_service import chat
from app.services.code_generator import (
    generate_code, generate_tests, optimize_uml, fix_code,
)
from app.services.react_engine import ReActEngine, ReActResult
from app.core.config import get_settings


def _save_pipeline_log(pipeline: PipelineState, diagram: UmlDiagram, language: str):
    """Save detailed pipeline run log as a markdown file in pipeline_log/ directory."""
    settings = get_settings()
    log_dir = os.path.abspath(os.path.join(settings.uml_dir, "..", "..", "pipeline_log"))
    os.makedirs(log_dir, exist_ok=True)

    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in diagram.name if c.isalnum() or c in "._- ").strip() or "pipeline"
    filename = f"{ts}_{safe_name}.md"
    filepath = os.path.join(log_dir, filename)

    status_icon = {"pending": "⏸", "running": "⏳", "success": "✅", "failed": "❌", "skipped": "⏭"}

    lines = [
        f"# 流水线运行报告",
        f"",
        f"| 项目 | 详情 |",
        f"|------|------|",
        f"| Pipeline ID | `{pipeline.pipeline_id}` |",
        f"| 项目名称 | {diagram.name} |",
        f"| 目标语言 | {language} |",
        f"| 运行时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |",
        f"| 总阶段数 | {len(pipeline.stages)} |",
        f"| 类数量 | {len(diagram.classes)} |",
        f"| 关系数量 | {len(diagram.relations)} |",
        f"",
        f"---",
        f"",
    ]

    # ── Class & Relation Summary ──
    if diagram.classes:
        lines.append("## UML 设计概览")
        lines.append("")
        lines.append("| 类名 | 构造型 | 属性数 | 方法数 | 备注 |")
        lines.append("|------|--------|--------|--------|------|")
        for c in diagram.classes:
            stereotype = str(c.stereotype).split(".")[-1] if hasattr(c.stereotype, 'value') else str(c.stereotype)
            lines.append(f"| {c.name} | {stereotype} | {len(c.attributes)} | {len(c.methods)} | {c.note or '-'} |")
        lines.append("")
        if diagram.relations:
            lines.append("**关系**:")
            for r in diagram.relations:
                src = next((c.name for c in diagram.classes if c.id == r.source), r.source)
                tgt = next((c.name for c in diagram.classes if c.id == r.target), r.target)
                lines.append(f"- {src} → {tgt}: `{r.type}`")
            lines.append("")

    lines.extend([
        "---",
        "",
        "## 阶段执行结果",
        "",
    ])

    # ── Stage details with rich info ──
    for i, s in enumerate(pipeline.stages, 1):
        icon = status_icon.get(s.status.value, "❓")
        lines.append(f"### Stage {i}: {s.label}")
        lines.append(f"**状态**: {icon} {s.status.value}")
        if s.logs:
            lines.append(f"**摘要**: {s.logs[:200]}")
        lines.append("")

        # Show stage-specific result data
        result = s.result or {}

        if s.name == StageName.CODE_GEN:
            files = result.get("files", [])
            lines.append(f"**生成文件**: {len(files)} 个")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")

        elif s.name == StageName.TEST_GEN:
            files = result.get("test_files", [])
            lines.append(f"**测试文件**: {len(files)} 个")
            for f in files:
                lines.append(f"- `{f}`")
            lines.append("")

        elif s.name == StageName.TEST_EXEC:
            react_steps = result.get("react_steps", [])
            test_results = result.get("test_results", "")
            if react_steps:
                lines.append(f"**ReAct 推理步骤**: {len(react_steps)} 步")
                lines.append("")
                lines.append("| 轮次 | 动作 | 观察结果 |")
                lines.append("|------|------|---------|")
                for step in react_steps:
                    obs = str(step.get("observation", ""))[:100]
                    lines.append(f"| {step.get('round', '-')} | `{step.get('action', '-')}` | {obs} |")
                lines.append("")
            if test_results:
                lines.append("**测试执行结果**:")
                lines.append("```")
                lines.append(str(test_results)[:1000])
                lines.append("```")
                lines.append("")

        elif s.name == StageName.CODE_OPTIMIZE:
            lines.append(f"**总优化轮次**: {pipeline.optimization_round}/3")
            lines.append("")

            # Show each round's detailed results
            rounds = result.get("rounds", [])
            if rounds:
                for rd in rounds:
                    rn = rd.get("round", "?")
                    pr = rd.get("pass_rate", 0)
                    icon = "🎉" if pr == 100 else "⚠️" if pr >= 80 else "❌"
                    lines.append(f"#### Round {rn}: {icon} 通过率 {pr}%")
                    lines.append(f"- 用例: {rd.get('passed', 0)} 通过 / {rd.get('failed', 0)} 失败 / {rd.get('total', 0)} 总计")
                    lines.append(f"- ReAct 摘要: {rd.get('react_summary', '-')[:150]}")
                    if rd.get("remaining_issues"):
                        lines.append(f"- 遗留问题: {rd['remaining_issues'][:150]}")

                    # Show ReAct steps for this round
                    steps = rd.get("react_steps", [])
                    if steps:
                        lines.append("")
                        lines.append("| 步骤 | 动作 | 结果 |")
                        lines.append("|------|------|------|")
                        for st in steps:
                            lines.append(f"| {st.get('round', '-')} | `{st.get('action', '-')}` | {st.get('observation', '-')[:100]} |")

                    # Show quick test result summary
                    tr = rd.get("test_results", "")
                    if tr:
                        # Show only FAIL results
                        fail_lines = [l for l in tr.split("\n") if "FAIL" in l]
                        if fail_lines:
                            lines.append("")
                            lines.append("**失败用例**:")
                            for fl in fail_lines[:5]:
                                lines.append(f"- {fl.strip()[:120]}")

                    lines.append("")

            # Show final comparison table
            if len(rounds) > 1:
                lines.append("#### 优化效果对比")
                lines.append("")
                lines.append("| 轮次 | 通过 | 失败 | 通过率 |")
                lines.append("|------|------|------|--------|")
                for rd in rounds:
                    lines.append(f"| {rd.get('round', '?')} | {rd.get('passed', 0)} | {rd.get('failed', 0)} | {rd.get('pass_rate', 0)}% |")
                lines.append("")

    # ── Code Artifacts ──
    lines.extend([
        "---",
        "",
        "## 代码产物",
        "",
    ])

    src_artifacts = [a for a in pipeline.code_artifacts if a.version == 1]
    test_artifacts = [a for a in pipeline.code_artifacts if a.version == 2]
    opt_artifacts = [a for a in pipeline.code_artifacts if a.version == 3]

    lines.append(f"### 📦 源代码 ({len(src_artifacts)} 文件)")
    for a in src_artifacts:
        lines.append(f"- `{a.filename}` ({len(a.content)} 字符, {a.content.count(chr(10))+1} 行)")
    if not src_artifacts:
        lines.append("- 无")
    lines.append("")

    lines.append(f"### 🧪 测试代码 ({len(test_artifacts)} 文件)")
    for a in test_artifacts:
        lines.append(f"- `{a.filename}` ({len(a.content)} 字符, {a.content.count(chr(10))+1} 行)")
    if not test_artifacts:
        lines.append("- 无")
    lines.append("")

    if opt_artifacts:
        lines.append(f"### 🔧 优化后代码 ({len(opt_artifacts)} 文件)")
        for a in opt_artifacts:
            lines.append(f"- `{a.filename}` ({len(a.content)} 字符)")
        lines.append("")

    # ── Final Test Pass Rate ──
    test_exec_stage = next((s for s in pipeline.stages if s.name == StageName.TEST_EXEC), None)
    if test_exec_stage and test_exec_stage.result:
        test_results_text = test_exec_stage.result.get("test_results", "")
        if test_results_text:
            # Parse pass/fail counts
            import re
            passed = len(re.findall(r'->\s*(?:✅\s*)?PASS', test_results_text, re.IGNORECASE))
            failed = len(re.findall(r'->\s*(?:❌\s*)?FAIL', test_results_text, re.IGNORECASE))
            total = passed + failed
            pass_rate = round(passed / total * 100) if total > 0 else 0

            lines.extend([
                "---",
                "",
                "## 最终测试结果",
                "",
                f"| 指标 | 数值 |",
                f"|------|------|",
                f"| 总用例数 | {total} |",
                f"| 通过 | {passed} |",
                f"| 失败 | {failed} |",
                f"| 通过率 | {pass_rate}% |",
                f"| 优化轮次 | {pipeline.optimization_round}/3 |",
                "",
            ])

            if pass_rate == 100:
                lines.append("🎉 **全部测试用例通过！**")
            elif pass_rate >= 80:
                lines.append(f"⚠️ 通过率 {pass_rate}%，仍有部分失败需人工审查。")
            else:
                lines.append(f"❌ 通过率仅 {pass_rate}%，建议重新审查代码和用例。")
            lines.append("")

    # ── Review Log ──
    if pipeline.review_log:
        lines.extend([
            "---",
            "",
            "## 评审记录",
            "",
        ])
        for entry in pipeline.review_log:
            action = "接受 ✅" if entry.get("accepted") else "拒绝 ❌"
            ts = entry.get("timestamp", "")[:19]
            lines.append(f"| {ts} | {action} | {entry.get('comment', '-')} |")

    lines.extend([
        "",
        "---",
        "",
        f"*Generated by UML Designer at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
    ])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[Pipeline] Log saved: {filepath}")
    return filepath


def _save_generated_files(project_name: str, language: str, src: dict, test: dict = None):
    """Save generated code files to generated/ directory."""
    settings = get_settings()
    base = os.path.abspath(os.path.join(settings.uml_dir, "..", "..", "generated"))
    os.makedirs(base, exist_ok=True)

    result = {"src": [], "test": []}
    # Sanitize project name for filesystem
    safe_name = "".join(c for c in project_name if c.isalnum() or c in "._- ").strip() or "project"

    if src:
        src_dir = os.path.join(base, "src", safe_name, language)
        os.makedirs(src_dir, exist_ok=True)
        for fname, content in src.items():
            fp = os.path.join(src_dir, fname)
            try:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(content)
                result["src"].append(fp.replace("\\", "/"))
                print(f"[Pipeline] Saved source: {fp}")
            except Exception as e:
                print(f"[Pipeline] Failed to save {fp}: {e}")

    if test:
        test_dir = os.path.join(base, "test", safe_name, language)
        os.makedirs(test_dir, exist_ok=True)
        for fname, content in test.items():
            fp = os.path.join(test_dir, fname)
            try:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(content)
                result["test"].append(fp.replace("\\", "/"))
                print(f"[Pipeline] Saved test: {fp}")
            except Exception as e:
                print(f"[Pipeline] Failed to save {fp}: {e}")

    return result

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
        _save_generated_files(diagram.name, language, current_code)
        pipeline.stages[2].logs = f"Saved: generated/src/{diagram.name}/{language}/"
        yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.FAILED, str(e))
        return

    # --- Stage 4: Case Review ---
    yield await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.RUNNING,
                               "请在主画布检视用例，确认后继续")
    # Pause for user to review test cases
    yield {
        "event": "request_case_review",
        "pipeline_id": pipeline_id,
        "stage": StageName.CASE_REVIEW.value,
        "message": "请检视并修改用例，完成后点击确认继续",
    }
    return  # Wait for confirm via WebSocket, then resume

    # --- Stage 5: Test Gen ---
    yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.RUNNING)
    try:
        test_cases_data = (pipeline.stages[3].result or {}).get("test_cases", "") if pipeline.stages[3].result else ""
        print(f"[Pipeline Stage 5] test_cases_data present: {bool(test_cases_data)}, length: {len(test_cases_data) if test_cases_data else 0}")
        test_files = await generate_tests(current_code, language, test_cases_data)
        print(f"[Pipeline] Stage 5: generated {len(test_files)} test files, current artifacts: {len(pipeline.code_artifacts)}")
        for fname, content in test_files.items():
            pipeline.code_artifacts.append(CodeArtifact(
                language=language, filename=fname, content=content, version=2,
            ))
        print(f"[Pipeline] Stage 5: after append, artifacts: {len(pipeline.code_artifacts)}")
        pipeline.stages[4].result = {"test_files": list(test_files.keys())}
        _save_generated_files(diagram.name, language, {}, test_files)
        pipeline.stages[4].logs = f"Saved: generated/test/{diagram.name}/{language}/"
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.FAILED, str(e))

    # --- Stage 6 + Stage 7: ReAct-based test exec + code optimize ---
    async for event in _run_react_code_opt(pipeline, diagram, language, current_code, test_files):
        yield event
    return


async def _run_react_code_opt(
    pipeline: PipelineState,
    diagram: UmlDiagram,
    language: str,
    current_code: dict,
    test_files: dict,
) -> AsyncIterator[dict]:
    """Run ReAct-based test execution + code optimization (Stages 6+7)."""
    react = ReActEngine(max_rounds=5)

    # --- Stage 6: Test Exec with ReAct ---
    yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.RUNNING,
                               "ReAct: Analyzing & fixing tests...")

    # Step 6a: Refine tests via ReAct
    for test_round in range(1, 3):
        yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.RUNNING,
                                   f"ReAct test-fix round {test_round}/2")
        test_result = await react.run_test_generate_and_fix(
            language=language,
            source_code=current_code,
            initial_tests=test_files,
            task_description=f"Validate and fix {language} test code. Check imports, mock setup, assertions, edge cases. Round {test_round}.",
        )
        if test_result.success and test_result.final_code:
            test_files = test_result.final_code
        pipeline.stages[5].result = {
            "react_steps": [{"round": s.round, "thought": s.thought[:200], "action": s.action, "observation": s.observation[:200]} for s in test_result.steps],
        }
        pipeline.stages[5].logs = f"ReAct test-fix complete: {len(test_result.steps)} reasoning steps"
        yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.RUNNING,
                                   f"Test check round {test_round}: {test_result.summary[:100]}")

    # Step 6b: Analyze test results via LLM (simulated execution)
    test_results_text = await _execute_tests(test_files, language)
    pipeline.stages[5].result = {**(pipeline.stages[5].result or {}), "test_results": test_results_text}
    yield await _update_stage(pipeline, StageName.TEST_EXEC, StageStatus.SUCCESS,
                               f"Tests analyzed: {test_results_text[:120]}")

    # --- Stage 7: Code Optimize with ReAct ---
    rounds_history = []
    for round_num in range(1, 4):
        pipeline.optimization_round = round_num
        yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.RUNNING,
                                   f"ReAct code optimization round {round_num}/3")

        react_result = await react.run_source_opt_from_tests(
            language=language,
            source_code=current_code,
            test_results=test_results_text,
            task_description=f"Fix source code based on test failures. Round {round_num}/3.",
        )
        if react_result.success and react_result.final_code:
            current_code = react_result.final_code

        # Save optimized code
        _save_generated_files(diagram.name, language, current_code)

        # ── CRITICAL: Re-verify by running test analysis ──
        new_test_results = await _execute_tests(test_files, language)

        # Parse pass/fail for this round
        import re as _re
        passed = len(_re.findall(r'->\s*PASS', new_test_results, _re.IGNORECASE))
        failed = len(_re.findall(r'->\s*FAIL', new_test_results, _re.IGNORECASE))
        total = passed + failed

        # Record this round's full results
        round_record = {
            "round": round_num,
            "react_steps": [{"round": s.round, "action": s.action, "observation": s.observation[:200]} for s in react_result.steps],
            "react_summary": react_result.summary[:300],
            "test_results": new_test_results[:2000],
            "passed": passed,
            "failed": failed,
            "total": total,
            "pass_rate": round(passed / total * 100) if total > 0 else 0,
            "remaining_issues": react_result.remaining_issues,
        }
        rounds_history.append(round_record)

        # Update stage result with cumulative history
        pipeline.stages[5].result = {**(pipeline.stages[5].result or {}), "test_results": new_test_results}
        pipeline.stages[6].result = {"rounds": rounds_history}

        yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.RUNNING,
                                   f"Re-verify after round {round_num}...")

        # Check if tests ACTUALLY pass now
        if "FAIL" not in new_test_results and "fail" not in new_test_results.lower():
            yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.SUCCESS,
                                       f"All tests pass after round {round_num}")
            break
        else:
            yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.RUNNING,
                                       f"Round {round_num} done, tests still failing, continuing...")

    else:
        # Final re-verify after max rounds
        final_test_results = await _execute_tests(test_files, language)
        pipeline.stages[5].result = {**(pipeline.stages[5].result or {}), "test_results": final_test_results}
        yield await _update_stage(pipeline, StageName.CODE_OPTIMIZE, StageStatus.SUCCESS,
                                   "Max optimization rounds reached")

    # Update pipeline artifacts with final code
    for fname, content in current_code.items():
        found = False
        for a in pipeline.code_artifacts:
            if a.filename == fname and a.version == 1:
                a.content = content
                found = True
                break
        if not found:
            pipeline.code_artifacts.append(CodeArtifact(
                language=language, filename=fname, content=content, version=3,
            ))


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
    skip_case_review: bool = False,
    skip_code_gen: bool = False,
) -> AsyncIterator[dict]:
    """Resume pipeline from the dev_confirm stage or after case review."""
    pipeline = _pipelines.get(pipeline_id)
    if not pipeline:
        raise ValueError(f"Pipeline not found: {pipeline_id}")

    current_code: dict[str, str] = {}
    test_files: dict[str, str] = {}

    if skip_code_gen:
        # Reuse existing source code from artifacts
        current_code = {a.filename: a.content for a in pipeline.code_artifacts if a.version == 1}
        yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.SUCCESS, "Using cached code")
    else:
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
            _save_generated_files(diagram.name, language, current_code)
            pipeline.stages[2].logs = f"Saved: generated/src/{diagram.name}/{language}/"
            yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.SUCCESS)
        except Exception as e:
            yield await _update_stage(pipeline, StageName.CODE_GEN, StageStatus.FAILED, str(e))
            return

    # --- Stage 4: Case Review ---
    if skip_case_review:
        yield await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.SUCCESS, "Skipped")
    else:
        yield await _update_stage(pipeline, StageName.CASE_REVIEW, StageStatus.RUNNING,
                                   "请在主画布检视用例，确认后继续")
        yield {
            "event": "request_case_review",
            "pipeline_id": pipeline_id,
            "stage": StageName.CASE_REVIEW.value,
            "message": "请检视并修改用例，完成后点击确认继续",
        }
        return  # Wait for confirm via WebSocket, then resume

    # --- Stage 5: Test Gen ---
    yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.RUNNING)
    try:
        test_cases_data = (pipeline.stages[3].result or {}).get("test_cases", "") if pipeline.stages[3].result else ""
        print(f"[Pipeline Stage 5] test_cases_data present: {bool(test_cases_data)}, length: {len(test_cases_data) if test_cases_data else 0}")
        test_files = await generate_tests(current_code, language, test_cases_data)
        for fname, content in test_files.items():
            pipeline.code_artifacts.append(CodeArtifact(
                language=language, filename=fname, content=content, version=2,
            ))
        pipeline.stages[4].result = {"test_files": list(test_files.keys())}
        _save_generated_files(diagram.name, language, {}, test_files)
        pipeline.stages[4].logs = f"Saved: generated/test/{diagram.name}/{language}/"
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.SUCCESS)
    except Exception as e:
        yield await _update_stage(pipeline, StageName.TEST_GEN, StageStatus.FAILED, str(e))
        return

    # --- Stage 6 + Stage 7: ReAct-based test exec + code optimize ---
    async for event in _run_react_code_opt(pipeline, diagram, language, current_code, test_files):
        yield event
    return
