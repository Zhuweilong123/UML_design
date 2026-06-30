"""
ReAct (Reasoning + Acting) Engine for automated code validation & optimization.

Uses DeepSeek native Function Calling (OpenAI-compatible tools parameter)
for reliable tool invocation — replaces the old text-based THOUGHT/ACTION parsing.
"""

import json
import re
import os
import logging
from datetime import datetime
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.llm_service import get_client, chat_with_tools
from app.services.tools import create_tools, create_validation_tools

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Context saver ──────────────────────────────────

def _save_context(messages: list, task_type: str = "") -> str:
    """Save ReAct conversation context to context/ directory."""
    ctx_dir = os.path.abspath(os.path.join(settings.uml_dir, "..", "..", "context"))
    os.makedirs(ctx_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"_{task_type}" if task_type else ""
    filename = f"context{tag}_{ts}.md"
    filepath = os.path.join(ctx_dir, filename)

    lines = [
        f"# ReAct 引擎上下文记录",
        f"",
        f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**任务类型**: {task_type or '通用'}",
        f"**消息总数**: {len(messages)} 条",
        f"",
        f"---",
        f"",
    ]

    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        # Handle tool calls in assistant messages
        tool_calls = msg.get("tool_calls")
        lines.append(f"### [{i+1}] {role.upper()}")
        if content:
            lines.append(f"```\n{str(content)[:3000]}\n```")
        if tool_calls:
            for tc in tool_calls:
                fn = tc.get("function", {})
                lines.append(f"- 🔧 **{fn.get('name', '?')}**")
                lines.append(f"  ```json\n{fn.get('arguments', '')[:1000]}\n  ```")
        lines.append("")

    lines.extend([
        "---",
        f"*Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
    ])

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"[Context] Saved: {filepath}")
    return filepath


# ── Data classes ───────────────────────────────────

@dataclass
class ReActStep:
    round: int
    thought: str = ""
    action: str = ""
    action_input: dict = field(default_factory=dict)
    observation: str = ""
    is_final: bool = False


@dataclass
class ReActResult:
    success: bool
    final_code: dict = field(default_factory=dict)
    summary: str = ""
    steps: list[ReActStep] = field(default_factory=list)
    rounds_used: int = 0
    remaining_issues: str = ""
    messages: list = field(default_factory=list)


def _serialize_steps(steps: list[ReActStep]) -> list[dict]:
    """Convert ReActStep list to JSON-serializable dicts for frontend."""
    return [
        {
            "round": s.round,
            "thought": s.thought,
            "action": s.action,
            "action_input": s.action_input,
            "observation": s.observation[:300] if s.observation else "",
            "is_final": s.is_final,
        }
        for s in steps
    ]


# ── Engine ─────────────────────────────────────────

