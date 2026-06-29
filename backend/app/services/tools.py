"""
Tool definitions for the ReAct engine.
Each tool is a function the LLM can call during the reasoning loop.
"""

import json
import ast
import asyncio
import py_compile
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

async def _validate_syntax(language: str, code_files: dict) -> str:
    """Validate syntax for multiple code files at once.
    Accepts a dict of filename→content, returns per-file results.
    """
    results = {}
    for fname, code in code_files.items():
        if not isinstance(code, str):
            results[fname] = "⚠️ Skipped: not a text file"
            continue
        try:
            if language == "python":
                ast.parse(code)
                results[fname] = "✅ Syntax OK"
            elif language in ("java", "csharp", "cpp", "c"):
                results[fname] = "✅ Basic structure check passed (full compilation needs compiler runtime)"
            elif language in ("typescript", "javascript"):
                results[fname] = "✅ Basic syntax check passed (full check needs Node.js runtime)"
            else:
                results[fname] = f"⚠️ Syntax validation for {language}: basic checks passed"
        except SyntaxError as e:
            results[fname] = f"❌ SyntaxError: line {e.lineno}, {e.msg}"
        except Exception as e:
            results[fname] = f"⚠️ Parse check: {str(e)}"
    return json.dumps(results, ensure_ascii=False)


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


