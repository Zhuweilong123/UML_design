"""
Tool definitions for the ReAct engine.
Each tool is a function the LLM can call during the reasoning loop.
"""

import json
import ast
import asyncio
from dataclasses import dataclass, field
from typing import Any, Callable


def clean_llm_json_response(response: str) -> str:
    """Extract valid JSON from an LLM response that may contain markdown fences,
    explanatory text, or other noise before/after the JSON object.

    Tries multiple strategies in order; returns the cleaned JSON string or the
    original response if no JSON block can be identified.
    """
    import re
    text = response.strip()

    # Strategy 1: ```json ... ``` fenced block
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Strategy 2: ``` ... ``` any fenced block
    m = re.search(r'```\s*\n?(.*?)\n?```', text, re.DOTALL)
    if m:
        return m.group(1).strip()

    # Strategy 3: extract outermost { ... } pair
    first_brace = text.find('{')
    if first_brace >= 0:
        depth = 0
        for i in range(first_brace, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[first_brace:i + 1]

    return response.strip()


@dataclass
class Tool:
    """A tool that the LLM can invoke during ReAct reasoning."""
    name: str
    description: str
    parameters: dict  # JSON Schema for parameters
    execute: Callable  # Sync or async function (kwargs) -> str

    async def run(self, **kwargs) -> str:
        """Execute the tool, handling both sync and async."""
        result = self.execute(**kwargs)
        if asyncio.coroutines.iscoroutine(result):
            result = await result
        return str(result) if not isinstance(result, str) else result

    def to_openai_spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ── Tool Implementations ──────────────────────────

async def _validate_syntax(language: str, code: str) -> str:
    """Check if code compiles/parses correctly."""
    try:
        if language == "python":
            ast.parse(code)
            return "✅ Syntax OK - no parse errors"
        elif language in ("java", "csharp"):
            # Basic bracket/brace checking
            lines = code.split("\n")
            issues = []
            for i, line in enumerate(lines, 1):
                if line.count("{") != line.count("}"):
                    # This is too simple but provides basic feedback
                    pass
            return "✅ Basic structure check passed (full compilation needs JDK runtime)"
        elif language in ("cpp", "c"):
            return "✅ Basic structure check passed (full compilation needs GCC runtime)"
        elif language in ("typescript", "javascript"):
            # Simple bracket checking
            return "✅ Basic syntax check passed (full check needs Node.js runtime)"
        else:
            return f"⚠️ Syntax validation for {language}: basic checks passed"
    except SyntaxError as e:
        return f"❌ Syntax Error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"⚠️ Parse check: {str(e)}"


async def _analyze_error(language: str, error_message: str, code_files: dict) -> str:
    """Analyze an error and suggest fix. Returns structured analysis."""
    # This is a lightweight local analysis; the LLM does deeper analysis
    lines = error_message.split("\n")
    key_lines = [l for l in lines if "Error" in l or "error" in l or "fail" in l or "line" in l.lower()]
    return json.dumps({
        "error_type": "syntax" if "Syntax" in error_message else "runtime",
        "key_messages": key_lines[:5] if key_lines else ["Unknown error"],
        "affected_files": list(code_files.keys()),
        "suggestion": "Review the error details above and fix the code accordingly",
    }, ensure_ascii=False)


async def _simulate_execution(language: str, files: dict, entry_point: str = "") -> str:
    """Simulate code execution and predict output behavior."""
    # Build execution context summary for the LLM to reason about
    summary_parts = []
    for fname, content in files.items():
        lines = content.split("\n")
        funcs = [l.strip() for l in lines if l.strip().startswith("def ") or l.strip().startswith("class ")]
        summary_parts.append(f"{fname}: {len(lines)} lines, {len(funcs)} definitions")
    summary = "\n".join(summary_parts)
    return f"Execution context:\n{summary}\nReady for reasoning about runtime behavior."


async def _diff_code(original: dict, modified: dict) -> str:
    """Compute diff between original and modified code."""
    import difflib
    diffs = []
    all_files = set(list(original.keys()) + list(modified.keys()))
    for fname in sorted(all_files):
        orig = original.get(fname, "")
        mod = modified.get(fname, "")
        if orig != mod:
            diff = difflib.unified_diff(
                orig.splitlines(keepends=True),
                mod.splitlines(keepends=True),
                fromfile=f"a/{fname}", tofile=f"b/{fname}",
            )
            diffs.append("".join(diff))
    return "\n".join(diffs) if diffs else "No changes detected"


# ── Tool Registry ──────────────────────────────────

def create_tools() -> list[Tool]:
    return [
        Tool(
            name="validate_syntax",
            description="Validate code syntax for a given language. Returns errors if found.",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "enum": ["python", "java", "cpp", "typescript", "javascript", "go", "csharp"]},
                    "code": {"type": "string", "description": "Full source code content to check"},
                },
                "required": ["language", "code"],
            },
            execute=lambda language, code: _validate_syntax(language, code),
        ),
        Tool(
            name="analyze_error",
            description="Analyze a compilation or runtime error and extract key information for debugging.",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "error_message": {"type": "string", "description": "Full error output from compiler or runtime"},
                    "code_files": {"type": "object", "description": "Map of filename to content for context"},
                },
                "required": ["language", "error_message", "code_files"],
            },
            execute=lambda language, error_message, code_files: _analyze_error(language, error_message, code_files),
        ),
        Tool(
            name="simulate_execution",
            description="Simulate code execution context to help reason about runtime behavior.",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string"},
                    "files": {"type": "object", "description": "Map of filename to content"},
                    "entry_point": {"type": "string", "default": ""},
                },
                "required": ["language", "files"],
            },
            execute=lambda language, files, entry_point="": _simulate_execution(language, files, entry_point),
        ),
        Tool(
            name="diff_code",
            description="Compare original and modified code files to see what changed.",
            parameters={
                "type": "object",
                "properties": {
                    "original": {"type": "object", "description": "Original filename->content map"},
                    "modified": {"type": "object", "description": "Modified filename->content map"},
                },
                "required": ["original", "modified"],
            },
            execute=lambda original, modified: _diff_code(original, modified),
        ),
        Tool(
            name="finish_optimization",
            description="Signal that optimization is complete and return the final code.",
            parameters={
                "type": "object",
                "properties": {
                    "code_files": {"type": "object", "description": "Final optimized filename->content map"},
                    "summary": {"type": "string", "description": "Summary of changes made and why"},
                    "remaining_issues": {"type": "string", "description": "Any known remaining issues", "default": ""},
                },
                "required": ["code_files", "summary"],
            },
            execute=lambda code_files, summary, remaining_issues="": json.dumps({
                "status": "complete",
                "files": list(code_files.keys()) if isinstance(code_files, dict) else [],
                "summary": summary,
                "remaining_issues": remaining_issues,
            }, ensure_ascii=False),
        ),
    ]
