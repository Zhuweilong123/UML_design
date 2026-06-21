"""Code generation service – generates code in 12 languages from UML diagrams."""

import json
from app.models.uml import UmlDiagram
from app.services.llm_service import chat
from app.services.tools import clean_llm_json_response

SUPPORTED_LANGUAGES = [
    "python", "java", "typescript", "javascript", "csharp", "cpp",
    "go", "rust", "ruby", "swift", "kotlin", "php",
]

LANGUAGE_TEMPLATES: dict[str, str] = {
    "python": """
# Python code generated from UML diagram: {diagram_name}
# Stereotype mapping:
#   class     -> regular class
#   interface -> ABC (abstract base class)
#   abstract  -> ABC with @abstractmethod
#   enum      -> Enum subclass
""",
    "java": """
// Java code generated from UML diagram: {diagram_name}
""",
    "typescript": """
// TypeScript code generated from UML diagram: {diagram_name}
""",
    "cpp": """
// C++ code generated from UML diagram: {diagram_name}
""",
    "go": """
// Go code generated from UML diagram: {diagram_name}
""",
}


def _build_class_prompt(diagram: UmlDiagram, language: str) -> str:
    """Build a structured prompt for the LLM to generate code."""
    classes_desc = []
    for c in diagram.classes:
        attrs = []
        for a in c.attributes:
            static = "static " if a.is_static else ""
            attrs.append(f"    {a.visibility} {static}{a.name}: {a.type}")
        methods = []
        for m in c.methods:
            static = "static " if m.is_static else ""
            abstract = "abstract " if m.is_abstract else ""
            methods.append(f"    {m.visibility} {abstract}{static}{m.name}({m.params}): {m.return_type}")
        # Include class notes (business logic requirements)
        note_block = ""
        if c.note.strip():
            note_block = f"\n  Business Rules: {c.note}"
        classes_desc.append(
            f"Class: {c.name} (stereotype={c.stereotype}){note_block}\n"
            + "Attributes:\n" + "\n".join(attrs or ["    (none)"]) + "\n"
            + "Methods:\n" + "\n".join(methods or ["    (none)"])
        )

    relations_desc = []
    for r in diagram.relations:
        src_name = next((c.name for c in diagram.classes if c.id == r.source), r.source)
        tgt_name = next((c.name for c in diagram.classes if c.id == r.target), r.target)
        # Include relation metadata
        extras = []
        if r.role_name:
            extras.append(f"role={r.role_name}")
        if r.multiplicity_source or r.multiplicity_target:
            extras.append(f"mult={r.multiplicity_source}..{r.multiplicity_target}")
        if r.note.strip():
            extras.append(f"note={r.note}")
        extra_str = f" ({', '.join(extras)})" if extras else ""
        relations_desc.append(f"  {src_name} --({r.type})--> {tgt_name}{extra_str}")

    prompt = f"""Generate complete, compilable {language} code from the following UML class diagram.

## Classes:
{chr(10).join(classes_desc)}

## Relations:
{chr(10).join(relations_desc) if relations_desc else "  (none)"}

## Requirements:
- CRITICAL: Implement ALL business rules described in each class's "Business Rules" section.
  These are the core logic requirements — do NOT skip them.
- Generate a separate file for each class where appropriate.
- Follow {language} best practices and conventions.
- Implement all specified attributes, methods, and relations.
- For inheritance/realization, use proper {language} syntax.
- For composition/aggregation, use member variables.
- Add proper imports/includes.
- Return the result as a JSON object mapping filenames to file content:
```json
{{"filename1.ext": "content...", "filename2.ext": "content..."}}
```
Only output the JSON object, no other text.
"""
    return prompt