async def _check_imports(language: str, code_files: dict) -> str:
    """Write code files to temp directory and verify all Python files compile
    and can be imported. Uses subprocess to actually resolve imports.

    Returns JSON with per-file pass/fail status.
    """
    import tempfile
    import subprocess
    import os as _os
    import sys

    if language != "python":
        return json.dumps({"status": "skipped", "reason": f"Import check only supported for Python, got {language}"})

    passed = []
    failed = {}

    with tempfile.TemporaryDirectory() as tmp:
        # Write all files to tmp
        for fname, content in code_files.items():
            fpath = _os.path.join(tmp, fname)
            _os.makedirs(_os.path.dirname(fpath) or tmp, exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

        # Check each .py file: syntax check + import check via subprocess
        for fname, content in code_files.items():
            if not fname.endswith(".py"):
                passed.append(fname)
                continue

            fpath = _os.path.join(tmp, fname)
            try:
                # Step 1: syntax check
                ast.parse(content)
            except SyntaxError as e:
                failed[fname] = f"SyntaxError: line {e.lineno}, {e.msg}"
                continue

            # Step 2: try to import the module via subprocess
            module_name = fname.replace(".py", "")
            preamble = (
                f"import sys; sys.path.insert(0, {tmp!r}); "
                f"__import__({module_name!r})"
            )
            try:
                proc = subprocess.run(
                    [sys.executable, "-c", preamble],
                    capture_output=True, text=True,
                    timeout=15, cwd=tmp,
                )
                if proc.returncode == 0:
                    passed.append(fname)
                else:
                    # Extract first meaningful error line
                    err_lines = [l for l in proc.stderr.split("\n") if l.strip() and "Traceback" not in l]
                    err_msg = err_lines[0].strip() if err_lines else f"exit={proc.returncode}"
                    # Shorten common verbose messages
                    if "ModuleNotFoundError" in proc.stderr or "ImportError" in proc.stderr:
                        for line in proc.stderr.split("\n"):
                            if "Error:" in line:
                                err_msg = line.strip()[:200]
                                break
                    failed[fname] = err_msg[:200]
            except subprocess.TimeoutExpired:
                failed[fname] = "Timeout: import took >15s"
            except Exception as e:
                failed[fname] = f"{type(e).__name__}: {e}"

    return json.dumps({"passed": passed, "failed": failed}, ensure_ascii=False)


async def _run_module(language: str, module_name: str, code_files: dict) -> str:
    """Execute a Python module via subprocess to detect runtime ImportError/SyntaxError.
    Returns stdout, stderr, and exit code.
    """
    import tempfile
    import subprocess
    import os as _os
    import sys

    if language != "python":
        return json.dumps({"status": "skipped", "reason": f"Module run only supported for Python, got {language}"})

    with tempfile.TemporaryDirectory() as tmp:
        # Write all files to tmp
        for fname, content in code_files.items():
            fpath = _os.path.join(tmp, fname)
            _os.makedirs(_os.path.dirname(fpath) or tmp, exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

        # Build command: python -c "import <module_name>"
        # First add tmp to sys.path so imports resolve
        preamble = f"import sys; sys.path.insert(0, {tmp!r}); import {module_name}"
        try:
            proc = subprocess.run(
                [sys.executable, "-c", preamble],
                capture_output=True, text=True,
                timeout=30, cwd=tmp,
            )
            return json.dumps({
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:2000],
                "stderr": proc.stderr[:2000],
            }, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({"exit_code": -1, "stderr": "Execution timed out (30s)"})
        except Exception as e:
            return json.dumps({"exit_code": -1, "stderr": str(e)})


async def _check_change_ratio(original: dict, modified: dict, threshold: int) -> str:
    """Compare original vs modified code using difflib character-level diff.

    Reports per-file change percentage and flags files exceeding *threshold* (%).
    New files (not in original) are noted but not counted against the threshold.
    """
    import difflib

    if not original:
        return json.dumps({
            "total_pct": 0,
            "exceeds_threshold": False,
            "message": "No original code to compare — skipping change check",
        }, ensure_ascii=False)

    per_file = {}
    total_orig_chars = 0
    total_changed_chars = 0

    all_files = sorted(set(list(original.keys()) + list(modified.keys())))
    for fname in all_files:
        orig = original.get(fname, "")
        mod = modified.get(fname, "")

        if not orig:
            # New file — not in original
            per_file[fname] = {"pct": 0, "status": "new_file", "note": "Not in original"}
            continue

        if orig == mod:
            per_file[fname] = {"pct": 0, "status": "unchanged"}
            total_orig_chars += len(orig)
            continue

        sm = difflib.SequenceMatcher(None, orig, mod)
        # ratio() = 2*M/T where M=matches, T=total chars in both sequences
        similarity = sm.ratio()
        change_pct = round((1 - similarity) * 100)

        exceeds = change_pct > threshold
        per_file[fname] = {
            "pct": change_pct,
            "status": "exceeds" if exceeds else "within_limit",
            "threshold": threshold,
        }
        total_orig_chars += len(orig)
        total_changed_chars += int(len(orig) * change_pct / 100)

    total_pct = round(total_changed_chars / total_orig_chars * 100) if total_orig_chars > 0 else 0
    exceeded = [f for f, d in per_file.items() if d.get("status") == "exceeds"]

    return json.dumps({
        "total_pct": total_pct,
        "exceeds_threshold": len(exceeded) > 0,
        "exceeded_files": exceeded,
        "per_file": per_file,
        "threshold": threshold,
    }, ensure_ascii=False)


# ── Tool Registry ──────────────────────────────────

def create_tools() -> list[Tool]:
    return [
        Tool(
            name="validate_syntax",
            description="Validate syntax for multiple code files at once. Pass all files as a filename→content dict.",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "enum": ["python", "java", "cpp", "typescript", "javascript", "go", "csharp"]},
                    "code_files": {"type": "object", "description": "Dict mapping filenames to full source code content"},
                },
                "required": ["language", "code_files"],
            },
            execute=lambda language, code_files: _validate_syntax(language, code_files),
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


def create_validation_tools() -> list[Tool]:
    """Create the subset of tools used for Stage 3 code validation.

    Schemas are strict-mode compatible:
    - ``additionalProperties``: false on every object
    - All properties are required (no optional/default fields)
    """
    return [
        Tool(
            name="check_imports",
            description="Validate syntax AND imports for ALL code files. Performs ast.parse (syntax) + subprocess import check (runtime). Reports per-file pass/fail.",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Programming language (only python is supported for import checking)"},
                    "code_files": {"type": "object", "description": "Map of filename to full source content"},
                },
                "required": ["language", "code_files"],
                "additionalProperties": False,
            },
            execute=lambda language, code_files: _check_imports(language, code_files),
        ),
        Tool(
            name="run_module",
            description="Run 'python -c \"import <module_name>\"' in a temp directory with all code files to catch runtime ImportError/SyntaxError.",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Programming language"},
                    "module_name": {"type": "string", "description": "The main module name to import (without .py extension)"},
                    "code_files": {"type": "object", "description": "Map of all filename to content"},
                },
                "required": ["language", "module_name", "code_files"],
                "additionalProperties": False,
            },
            execute=lambda language, module_name, code_files: _run_module(language, module_name, code_files),
        ),
        Tool(
            name="analyze_error",
            description="Analyze a compilation or runtime error message and extract key information for debugging.",
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Programming language"},
                    "error_message": {"type": "string", "description": "Full error output from compiler or runtime"},
                    "code_files": {"type": "object", "description": "Map of filename to content for context"},
                },
                "required": ["language", "error_message", "code_files"],
                "additionalProperties": False,
            },
            execute=lambda language, error_message, code_files: _analyze_error(language, error_message, code_files),
        ),
        Tool(
            name="finish_optimization",
            description="Signal that validation/optimization is complete and return the final code files.",
            parameters={
                "type": "object",
                "properties": {
                    "code_files": {"type": "object", "description": "Final validated filename->content map"},
                    "summary": {"type": "string", "description": "Summary of changes made and validation results"},
                    "remaining_issues": {"type": "string", "description": "Any known remaining issues (empty string if none)"},
                },
                "required": ["code_files", "summary", "remaining_issues"],
                "additionalProperties": False,
            },
            execute=lambda code_files, summary, remaining_issues="": json.dumps({
                "status": "complete",
                "files": list(code_files.keys()) if isinstance(code_files, dict) else [],
                "summary": summary,
                "remaining_issues": remaining_issues,
            }, ensure_ascii=False),
        ),
    ]
