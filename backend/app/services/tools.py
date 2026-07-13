"""
Tool definitions for the ReAct engine.
Each tool is a function the LLM can call during the reasoning loop.
"""

import json
import ast
import asyncio
import logging
import os
import subprocess
import py_compile
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


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


async def _check_imports(language: str, code_files: dict | None = None, source_dir: str = "") -> str:
    """Validate syntax + imports for Python files.

    If *source_dir* is given, reads ``.py`` files directly from disk.
    Otherwise falls back to *code_files* (in-memory dict).

    Returns JSON with per-file pass/fail status.
    """
    import subprocess as _sp
    import sys as _sys
    import os as _os

    if language != "python":
        return json.dumps({"status": "skipped", "reason": f"Import check only supported for Python, got {language}"})

    # ── Resolve files to check ──
    if source_dir and _os.path.isdir(source_dir):
        files: dict[str, str] = {}
        for fname in sorted(_os.listdir(source_dir)):
            if fname.endswith(".py") and not fname.startswith("test_"):
                fpath = _os.path.join(source_dir, fname)
                with open(fpath, "r", encoding="utf-8") as f:
                    files[fname] = f.read()
    elif code_files:
        files = code_files
    else:
        return json.dumps({"status": "skipped", "reason": "No source_dir or code_files provided"})

    passed, failed = [], {}
    has_dir = bool(source_dir and _os.path.isdir(source_dir))

    for fname, content in files.items():
        if not fname.endswith(".py"):
            passed.append(fname)
            continue

        # Step 1: syntax check
        try:
            ast.parse(content)
        except SyntaxError as e:
            failed[fname] = f"SyntaxError: line {e.lineno}, {e.msg}"
            continue

        # Step 2: import check via subprocess
        if has_dir:
            # Files on disk — just run from their actual location
            module_name = fname.replace(".py", "")
            preamble = (
                f"import sys; sys.path.insert(0, {source_dir!r}); "
                f"__import__({module_name!r})"
            )
        else:
            # In-memory — write to temp dir first
            import tempfile
            tmp = tempfile.mkdtemp()
            for fn, fc in files.items():
                fp = _os.path.join(tmp, fn)
                _os.makedirs(_os.path.dirname(fp) or tmp, exist_ok=True)
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(fc)
            module_name = fname.replace(".py", "")
            preamble = (
                f"import sys; sys.path.insert(0, {tmp!r}); "
                f"__import__({module_name!r})"
            )

        try:
            proc = _sp.run(
                [_sys.executable, "-c", preamble],
                capture_output=True, text=True, timeout=15,
                cwd=(source_dir if has_dir else tmp),
            )
            if proc.returncode == 0:
                passed.append(fname)
            else:
                err_lines = [l for l in proc.stderr.split("\n") if l.strip() and "Traceback" not in l]
                err_msg = err_lines[0].strip() if err_lines else f"exit={proc.returncode}"
                if "ModuleNotFoundError" in proc.stderr or "ImportError" in proc.stderr:
                    for line in proc.stderr.split("\n"):
                        if "Error:" in line:
                            err_msg = line.strip()[:200]
                            break
                failed[fname] = err_msg[:200]
        except _sp.TimeoutExpired:
            failed[fname] = "Timeout: import took >15s"
        except Exception as e:
            failed[fname] = f"{type(e).__name__}: {e}"
        finally:
            if not has_dir:
                import shutil
                shutil.rmtree(tmp, ignore_errors=True)

    return json.dumps({"passed": passed, "failed": failed}, ensure_ascii=False)