def _build_test_prompt(code_files: dict[str, str], language: str, test_cases: str = "") -> str:
    """Build a prompt to generate tests for the given code, using Excel test case requirements."""
    code_block = "\n\n".join(
        f"### {fname}\n```{language}\n{content}\n```"
        for fname, content in code_files.items()
    )

    # ── Extract actual API signatures from source code ──
    api_sigs = _extract_api_signatures(code_files, language)

    # ── Truncation detection ──
    MAX_TEST_CASES = 10000
    MAX_CODE_LEN = 8000
    tc_truncated = len(test_cases) > MAX_TEST_CASES if test_cases else False
    code_truncated = len(code_block) > MAX_CODE_LEN

    if test_cases and test_cases.strip():
        test_cases_section = test_cases[:MAX_TEST_CASES]
        code_section = code_block[:MAX_CODE_LEN]

        trunc_warning = ""
        if tc_truncated or code_truncated:
            trunc_warning = "⚠️ WARNING: Some data was truncated due to length limits. "
            if tc_truncated:
                trunc_warning += f"Test cases truncated from {len(test_cases)} to {MAX_TEST_CASES} chars. "
            if code_truncated:
                trunc_warning += f"Source code truncated from {len(code_block)} to {MAX_CODE_LEN} chars. "
            trunc_warning += "Use the API signatures below as the authoritative reference.\n\n"

        prompt = f"""You MUST generate unit tests for {language}. Follow these rules EXACTLY.

## YOUR PRIMARY TASK: ONE test function per case ID below

For EACH case ID in the test case list below, you MUST create exactly one test function.
The function name MUST be: `test_<CASE_ID>_<short_description>`

Example mapping:
  TC-OTA-001 "OtaTask.execute normal execution" → `def test_TC_OTA_001_ota_execute():`
  TC-CROW-002 "crow time window 2:00-4:00" → `def test_TC_CROW_002_crow_time_window():`
  TC-BASE-001 "subclass instantiation" → `def test_TC_BASE_001_subclass_instantiation():`

## ACTUAL SOURCE API (tests MUST match these exact signatures):
{api_sigs}

{trunc_warning}## TEST CASES (MUST cover ALL of these):
{test_cases_section}

## Complete Source Code (for understanding business logic):
{code_section}

## OUTPUT REQUIREMENTS:
1. Return ONLY a JSON object mapping filenames to file content.
2. Each test function's docstring MUST include: Case ID, test steps, and expected result.
3. Use the standard testing framework for {language}.
4. Group test functions logically — one test file per source module.
5. CRITICAL: Import paths and class/method signatures MUST match the ACTUAL SOURCE API above exactly.
   DO NOT invent parameter names — use the exact signatures shown.

Output format:
```json
{{"test_module1.ext": "code...", "test_module2.ext": "code..."}}
```
"""
    else:
        code_section = code_block[:MAX_CODE_LEN]
        prompt = f"""Generate comprehensive unit tests for the following {language} code.

## Source Code:
{code_section}

## Requirements:
- Write tests using the standard testing framework for {language}.
- Cover all public methods and edge cases.
- Each test function name MUST describe the scenario (e.g., `test_classname_method_scenario`).
- Return the result as a JSON object mapping test filenames to content:
```json
{{"test_filename.ext": "content..."}}
```
Only output the JSON object, no other text.
"""

    return prompt


def _extract_api_signatures(code_files: dict[str, str], language: str) -> str:
    """Extract importable class/func signatures from source code so LLM can match exact API."""
    import re
    lines_out = []
    for fname, content in code_files.items():
        lines_out.append(f"### {fname}")
        module_name = fname.rsplit(".", 1)[0] if "." in fname else fname
        lines_out.append(f"# Import: from {module_name} import ...")
        # Extract class definitions with constructor params
        for line in content.split("\n"):
            stripped = line.strip()
            # Class definition
            if stripped.startswith("class "):
                lines_out.append(stripped)
            # Method/function definition (top-level or class method)
            elif stripped.startswith("def ") and not stripped.startswith("def test_"):
                lines_out.append(f"  {stripped}")
        lines_out.append("")
    return "\n".join(lines_out)


async def generate_code(diagram: UmlDiagram, language: str) -> dict[str, str]:
    """Generate code files from a UML diagram."""
    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Unsupported language: {language}. Supported: {SUPPORTED_LANGUAGES}")

    prompt = _build_class_prompt(diagram, language)
    response = await chat(
        prompt=prompt,
        system_prompt=f"You are an expert {language} developer. Output only valid JSON mapping filenames to file content.",
        temperature=0.3,
        max_tokens=8192,
        json_mode=True,
    )

    # Parse JSON from response
    try:
        # Strip markdown code fences if present
        cleaned = clean_llm_json_response(response)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"main." + _get_extension(language): response}


async def generate_tests(
    code_files: dict[str, str], language: str, test_cases: str = ""
) -> dict[str, str]:
    """Generate test files for the given code, optionally using Excel test case requirements."""
    prompt = _build_test_prompt(code_files, language, test_cases)
    response = await chat(
        prompt=prompt,
        system_prompt=f"You are an expert {language} test engineer. Output only valid JSON.",
        temperature=0.3,
        max_tokens=8192,
    )
    try:
        cleaned = clean_llm_json_response(response)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"test_main." + _get_extension(language): response}


