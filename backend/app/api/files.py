"""File operations API – new, open, save, export, browse, review."""

import os
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import PlainTextResponse

from app.models.uml import UmlDiagram, ExportRequest
from app.services.file_service import (
    save_diagram, load_diagram, list_diagrams, export_markdown,
)
from app.core.config import get_settings
from app.core.auth import require_auth
from app.core.security import safe_path, resolve_path, sanitize_path_segment

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/list")
async def list_files():
    """List all saved UML diagram files."""
    return {"files": list_diagrams()}


@router.post("/save", dependencies=[Depends(require_auth)])
async def save_file(diagram: UmlDiagram, filename: str = ""):
    """Save a UML diagram to a .uml file. Optional custom filename."""
    filepath = None
    if filename:
        # Sanitize filename — strip path and dangerous chars
        safe_name = sanitize_path_segment(filename.replace(".uml", ""))
        if safe_name:
            safe_name += ".uml"
            filepath = os.path.join(get_settings().uml_dir, safe_name)
    filepath = save_diagram(diagram, filepath)
    return {"success": True, "filepath": filepath, "filename": os.path.basename(filepath)}


@router.get("/open")
async def open_file(filepath: str):
    """Open a saved UML diagram file. Only allows .uml files within the project."""
    # Validate path stays within project
    try:
        safe = safe_path(filepath)
    except HTTPException:
        raise HTTPException(status_code=403, detail="Access denied")
    if not safe.endswith(".uml"):
        raise HTTPException(status_code=400, detail="Only .uml files can be opened")
    if not os.path.exists(safe):
        raise HTTPException(status_code=404, detail="File not found")
    diagram = load_diagram(safe)
    return {"diagram": diagram.model_dump()}


@router.post("/new")
async def new_diagram(name: str = "Untitled"):
    """Create a new empty UML diagram."""
    diagram = UmlDiagram(name=name)
    return {"diagram": diagram.model_dump()}


@router.post("/export/markdown", response_class=PlainTextResponse)
async def export_to_markdown(req: ExportRequest):
    """Export UML diagram to Markdown design document."""
    md = export_markdown(req.diagram)
    return md


@router.post("/upload/excel", dependencies=[Depends(require_auth)])
async def upload_excel(file: UploadFile = File(...)):
    """Upload an Excel test case file."""
    import pandas as pd
    content = await file.read()

    # Sanitize filename — strip path components to prevent traversal
    raw_name = file.filename or "testCase.xlsx"
    safe_name = os.path.basename(raw_name)
    if not safe_name or safe_name.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # Save uploaded file
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    filepath = os.path.join(settings.upload_dir, safe_name)
    with open(filepath, "wb") as f:
        f.write(content)

    # Parse Excel
    xls = pd.ExcelFile(filepath)
    sheets = {}
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        sheets[sheet_name] = df.fillna("").to_dict(orient="records")

    return {"filename": file.filename, "sheets": sheets, "sheet_names": xls.sheet_names}


# ── Directory browsing ──────────────────────────────────