async def _run_module(language: str, module_name: str, code_files: dict | None = None, source_dir: str = "") -> str:
    """Execute ``python -c "import <module_name>"`` to catch ImportError/SyntaxError.

    If *source_dir* is given, sets ``sys.path`` to that directory.
    Otherwise falls back to *code_files* (written to a temp dir).

    Returns JSON with exit_code, stdout, stderr.
    """
    import tempfile
    import subprocess as _sp
    import sys as _sys
    import os as _os

    if language != "python":
        return json.dumps({"status": "skipped", "reason": f"Module run only supported for Python, got {language}"})

    if source_dir and _os.path.isdir(source_dir):
        preamble = (
            f"import sys; sys.path.insert(0, {source_dir!r}); "
            f"import {module_name}"
        )
        cwd = source_dir
    elif code_files:
        tmp = tempfile.mkdtemp()
        try:
            for fname, content in code_files.items():
                fpath = _os.path.join(tmp, fname)
                _os.makedirs(_os.path.dirname(fpath) or tmp, exist_ok=True)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
            preamble = (
                f"import sys; sys.path.insert(0, {tmp!r}); "
                f"import {module_name}"
            )
            cwd = tmp
        except Exception as e:
            return json.dumps({"exit_code": -1, "stderr": str(e)})
    else:
        return json.dumps({"status": "skipped", "reason": "No source_dir or code_files provided"})

    try:
        proc = _sp.run(
            [_sys.executable, "-c", preamble],
            capture_output=True, text=True, timeout=30, cwd=cwd,
        )
        return json.dumps({
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:2000],
            "stderr": proc.stderr[:2000],
        }, ensure_ascii=False)
    except _sp.TimeoutExpired:
        return json.dumps({"exit_code": -1, "stderr": "Execution timed out (30s)"})
    except Exception as e:
        return json.dumps({"exit_code": -1, "stderr": str(e)})
    finally:
        if not source_dir and code_files:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)


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


# ── Bash tool ───────────────────────────────────────

# Commands allowed in run_bash. Each key is the first word of a command.
# Adding a new entry here is an explicit security decision — review required.
ALLOWED_COMMANDS: set[str] = {
    # Environment / info
    "python", "python3", "pip", "pip3", "which", "where", "echo",
    "printenv", "env", "pwd",
    # File inspection (read-only)
    "ls", "dir", "cat", "head", "tail", "wc", "find", "tree",
    "file", "stat", "du", "test",
    # Test execution
    "pytest", "coverage", "python",
    # Git (read-only sub-commands enforced separately below)
    "git",
    # Text processing
    "grep", "sort", "uniq", "cut", "awk", "sed",
}

# Git sub-commands that are read-only and safe for the LLM to invoke.
_GIT_SAFE_SUBCOMMANDS: set[str] = {
    "status", "diff", "log", "branch", "show", "rev-parse",
    "config", "remote", "tag", "stash",
}


def _resolve_project_root() -> str:
    """Return the project-root directory for sandboxing bash execution."""
    try:
        from app.core.config import get_settings
        settings = get_settings()
        return os.path.abspath(os.path.join(settings.uml_dir, "..", ".."))
    except Exception:
        return os.getcwd()


def _check_dangerous_syntax(command: str) -> list[str]:
    """Return a list of dangerous syntax elements found in *command*.

    Returns an empty list when the command passes all syntactic checks.
    """
    import re as _re

    violations: list[str] = []

    # Command chaining operators (only outside of quoted strings)
    _in_single = False
    _in_double = False
    _esc = False
    for i, ch in enumerate(command):
        if _esc:
            _esc = False
            continue
        if ch == '\\':
            _esc = True
            continue
        if ch == "'" and not _in_double:
            _in_single = not _in_single
            continue
        if ch == '"' and not _in_single:
            _in_double = not _in_double
            continue
        if _in_single or _in_double:
            continue
        if ch == ';':
            violations.append("';' — command chaining is not allowed; "
                              "split into separate run_bash calls")
            break
        if command[i:i+2] in ("&&", "||"):
            token = command[i:i+2]
            violations.append(f"'{token}' — command chaining is not allowed; "
                              "split into separate run_bash calls")
            break

    # Command substitution (outside quotes only — checked above)
    # Re-check outside quotes
    _no_quotes = _re.sub(r'"[^"]*"', '', _re.sub(r"'[^']*'", '', command))
    if "$(" in _no_quotes or "`" in _no_quotes:
        violations.append("'$()' or backtick — command substitution is not allowed")

    # Output redirect: allow stderr redirects (2>&1, 2>/dev/null) but block others
    stripped = _re.sub(r'2>(?:&1|/dev/null)', '', command)
    if ">" in stripped:
        violations.append("'>' — output redirection is not allowed (2>&1 and 2>/dev/null are ok)")

    # Input redirect from a file is ok, but << (heredoc) and <() (process sub) are not
    if "<<" in command:
        violations.append("'<<' — heredoc is not allowed")
    if "<(" in _no_quotes:
        violations.append("'<()' — process substitution is not allowed")

    return violations