def _normalize_llm_output(data: dict) -> dict:
    """Normalize LLM output to ensure all enum values and field names match Pydantic model."""

    VIS_MAP = {
        "public": "+", "private": "-", "protected": "#",
        "+": "+", "-": "-", "#": "#",
    }

    VALID_STEREOTYPES = {"class", "interface", "abstract", "enum"}

    RELATION_TYPE_MAP = {
        "inheritance": "inheritance", "generalization": "inheritance",
        "extends": "inheritance", "composition": "composition",
        "aggregation": "aggregation", "association": "association",
        "realization": "realization", "implements": "realization",
        "dependency": "dependency", "depends": "dependency",
        "composite": "composition", "aggregate": "aggregation",
    }

    # Map alternate field names LLM might use → correct field name
    FIELD_ALIASES = {
        # Relation fields
        "source_id": "source", "target_id": "target",
        "from": "source", "to": "target",
        "from_id": "source", "to_id": "target",
        "source_mult": "multiplicity_source", "target_mult": "multiplicity_target",
        "source_multiplicity": "multiplicity_source", "target_multiplicity": "multiplicity_target",
        "mult_src": "multiplicity_source", "mult_tgt": "multiplicity_target",
        "label": "role_name",
        # Class fields
        "is_abstract_class": "stereotype",
        "class_name": "name",
    }

    import uuid as _uuid

    def walk(obj, parent_key=""):
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                # Remap known alias fields
                mapped_key = FIELD_ALIASES.get(k, k)
                if k == "visibility" and isinstance(v, str):
                    v = VIS_MAP.get(v.lower(), "+")
                elif mapped_key == "stereotype":
                    if isinstance(v, str) and v.lower() in VALID_STEREOTYPES:
                        v = v.lower()
                    else:
                        v = "class"
                elif k == "is_abstract_class" and v is True:
                    mapped_key = "stereotype"
                    v = "abstract"
                elif mapped_key == "type" and isinstance(v, str):
                    v = RELATION_TYPE_MAP.get(v.lower(), "association")
                elif k in ("is_static", "is_abstract") and v is None:
                    v = False
                elif k == "default_value" and v == "":
                    v = None
                result[mapped_key] = walk(v, mapped_key)
            # Auto-generate missing IDs for relations
            if parent_key == "relations" and "id" not in result:
                result["id"] = f"rel_{_uuid.uuid4().hex[:8]}"
            if parent_key == "classes" and "id" not in result:
                result["id"] = f"class_{_uuid.uuid4().hex[:8]}"
            return result
        elif isinstance(obj, list):
            return [walk(item, parent_key) for item in obj]
        return obj

    return walk(data)


async def optimize_uml(diagram: UmlDiagram, instructions: str = "") -> dict:
    """Ask LLM to optimize a UML diagram design."""
    prompt = f"""Analyze and optimize the following UML class diagram.

## Current Diagram (reference the exact field names and structure):
```json
{diagram.model_dump_json(indent=2)}
```

## User Instructions:
{instructions or "General design optimization: improve cohesion, reduce coupling, apply design patterns where appropriate."}

## CRITICAL RULES:
1. Use EXACTLY the same JSON field names as the input. Relations use "source"/"target" (NOT "from"/"to"/"source_id").
2. visibility values MUST be "+", "-", or "#" (NOT "public"/"private"/"protected").
3. stereotype values MUST be "class", "interface", "abstract", or "enum".
4. relation type values MUST be "inheritance", "composition", "aggregation", "association", "realization", or "dependency".
5. Every class and relation MUST have a unique "id" field.
6. PRESERVE all "note" fields on classes and relations — these contain business requirements.
7. PRESERVE "role_name", "multiplicity_source", "multiplicity_target" on relations.

## Output Format:
```json
{{
  "optimized": {{ COPY THE EXACT INPUT STRUCTURE }},
  "changes_summary": "brief summary",
  "diff": "what changed"
}}
```
Only output the JSON object, no other text.
"""
    response = await chat(
        prompt=prompt,
        system_prompt="You are an expert software architect specializing in UML design and design patterns. Always use +, -, # for visibility values.",
        temperature=0.5,
        max_tokens=8192,
    )
    try:
        cleaned = clean_llm_json_response(response)
        result = json.loads(cleaned)
        # Normalize all enum values from LLM output
        if "optimized" in result and isinstance(result["optimized"], dict):
            result["optimized"] = _normalize_llm_output(result["optimized"])
        return result
    except json.JSONDecodeError:
        return {
            "optimized": diagram.model_dump(),
            "changes_summary": "Unable to parse optimization result",
            "diff": response,
        }


async def fix_code(
    code_files: dict[str, str],
    test_results: str,
    language: str,
) -> dict[str, str]:
    """Ask LLM to fix code based on test failure feedback."""
    code_block = "\n\n".join(
        f"### {fname}\n```{language}\n{content}\n```"
        for fname, content in code_files.items()
    )
    prompt = f"""Fix the following {language} code based on the test results.

## Current Code:
{code_block}

## Test Results (failures):
{test_results}

## Requirements:
- Fix all failing tests.
- Return the corrected code as a JSON object mapping filenames to content.
- Only output the JSON object, no other text.
"""
    response = await chat(
        prompt=prompt,
        system_prompt=f"You are an expert {language} developer fixing failing tests.",
        temperature=0.3,
        max_tokens=8192,
    )
    try:
        cleaned = clean_llm_json_response(response)
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {f"fixed_{k}": v for k, v in code_files.items()}


def _get_extension(language: str) -> str:
    ext_map = {
        "python": "py", "java": "java", "typescript": "ts",
        "javascript": "js", "csharp": "cs", "cpp": "cpp",
        "go": "go", "rust": "rs", "ruby": "rb", "swift": "swift",
        "kotlin": "kt", "php": "php",
    }
    return ext_map.get(language, "txt")