@router.get("/browse")
async def browse_directory(path: str = "", safe: bool = True):
    """Browse a directory. Returns subdirectories and .uml files.

    Set safe=false to allow browsing any path on disk (pipeline directory selection).
    """
    settings = get_settings()
    path_resolver = safe_path if safe else resolve_path

    if not path:
        base = os.path.abspath(settings.uml_dir)
    else:
        try:
            base = path_resolver(path)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid path")

    if not os.path.exists(base) or not os.path.isdir(base):
        base = os.path.abspath(settings.uml_dir)

    try:
        items = os.listdir(base)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    dirs = []
    files = []
    for name in sorted(items):
        full = os.path.join(base, name)
        if os.path.isdir(full) and not name.startswith("."):
            dirs.append({"name": name, "path": full.replace("\\", "/")})
        elif name.endswith(".uml"):
            stat = os.stat(full)
            files.append({
                "name": name,
                "path": full.replace("\\", "/"),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    # Parent navigation: always allowed when unrestricted; checked when restricted
    parent = ""
    if safe:
        project_root = os.path.abspath(os.path.join(settings.uml_dir, "..", ".."))
        if base != project_root and base != os.path.abspath(settings.uml_dir):
            parent_dir = os.path.dirname(base)
            try:
                safe_path(parent_dir)
                parent = parent_dir.replace("\\", "/")
            except HTTPException:
                parent = ""
    else:
        parent_dir = os.path.dirname(base)
        if parent_dir != base:
            parent = parent_dir.replace("\\", "/")

    return {
        "current": base.replace("\\", "/"),
        "parent": parent,
        "dirs": dirs,
        "files": files,
    }


# ── Review saving ───────────────────────────────────────

class ReviewRequest(BaseModel):
    action: str  # "accept" or "reject"
    comment: str = ""
    requirements: str = ""
    original_name: str = ""
    optimized_name: str = ""
    timestamp: str = ""

@router.post("/save-review", dependencies=[Depends(require_auth)])
async def save_review(req: ReviewRequest):
    """Save optimization review to dev_review.txt."""
    settings = get_settings()
    review_file = os.path.join(settings.uml_dir, "..", "dev_review.txt")
    review_file = os.path.abspath(review_file)

    ts = req.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    action_label = "接受" if req.action == "accept" else "拒绝"

    entry = f"""============================================================
[{ts}] 评审结果: {action_label}
优化需求: {req.requirements if req.requirements else '(无)'}
原始版本: {req.original_name}
优化版本: {req.optimized_name}
评审意见: {req.comment if req.comment else '(无)'}
============================================================
"""

    with open(review_file, "a", encoding="utf-8") as f:
        f.write(entry)

    return {"success": True, "file": review_file}


# ── Generated code management ───────────────────────────

class SaveGeneratedRequest(BaseModel):
    project_name: str = "project"
    language: str = "python"
    source_files: dict[str, str] = {}  # filename -> content
    test_files: dict[str, str] = {}    # filename -> content


@router.post("/save-generated", dependencies=[Depends(require_auth)])
async def save_generated_code(req: SaveGeneratedRequest):
    """Save generated source and test code to generated/ folder."""
    settings = get_settings()
    base = os.path.abspath(os.path.join(settings.uml_dir, "..", "..", "generated"))

    # Sanitize project_name and language to prevent path traversal
    safe_project = sanitize_path_segment(req.project_name) or "project"
    safe_lang = sanitize_path_segment(req.language) or "python"

    # Create project folders
    src_dir = os.path.join(base, "src", safe_project, safe_lang)
    test_dir = os.path.join(base, "test", safe_project, safe_lang)
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)

    saved = {"src": [], "test": []}

    for fname, content in req.source_files.items():
        safe_fname = os.path.basename(fname)  # strip any directory components
        if not safe_fname or safe_fname.startswith("."):
            continue
        fp = os.path.join(src_dir, safe_fname)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        saved["src"].append(safe_fname)

    for fname, content in req.test_files.items():
        safe_fname = os.path.basename(fname)
        if not safe_fname or safe_fname.startswith("."):
            continue
        fp = os.path.join(test_dir, safe_fname)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        saved["test"].append(safe_fname)

    return {
        "success": True,
        "src_dir": src_dir.replace("\\", "/"),
        "test_dir": test_dir.replace("\\", "/"),
        "saved": saved,
    }


@router.get("/list-generated")
async def list_generated_code():
    """List all generated code projects."""
    settings = get_settings()
    base = os.path.abspath(os.path.join(settings.uml_dir, "..", "..", "generated"))

    def list_dir(path):
        if not os.path.exists(path):
            return []
        result = []
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f).replace("\\", "/")
                result.append({
                    "name": f,
                    "path": fp,
                    "size": os.path.getsize(fp),
                    "modified": datetime.fromtimestamp(os.path.getmtime(fp)).isoformat(),
                })
        return result

    return {
        "src": list_dir(os.path.join(base, "src")),
        "test": list_dir(os.path.join(base, "test")),
        "base": base.replace("\\", "/"),
    }