def _validate_bash_command(command: str) -> dict | None:
    """Validate *command* against the safety policy.

    Returns ``None`` when the command passes all checks, or a rejection
    ``dict`` (with ``status: "rejected"``) suitable for the LLM observation.
    """
    # ── 1. Prohibited syntax ──
    violations = _check_dangerous_syntax(command)
    if violations:
        logger.warning(f"[run_bash] Rejected (syntax): {command!r} → {violations}")
        return {
            "status": "rejected",
            "command": command,
            "reason": "prohibited_syntax",
            "violations": violations,
            "suggestion": (
                "Remove prohibited operators. Use pipe (|) only for chaining "
                "allowed commands. Redirect stderr safely with 2>&1 at the end."
            ),
        }

    # ── 2. Pipeline whitelist check ──
    segments = [s.strip() for s in command.split("|")]
    for i, seg in enumerate(segments):
        if not seg:
            continue
        cmd_name = seg.split()[0] if seg.split() else ""
        if cmd_name not in ALLOWED_COMMANDS:
            logger.warning(
                f"[run_bash] Rejected (cmd): {command!r} → "
                f"'{cmd_name}' at position {i+1} not allowed"
            )
            return {
                "status": "rejected",
                "full_command": command,
                "reason": "command_not_allowed",
                "blocked_cmd": cmd_name,
                "position": i + 1,
                "allowed_commands": sorted(ALLOWED_COMMANDS),
                "suggestion": (
                    f"Command '{cmd_name}' is blocked. Use an allowed command "
                    f"or split your task into multiple safe calls."
                ),
            }

        # ── 2a. Extra check: git → only safe sub-commands ──
        if cmd_name == "git":
            parts = seg.split()
            sub = parts[1] if len(parts) > 1 else ""
            if not sub:
                return {
                    "status": "rejected",
                    "command": command,
                    "reason": "git_no_subcommand",
                    "suggestion": "Specify a git sub-command, e.g. 'git status' or 'git diff'",
                }
            if sub not in _GIT_SAFE_SUBCOMMANDS:
                # Check for --help or -h which are always benign
                if "--help" not in parts and "-h" not in parts:
                    logger.warning(
                        f"[run_bash] Rejected (git): {command!r} → "
                        f"sub-command '{sub}' not safe"
                    )
                    return {
                        "status": "rejected",
                        "command": command,
                        "reason": "git_subcommand_blocked",
                        "subcommand": sub,
                        "allowed_subcommands": sorted(_GIT_SAFE_SUBCOMMANDS),
                        "suggestion": (
                            f"Git sub-command '{sub}' is blocked. "
                            f"Allowed read-only sub-commands: "
                            f"{', '.join(sorted(_GIT_SAFE_SUBCOMMANDS))}"
                        ),
                    }

    return None  # all checks passed