class ReActEngine:
    """ReAct engine with native Function Calling support (DeepSeek/OpenAI).

    Two modes:
    - ``validation_mode=True``: loads validation tools (syntax check, import
      check, module run) — used in Pipeline Stage 3.
    - ``validation_mode=False``: loads the full tool set including diff and
      simulation — used for general code optimisation.
    """

    def __init__(
        self, max_rounds: int = 5, validation_mode: bool = False,
        max_change_ratio: int = 0,
    ):
        self.client = get_client()
        self.model = settings.deepseek_model
        self.max_rounds = max_rounds
        self.validation_mode = validation_mode
        self.max_change_ratio = max_change_ratio  # 0 = disabled
        self.tools = create_validation_tools() if validation_mode else create_tools()
        self.tool_specs = [t.to_openai_spec() for t in self.tools]
        self.tool_map = {t.name: t for t in self.tools}

    # ── Public API ────────────────────────────────

    async def run_code_validate_and_fix(
        self, language: str, code_files: dict[str, str], task_description: str
    ) -> ReActResult:
        """Validate generated code and fix any errors found.

        Dedicated entry point for Pipeline Stage 3 code quality gate.
        Uses validation tools (syntax check, import check, module run).
        If *max_change_ratio* > 0, also injects a ``check_change_ratio`` tool
        that compares against the original *code_files*.
        """
        # Store snapshot for change-ratio comparison
        self._original_code = {**code_files}

        # Inject check_change_ratio tool if threshold is configured and original exists
        if self.max_change_ratio > 0 and self._original_code:
            from app.services.tools import Tool, _check_change_ratio
            orig = self._original_code
            threshold = self.max_change_ratio
            ratio_tool = Tool(
                name="check_change_ratio",
                description=(
                    f"Compare the current (modified) code against the original baseline. "
                    f"Reports per-file change percentage. Files exceeding {threshold}% "
                    f"change MUST be slimmed down before calling finish_optimization."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "modified": {
                            "type": "object",
                            "description": "Current (possibly modified) filename→content map",
                        },
                    },
                    "required": ["modified"],
                    "additionalProperties": False,
                },
                execute=lambda modified: _check_change_ratio(orig, modified, threshold),
            )
            self.tools = self.tools + [ratio_tool]
            self.tool_specs = [t.to_openai_spec() for t in self.tools]
            self.tool_map = {t.name: t for t in self.tools}

        system = self._build_validation_system_prompt(language)
        user = self._build_validation_user_prompt(language, code_files, task_description)
        return await self._run_loop_with_tools(system, user, code_files, "code_validate")

    async def run_code_validate_and_fix_stream(
        self, language: str, code_files: dict[str, str], task_description: str
    ):
        """Streaming variant — yields progress after each ReAct round.

        Yields:
            ``{"react_steps": [...], "round": N}`` after each round,
            then a final ``{"result": ReActResult}`` on completion.
        """
        # Same setup as run_code_validate_and_fix
        self._original_code = {**code_files}
        if self.max_change_ratio > 0 and self._original_code:
            from app.services.tools import Tool, _check_change_ratio
            orig = self._original_code
            threshold = self.max_change_ratio
            ratio_tool = Tool(
                name="check_change_ratio",
                description=(
                    f"Compare the current (modified) code against the original baseline. "
                    f"Reports per-file change percentage. Files exceeding {threshold}% "
                    f"change MUST be slimmed down before calling finish_optimization."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "modified": {
                            "type": "object",
                            "description": "Current (possibly modified) filename→content map",
                        },
                    },
                    "required": ["modified"],
                    "additionalProperties": False,
                },
                execute=lambda modified: _check_change_ratio(orig, modified, threshold),
            )
            self.tools = self.tools + [ratio_tool]
            self.tool_specs = [t.to_openai_spec() for t in self.tools]
            self.tool_map = {t.name: t for t in self.tools}

        system = self._build_validation_system_prompt(language)
        user = self._build_validation_user_prompt(language, code_files, task_description)

        async for progress in self._run_loop_with_tools_stream(system, user, code_files, "code_validate"):
            yield progress

    async def run_code_generate_and_fix(
        self, language: str, initial_code: dict, task_description: str
    ) -> ReActResult:
        """[DEPRECATED] Legacy code fix entry point using text-based parsing.

        Kept for backward compatibility. New code should use
        ``run_code_validate_and_fix``.
        """
        logger.warning("[ReAct] Using deprecated run_code_generate_and_fix — "
                       "prefer run_code_validate_and_fix with native Function Calling")
        return await self._run_legacy(language, initial_code, task_description,
            self._build_code_fix_prompt, "code_opt")

    async def run_test_generate_and_fix(
        self, language: str, source_code: dict, initial_tests: dict, task_description: str
    ) -> ReActResult:
        """[DEPRECATED] Legacy test fix entry point using text-based parsing."""
        logger.warning("[ReAct] Using deprecated run_test_generate_and_fix")
        prompt = self._build_test_fix_prompt(language, source_code, initial_tests, task_description)
        return await self._run_legacy_with_prompt(language, initial_tests, prompt, "test_fix")

    async def run_source_opt_from_tests(
        self, language: str, source_code: dict, test_results: str, task_description: str
    ) -> ReActResult:
        """[DEPRECATED] Legacy source optimisation entry point."""
        logger.warning("[ReAct] Using deprecated run_source_opt_from_tests")
        prompt = self._build_source_opt_prompt(language, source_code, test_results, task_description)
        return await self._run_legacy_with_prompt(language, source_code, prompt, "src_opt")

    # ── Prompt builders ────────────────────────────

    def _build_validation_system_prompt(self, language: str) -> str:
        """System prompt for Stage 3 code validation mode.

        Guides the LLM to step through validation tools methodically
        and fix any errors before calling finish_optimization.
        When ``max_change_ratio`` > 0, adds a change-limit constraint
        and instructs the LLM to verify with ``check_change_ratio``.
        """
        tool_descs = "\n".join(
            f"- **{t.name}**: {t.description}"
            for t in self.tools
        )
        has_change_limit = self.max_change_ratio > 0

        parts = [
            f"You are an expert {language} code validator using the ReAct (Reasoning + Acting) method.",
            "",
            "Your job is to validate newly generated code files and fix ANY errors you find.",
            "",
            "## Available Tools",
            tool_descs,
            "",
        ]

        if has_change_limit:
            parts.extend([
                f"## Change Limit ({self.max_change_ratio}%)",
                f"This is an EXISTING project — code modifications MUST stay within {self.max_change_ratio}% per file.",
                "",
                "**MANDATORY**: You MUST call **check_change_ratio** before calling finish_optimization —",
                "even if you believe no changes were made. This is a hard requirement, not optional.",
                f"- If any file exceeds {self.max_change_ratio}%, slim down your changes to that specific file",
                "- Only modify what is NECESSARY to fix errors — do not rewrite or restructure working code",
                "- New files (not in the original) are exempt from the limit",
                "- If a validation error genuinely requires a large change, note it in finish_optimization remaining_issues",
                "",
            ])

        parts.extend([
            "## Validation Flow",
            "1. **Batch validation**: call check_imports (covers syntax too) + run_module together",
            "2. If any errors are found, fix ONLY the affected files and re-validate",
        ])
        if has_change_limit:
            parts.append(f"3. call check_change_ratio — if any file > {self.max_change_ratio}%, slim it down and re-check")
            parts.append("4. After all checks pass, call **finish_optimization**")
        else:
            parts.append("3. When ALL validations pass, call **finish_optimization**")

        parts.extend([
            "",
            "## Rules",
            "- Call independent tools TOGETHER in the same round",
            "- Fix ALL errors before finishing — do not skip any",
            "- Preserve the original design intent (class names, method signatures, relationships)",
            "- Only modify files that have errors",
            "- ALWAYS re-validate after making fixes",
            "- Call finish_optimization ONLY when every validation passes",
            "- You have limited rounds — batch tools aggressively",
        ])

        return "\n".join(parts)

    def _build_validation_user_prompt(
        self, language: str, code_files: dict[str, str], task_description: str
    ) -> str:
        """User prompt with the generated code to validate."""
        files_text = "\n\n".join(
            f"### {fname}\n```{language}\n{content}\n```"
            for fname, content in code_files.items()
        )
        # Pick the best main module: prefer files with "app"/"main" in name,
        # fall back to first non-abstract-looking file, then first .py file
        main_module = ""
        py_files = [f for f in code_files if f.endswith(".py") and not f.startswith("test_")]
        for keyword in ("app", "main"):
            for f in py_files:
                if keyword in f.lower():
                    main_module = f.replace(".py", "")
                    break
            if main_module:
                break
        if not main_module:
            for f in py_files:
                content = code_files.get(f, "")
                if "class" in content and "ABC" not in content and "abstract" not in content.lower():
                    main_module = f.replace(".py", "")
                    break
        if not main_module and py_files:
            main_module = py_files[0].replace(".py", "")

        return f"""## Task: {task_description}

## Generated Code to Validate:
{files_text[:8000]}

## Entry Point for run_module
Use **{main_module or 'N/A'}** — the main application module. Call run_module ONCE with this module name.

Start by validating syntax, then check imports, then try running the module.
Fix any problems found, then call finish_optimization.
"""

    def _build_system_prompt(self, language: str, task_type: str) -> str:
        """Legacy system prompt for text-based ReAct mode (kept for backward compat)."""
        tool_descs = "\n".join(
            f"- **{t.name}**: {t.description}\n  Parameters: {json.dumps(t.parameters, ensure_ascii=False)}"
            for t in self.tools
        )
        return f"""You are an expert {language} engineer using the ReAct (Reasoning + Acting) method.

## Available Tools
{tool_descs}

## Response Format
For each step, respond in this exact format:

THOUGHT: <your reasoning about what to do next>
ACTION: <tool_name>
```json
{{"param1": "value1", ...}}
```

Or when finished:

THOUGHT: <summary of what was done>
ACTION: finish_optimization
```json
{{"code_files": {{"file1.py": "content...", ...}}, "summary": "...", "remaining_issues": ""}}
```

CRITICAL: Put EXACTLY ONE action per response. Use ```json blocks for parameters."""

    def _build_code_fix_prompt(self, language: str, code: dict, task: str) -> str:
        files_text = "\n\n".join(f"### {fname}\n```{language}\n{content}\n```" for fname, content in code.items())
        return f"""## Task: {task}

## Current Code:
{files_text}

## Steps
1. Validate syntax of each file
2. Fix any issues found
3. When done, call finish_optimization

Begin ReAct loop now."""

    def _build_test_fix_prompt(self, language: str, source: dict, tests: dict, task: str) -> str:
        src_text = "\n\n".join(f"### {f}\n```{language}\n{c}\n```" for f, c in source.items())
        test_text = "\n\n".join(f"### {f}\n```{language}\n{c}\n```" for f, c in tests.items())
        return f"""## Task: {task}

## Source Code:
{src_text[:2000]}

## Test Code:
{test_text}

Validate and fix tests. Call finish_optimization when done."""

    def _build_source_opt_prompt(self, language: str, source: dict, test_results: str, task: str) -> str:
        src_text = "\n\n".join(f"### {f}\n```{language}\n{c}\n```" for f, c in source.items())
        return f"""## Task: {task}

## Source Code:
{src_text[:3000]}

## Test Results:
{test_results[:2000]}

Fix source code based on failures. Call finish_optimization when done."""

    # ── Core loop: Native Function Calling ─────────

    async def _run_loop_with_tools(
        self, system_prompt: str, user_prompt: str,
        initial_code: dict, task_type: str,
    ) -> ReActResult:
        """Core ReAct loop using native Function Calling (DeepSeek/OpenAI tools).

        The LLM receives tool definitions via the ``tools`` API parameter.
        Tool calls are returned as structured ``tool_calls`` in the response
        — no text parsing needed.
        """
        steps: list[ReActStep] = []
        current_code = initial_code
        # Track whether check_change_ratio was called (server-side guard)
        change_ratio_checked = self.max_change_ratio <= 0

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for round_num in range(1, self.max_rounds + 1):
            step = ReActStep(round=round_num)

            # ── Call LLM with tools ──
            response_msg = None
            for attempt in range(3):
                try:
                    response_msg = await chat_with_tools(
                        messages=messages,
                        tools=self.tool_specs,
                        tool_choice="auto",
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"[ReAct] Retry {attempt+1}/2: {e}")
                        import asyncio
                        await asyncio.sleep(2)
                    else:
                        step.observation = f"API error after 3 attempts: {e}"
                        steps.append(step)
                        return ReActResult(
                            success=False, final_code=current_code,
                            summary=f"API failed after 3 attempts", steps=steps,
                            rounds_used=round_num, messages=messages,
                        )

            if response_msg is None:
                break

            # ── No tool calls: LLM just sent text ──
            if not response_msg.get("tool_calls"):
                thought = (response_msg.get("content") or "")[:500]
                step.thought = thought
                step.observation = "No tool call in response, waiting for next round"
                messages.append({
                    "role": "assistant",
                    "content": response_msg.get("content") or "",
                })
                steps.append(step)
                logger.info(f"[ReAct] Round {round_num}: text-only response, continuing")
                continue

            # ── Process tool calls ──
            tool_calls = response_msg["tool_calls"]
            step.thought = (response_msg.get("content") or "")[:500]

            # Execute EVERY tool call, collect results into one merged step
            tool_results: list[dict] = []
            actions: list[str] = []
            observations: list[str] = []
            finish_triggered = False
            finish_code = current_code
            finish_summary = ""
            finish_remaining = ""

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                actions.append(tool_name)

                # Track check_change_ratio for server-side guard
                if tool_name == "check_change_ratio":
                    change_ratio_checked = True

                # Parse arguments
                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                # Execute tool
                obs = ""
                tool = self.tool_map.get(tool_name)
                if tool:
                    try:
                        result = await tool.run(**tool_args)
                        obs = str(result)[:500]
                    except Exception as e:
                        obs = f"Tool error: {e}"
                else:
                    obs = f"Unknown tool: {tool_name}"

                observations.append(f"[{tool_name}] {obs}")
                tool_results.append({
                    "tool_call_id": tc["id"],
                    "content": obs,
                })

                # ── Check for finish signal ──
                if tool_name in ("finish_optimization", "finish_validation"):
                    finish_triggered = True
                    code = tool_args.get("code_files", current_code)
                    if isinstance(code, str):
                        try:
                            code = json.loads(code)
                        except json.JSONDecodeError:
                            code = current_code
                    finish_code = code if isinstance(code, dict) else current_code
                    finish_summary = tool_args.get("summary", "Done")
                    finish_remaining = tool_args.get("remaining_issues", "")

            # ── Merge into one consolidated ReActStep per round ──
            step.action = ", ".join(actions)
            # Use first tool's args as representative (schema display)
            step.action_input = {}
            try:
                first_args = json.loads(tool_calls[0]["function"]["arguments"])
                step.action_input = first_args if isinstance(first_args, dict) else {}
            except (json.JSONDecodeError, KeyError):
                pass
            step.observation = "\n".join(observations)
            step.is_final = finish_triggered
            steps.append(step)

            # Append ONE assistant message with all tool_calls
            messages.append({
                "role": "assistant",
                "content": response_msg.get("content") or "",
                "tool_calls": tool_calls,
            })
            # Append ONE tool response per tool_call_id
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": tr["content"],
                })

            # ── Server-side guard: enforce check_change_ratio ──
            if finish_triggered and not change_ratio_checked:
                from app.services.tools import _check_change_ratio
                cr_result = await _check_change_ratio(
                    getattr(self, '_original_code', {}), finish_code, self.max_change_ratio,
                )
                cr_data = json.loads(cr_result)

                if cr_data.get("exceeds_threshold"):
                    exceeded = cr_data.get("exceeded_files", [])
                    total_pct = cr_data.get("total_pct", 0)
                    guard_obs = (
                        f"BLOCKED — {len(exceeded)} file(s) exceed {self.max_change_ratio}% "
                        f"limit (total: {total_pct}%): {', '.join(exceeded)}. "
                        f"Slim down changes and re-validate."
                    )
                    observations.append(f"[auto:check_change_ratio] {guard_obs}")
                    step.observation = "\n".join(observations)
                    step.is_final = False
                    finish_triggered = False
                    messages.append({
                        "role": "user",
                        "content": f"⚠️ check_change_ratio failed: {guard_obs}",
                    })
                    logger.info(f"[ReAct] Round {round_num}: finish blocked by change_ratio guard")
                else:
                    change_ratio_checked = True
                    observations.append(
                        f"[auto:check_change_ratio] Passed — {cr_data.get('total_pct', 0)}% "
                        f"within {self.max_change_ratio}% limit"
                    )
                    step.observation = "\n".join(observations)
                    logger.info(f"[ReAct] Round {round_num}: auto check_change_ratio passed")

            # ── Finish if any tool was finish_optimization ──
            if finish_triggered:
                result = ReActResult(
                    success=True,
                    final_code=finish_code,
                    summary=finish_summary,
                    steps=steps,
                    rounds_used=round_num,
                    remaining_issues=finish_remaining,
                    messages=messages,
                )
                _save_context(messages, task_type)
                return result

        # ── Max rounds reached ──
        _save_context(messages, task_type)
        return ReActResult(
            success=False, final_code=current_code,
            summary=f"Incomplete after {self.max_rounds} rounds",
            steps=steps, rounds_used=self.max_rounds, messages=messages,
        )

    async def _run_loop_with_tools_stream(
        self, system_prompt: str, user_prompt: str,
        initial_code: dict, task_type: str,
    ):
        """Streaming variant of ``_run_loop_with_tools``.

        Yields ``{"react_steps": [...], "round": N}`` after every round,
        then ``{"result": ReActResult}`` on completion.
        """
        steps: list[ReActStep] = []
        current_code = initial_code
        change_ratio_checked = self.max_change_ratio <= 0

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for round_num in range(1, self.max_rounds + 1):
            # ── Call LLM with tools ──
            response_msg = None
            for attempt in range(3):
                try:
                    response_msg = await chat_with_tools(
                        messages=messages, tools=self.tool_specs,
                        tool_choice="auto", temperature=0.3, max_tokens=4096,
                    )
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"[ReAct] Retry {attempt+1}/2: {e}")
                        import asyncio
                        await asyncio.sleep(2)
                    else:
                        yield {
                            "react_steps": _serialize_steps(steps),
                            "round": round_num,
                            "result": ReActResult(
                                success=False, final_code=current_code,
                                summary=f"API failed after 3 attempts", steps=steps,
                                rounds_used=round_num, messages=messages,
                            ),
                        }
                        return

            if response_msg is None:
                break

            # ── No tool calls ──
            if not response_msg.get("tool_calls"):
                step = ReActStep(
                    round=round_num,
                    thought=(response_msg.get("content") or "")[:500],
                    observation="No tool call in response, waiting for next round",
                )
                steps.append(step)
                messages.append({
                    "role": "assistant",
                    "content": response_msg.get("content") or "",
                })
                yield {"react_steps": _serialize_steps(steps), "round": round_num}
                continue

            # ── Process tool calls ──
            tool_calls = response_msg["tool_calls"]
            step = ReActStep(
                round=round_num,
                thought=(response_msg.get("content") or "")[:500],
            )
            tool_results: list[dict] = []
            actions: list[str] = []
            observations: list[str] = []
            finish_triggered = False
            finish_code = current_code
            finish_summary = ""
            finish_remaining = ""

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                actions.append(tool_name)
                if tool_name == "check_change_ratio":
                    change_ratio_checked = True

                try:
                    tool_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    tool_args = {}

                obs = ""
                tool = self.tool_map.get(tool_name)
                if tool:
                    try:
                        result = await tool.run(**tool_args)
                        obs = str(result)[:500]
                    except Exception as e:
                        obs = f"Tool error: {e}"
                else:
                    obs = f"Unknown tool: {tool_name}"

                observations.append(f"[{tool_name}] {obs}")
                tool_results.append({"tool_call_id": tc["id"], "content": obs})

                if tool_name in ("finish_optimization", "finish_validation"):
                    finish_triggered = True
                    code = tool_args.get("code_files", current_code)
                    if isinstance(code, str):
                        try:
                            code = json.loads(code)
                        except json.JSONDecodeError:
                            code = current_code
                    finish_code = code if isinstance(code, dict) else current_code
                    finish_summary = tool_args.get("summary", "Done")
                    finish_remaining = tool_args.get("remaining_issues", "")

            # ── Server-side guard: enforce check_change_ratio ──
            if finish_triggered and not change_ratio_checked:
                from app.services.tools import _check_change_ratio
                cr_result = await _check_change_ratio(
                    getattr(self, '_original_code', {}), finish_code, self.max_change_ratio,
                )
                cr_data = json.loads(cr_result)
                if cr_data.get("exceeds_threshold"):
                    exceeded = cr_data.get("exceeded_files", [])
                    total_pct = cr_data.get("total_pct", 0)
                    guard_obs = (
                        f"BLOCKED — {len(exceeded)} file(s) exceed {self.max_change_ratio}% "
                        f"limit (total: {total_pct}%): {', '.join(exceeded)}. "
                        f"Slim down changes and re-validate."
                    )
                    observations.append(f"[auto:check_change_ratio] {guard_obs}")
                    finish_triggered = False
                    messages.append({
                        "role": "user",
                        "content": f"⚠️ check_change_ratio failed: {guard_obs}",
                    })
                else:
                    change_ratio_checked = True
                    observations.append(
                        f"[auto:check_change_ratio] Passed — {cr_data.get('total_pct', 0)}% "
                        f"within {self.max_change_ratio}% limit"
                    )

            # ── Merge step ──
            step.action = ", ".join(actions)
            try:
                first_args = json.loads(tool_calls[0]["function"]["arguments"])
                step.action_input = first_args if isinstance(first_args, dict) else {}
            except (json.JSONDecodeError, KeyError):
                pass
            step.observation = "\n".join(observations)
            step.is_final = finish_triggered
            steps.append(step)

            messages.append({
                "role": "assistant",
                "content": response_msg.get("content") or "",
                "tool_calls": tool_calls,
            })
            for tr in tool_results:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tr["tool_call_id"],
                    "content": tr["content"],
                })

            if finish_triggered:
                result = ReActResult(
                    success=True, final_code=finish_code, summary=finish_summary,
                    steps=steps, rounds_used=round_num, remaining_issues=finish_remaining,
                    messages=messages,
                )
                _save_context(messages, task_type)
                yield {"react_steps": _serialize_steps(steps), "round": round_num, "result": result}
                return
            else:
                yield {"react_steps": _serialize_steps(steps), "round": round_num}

        # Max rounds
        _save_context(messages, task_type)
        yield {
            "react_steps": _serialize_steps(steps),
            "round": self.max_rounds,
            "result": ReActResult(
                success=False, final_code=current_code,
                summary=f"Incomplete after {self.max_rounds} rounds",
                steps=steps, rounds_used=self.max_rounds, messages=messages,
            ),
        }

    # ── Legacy text-parsing loop (backward compat) ──

    async def _run_legacy(
        self, language: str, initial_code: dict, task: str,
        prompt_builder, task_type: str,
    ) -> ReActResult:
        system = self._build_system_prompt(language, task_type)
        user = prompt_builder(language, initial_code, task)
        return await self._run_loop_legacy(system, user, initial_code, task_type)

    async def _run_legacy_with_prompt(
        self, language: str, initial_code: dict, user_prompt: str, task_type: str,
    ) -> ReActResult:
        system = self._build_system_prompt(language, task_type)
        return await self._run_loop_legacy(system, user_prompt, initial_code, task_type)

    async def _run_loop_legacy(
        self, system_prompt: str, user_prompt: str,
        initial_code: dict, task_type: str,
    ) -> ReActResult:
        """Legacy ReAct loop using text-based THOUGHT/ACTION parsing.

        Kept only for backward compatibility with deprecated entry points.
        New code should use ``_run_loop_with_tools``.
        """
        steps: list[ReActStep] = []
        current_code = initial_code

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for round_num in range(1, self.max_rounds + 1):
            step = ReActStep(round=round_num)

            response_text = None
            for attempt in range(3):
                try:
                    resp = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    response_text = resp.choices[0].message.content or ""
                    break
                except Exception as e:
                    if attempt < 2:
                        logger.warning(f"[ReAct] Retry {attempt+1}/2: {e}")
                        import asyncio
                        await asyncio.sleep(2)
                    else:
                        step.observation = f"API error: {e}"
                        steps.append(step)
                        return ReActResult(success=False, final_code=current_code,
                            summary=f"API failed after 3 attempts", steps=steps,
                            rounds_used=round_num, messages=messages)

            if not response_text:
                break

            step.thought = response_text[:500]
            action, action_input = self._parse_action_legacy(response_text)

            if not action:
                extracted = self._extract_code_legacy(response_text, current_code)
                if extracted:
                    result = ReActResult(success=True, final_code=extracted,
                        summary="Extracted from response", steps=steps,
                        rounds_used=round_num, messages=messages)
                    _save_context(messages, task_type)
                    return result
                messages.append({"role": "assistant", "content": response_text})
                step.observation = "No action parsed, continuing"
                steps.append(step)
                continue

            step.action = action
            step.action_input = action_input

            tool = self.tool_map.get(action)
            if tool:
                try:
                    result = await tool.run(**action_input)
                    step.observation = str(result)[:500]
                except Exception as e:
                    step.observation = f"Tool error: {e}"
            else:
                step.observation = f"Unknown action: {action}"

            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"Tool [{action}] result:\n{step.observation}"})

            steps.append(step)

            if action == "finish_optimization":
                step.is_final = True
                code = action_input.get("code_files", current_code)
                if isinstance(code, str):
                    try:
                        code = json.loads(code)
                    except json.JSONDecodeError:
                        code = current_code
                result = ReActResult(
                    success=True,
                    final_code=code if isinstance(code, dict) else current_code,
                    summary=action_input.get("summary", "Done"),
                    steps=steps,
                    rounds_used=round_num,
                    remaining_issues=action_input.get("remaining_issues", ""),
                    messages=messages,
                )
                _save_context(messages, task_type)
                return result

        _save_context(messages, task_type)
        return ReActResult(
            success=False, final_code=current_code,
            summary=f"Incomplete after {self.max_rounds} rounds",
            steps=steps, rounds_used=self.max_rounds, messages=messages,
        )

    # ── Legacy parsing helpers ─────────────────────

    def _parse_action_legacy(self, text: str) -> tuple:
        """Legacy: Parse THOUGHT/ACTION format from LLM response."""
        action_match = re.search(r'ACTION:\s*(\w+)', text, re.IGNORECASE)
        if not action_match:
            return (None, {})

        action = action_match.group(1)

        json_match = re.search(r'```json\s*\n(.*?)\n```', text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\{[\s\S]*\}', text)
        if not json_match:
            return (action, {})

        try:
            params = json.loads(json_match.group(1) if json_match.lastindex else json_match.group(0))
        except json.JSONDecodeError:
            params = {}

        return (action, params if isinstance(params, dict) else {})

    def _extract_code_legacy(self, text: str, fallback: dict) -> dict:
        """Legacy: Extract code files from LLM response."""
        result = {}
        blocks = re.findall(r'###\s*(\S+)\s*\n```(?:\w+)?\n(.*?)```', text, re.DOTALL)
        for fname, code in blocks:
            result[fname.strip()] = code.strip()
        return result or {}
