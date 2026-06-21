"""
ReAct (Reasoning + Acting) Engine for automated code optimization.
Uses text-based tool calling (compatible with all LLMs including DeepSeek).
"""

import json
import re
import os
import logging
from datetime import datetime
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.tools import create_tools, Tool

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
        lines.append(f"### [{i+1}] {role.upper()}")
        lines.append(f"```\n{content[:3000]}\n```")
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


# ── Engine ─────────────────────────────────────────

class ReActEngine:

    def __init__(self, max_rounds: int = 5):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.model = settings.deepseek_model
        self.max_rounds = max_rounds
        self.tools = create_tools()

    # ── Public API ────────────────────────────────

    async def run_code_generate_and_fix(self, language: str, initial_code: dict, task_description: str) -> ReActResult:
        return await self._run(language, initial_code, task_description,
            self._build_code_fix_prompt, "code_opt")

    async def run_test_generate_and_fix(self, language: str, source_code: dict, initial_tests: dict, task_description: str) -> ReActResult:
        prompt = self._build_test_fix_prompt(language, source_code, initial_tests, task_description)
        return await self._run_with_prompt(language, initial_tests, prompt, "test_fix")

    async def run_source_opt_from_tests(self, language: str, source_code: dict, test_results: str, task_description: str) -> ReActResult:
        prompt = self._build_source_opt_prompt(language, source_code, test_results, task_description)
        return await self._run_with_prompt(language, source_code, prompt, "src_opt")

    # ── Prompt builders ────────────────────────────

    def _build_system_prompt(self, language: str, task_type: str) -> str:
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

    # ── Core loop ──────────────────────────────────

    async def _run(self, language: str, initial_code: dict, task: str, prompt_builder, task_type: str) -> ReActResult:
        system = self._build_system_prompt(language, task_type)
        user = prompt_builder(language, initial_code, task)
        return await self._run_loop(system, user, initial_code, task_type)

    async def _run_with_prompt(self, language: str, initial_code: dict, user_prompt: str, task_type: str) -> ReActResult:
        system = self._build_system_prompt(language, task_type)
        return await self._run_loop(system, user_prompt, initial_code, task_type)

    async def _run_loop(self, system_prompt: str, user_prompt: str, initial_code: dict, task_type: str) -> ReActResult:
        steps: list[ReActStep] = []
        tool_map = {t.name: t for t in self.tools}
        current_code = initial_code

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        for round_num in range(1, self.max_rounds + 1):
            step = ReActStep(round=round_num)

            # Call LLM with retry
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

            # Parse the response
            step.thought = response_text[:500]
            action, action_input = self._parse_action(response_text)

            if not action:
                # No valid action found, try to extract code directly
                extracted = self._extract_code(response_text, current_code)
                if extracted:
                    result = ReActResult(success=True, final_code=extracted,
                        summary="Extracted from response", steps=steps,
                        rounds_used=round_num, messages=messages)
                    _save_context(messages, task_type)
                    return result
                # Continue loop with LLM response as context
                messages.append({"role": "assistant", "content": response_text})
                step.observation = "No action parsed, continuing"
                steps.append(step)
                continue

            step.action = action
            step.action_input = action_input

            # Execute tool
            tool = tool_map.get(action)
            if tool:
                try:
                    result = await tool.run(**action_input)
                    step.observation = result[:500]
                except Exception as e:
                    step.observation = f"Tool error: {e}"
            else:
                step.observation = f"Unknown action: {action}"

            # Append to messages as text (no tool_calls format)
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": f"Tool [{action}] result:\n{step.observation}"})

            steps.append(step)

            # Check if finished
            if action == "finish_optimization":
                code = action_input.get("code_files", current_code)
                if isinstance(code, str):
                    try:
                        code = json.loads(code)
                    except:
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

        # Max rounds
        _save_context(messages, task_type)
        return ReActResult(
            success=False, final_code=current_code,
            summary=f"Incomplete after {self.max_rounds} rounds",
            steps=steps, rounds_used=self.max_rounds, messages=messages,
        )

    # ── Parsing helpers ────────────────────────────

    def _parse_action(self, text: str) -> tuple:
        """Parse THOUGHT/ACTION format from LLM response."""
        # Match: ACTION: tool_name
        action_match = re.search(r'ACTION:\s*(\w+)', text, re.IGNORECASE)
        if not action_match:
            return (None, {})

        action = action_match.group(1)

        # Parse JSON block after ACTION
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

    def _extract_code(self, text: str, fallback: dict) -> dict:
        """Extract code files from LLM response."""
        result = {}
        blocks = re.findall(r'###\s*(\S+)\s*\n```(?:\w+)?\n(.*?)```', text, re.DOTALL)
        for fname, code in blocks:
            result[fname.strip()] = code.strip()
        return result or {}