def _find_bash_shell() -> str | None:
    """Return the path to ``bash.exe`` on Windows, or ``None`` if not found."""
    if os.name != "nt":
        return None
    candidates = [
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
        os.path.expandvars(r"%ProgramFiles%\Git\bin\bash.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\bin\bash.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    # Last resort: try `where bash` in cmd
    try:
        result = subprocess.run(
            ["where", "bash"], capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return None


async def _execute_bash(command: str, cwd: str) -> str:
    """Execute a (pre-validated) bash command and return the result JSON.

    On Windows, prefers Git Bash (``bash.exe``) over ``cmd.exe`` so that
    Linux-idiom commands (``ls``, ``cat``, ``find``, etc.) work correctly.
    """
    bash_path = _find_bash_shell()
    kwargs: dict = {
        "shell": True,
        "capture_output": True,
        "text": True,
        "timeout": 30,
        "cwd": cwd,
        "env": {**os.environ, "PYTHONIOENCODING": "utf-8"},
    }
    if bash_path:
        kwargs["executable"] = bash_path

    try:
        proc = subprocess.run(command, **kwargs)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        output = (stdout + ("\n" + stderr if stderr else ""))[:50_000]
        logger.info(
            f"[run_bash] exit={proc.returncode} len={len(output)} cmd={command!r}"
        )

        # ── Help the LLM when the shell clearly doesn't support POSIX commands ──
        hint = ""
        if bash_path is None and proc.returncode == 1 and not output:
            hint = (
                "⚠️ This machine does not have Git Bash installed — POSIX commands "
                "(ls, cat, find, grep) may not work. Prefer check_imports + run_module "
                "for code validation, and use 'dir' instead of 'ls' to list files."
            )

        return json.dumps({
            "status": "ok",
            "command": command,
            "exit_code": proc.returncode,
            "output": output + (("\n" + hint) if hint else ""),
            "cwd": cwd,
        }, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        logger.warning(f"[run_bash] Timeout: {command!r}")
        return json.dumps({
            "status": "error",
            "command": command,
            "reason": "timeout",
            "detail": "Command exceeded 30 second limit",
        }, ensure_ascii=False)
    except Exception as e:
        logger.error(f"[run_bash] Error: {command!r} → {e}")
        return json.dumps({
            "status": "error",
            "command": command,
            "reason": "execution_failed",
            "detail": f"{type(e).__name__}: {e}",
        }, ensure_ascii=False)


async def _run_bash(command: str) -> str:
    """Execute a safe bash command inside the project root.

    Safety checks (in order):
    1. Prohibited syntax: ``;`` ``&&`` ``||`` ``$()`` `` `` `` > `` `` >> `` ``<<`` ``<()``
    2. Each pipeline segment's first word must be in :data:`ALLOWED_COMMANDS`
    3. ``git`` sub-commands are validated against ``_GIT_SAFE_SUBCOMMANDS``
    4. Execution caps: 30 s timeout, 50 kiB output limit, cwd = project root
    """
    cwd = _resolve_project_root()

    rejection = _validate_bash_command(command)
    if rejection is not None:
        return json.dumps(rejection, ensure_ascii=False)

    return await _execute_bash(command, cwd)


# ── Tool Registry ──────────────────────────────────

def create_tools() -> list[Tool]:
    """Unified tool registry for ReAct engine — used by Pipeline Stage 3/5 and
    general-purpose code optimisation.

    All tool schemas use ``additionalProperties: false`` for strict-mode
    compatibility with LLM function-calling APIs.
    """
    return [
        Tool(
            name="check_imports",
            description=(
                "Validate syntax AND imports for Python files. "
                "Pass source_dir to check files on disk (preferred — no code transfer needed). "
                "Pass code_files dict only when files are not on disk yet. "
                "Reports per-file pass/fail with specific error messages."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Programming language (only python is supported)"},
                    "source_dir": {"type": "string", "description": "Directory containing .py files (preferred — reads from disk)"},
                    "code_files": {"type": "object", "description": "Map of filename→content (fallback when files not on disk)"},
                },
                "required": ["language"],
                "additionalProperties": False,
            },
            execute=lambda language, source_dir="", code_files=None: _check_imports(language, code_files, source_dir),
        ),
        Tool(
            name="run_module",
            description=(
                "Run 'python -c \"import <module_name>\"' to catch ImportError/SyntaxError. "
                "Pass source_dir to run from disk (preferred). "
                "Pass code_files only as fallback."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Programming language"},
                    "module_name": {"type": "string", "description": "Module name to import (without .py extension)"},
                    "source_dir": {"type": "string", "description": "Directory to add to sys.path (preferred)"},
                    "code_files": {"type": "object", "description": "Map of filename→content (fallback)"},
                },
                "required": ["language", "module_name"],
                "additionalProperties": False,
            },
            execute=lambda language, module_name, source_dir="", code_files=None: _run_module(language, module_name, code_files, source_dir),
        ),
        Tool(
            name="run_bash",
            description=(
                "Execute a READ-ONLY bash command to inspect the environment, "
                "list files, check installed packages, or run tests.\n"
                "ALLOWED commands: python, pip, pytest, ls, cat, git (status/diff/log/show only), "
                "grep, find, echo, which, wc, head, tail, sort, uniq, cut, awk, sed, file, stat, tree.\n"
                "PROHIBITED: rm, sudo, curl, kill, chmod, file writes (> >>), "
                "command chaining (; && ||), command substitution ($() ``).\n"
                "Pipes (|) are allowed only between allowed commands.\n"
                "Each call is capped at 30 s timeout and 50 kiB output.\n"
                "Use this to explore the environment — the observation will help you "
                "decide next steps."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The bash command to execute. Must only use allowed commands.",
                    },
                },
                "required": ["command"],
                "additionalProperties": False,
            },
            execute=lambda command: _run_bash(command),
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
            name="diff_code",
            description="Compare original and modified code files to see what changed.",
            parameters={
                "type": "object",
                "properties": {
                    "original": {"type": "object", "description": "Original filename->content map"},
                    "modified": {"type": "object", "description": "Modified filename->content map"},
                },
                "required": ["original", "modified"],
                "additionalProperties": False,
            },
            execute=lambda original, modified: _diff_code(original, modified),
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
