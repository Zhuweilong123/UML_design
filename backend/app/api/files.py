"""File operations API – new, open, save, export, browse, review."""

import os
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import PlainTextResponse

from app.models.uml import UmlDiagram, ExportRequest
from app.services.file_service import (
    save_diagram, load_diagram, list_diagrams, export_markdown,
)
from app.core.config import get_settings

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/list")
async def list_files():
    """List all saved UML diagram files."""
    return {"files": list_diagrams()}


@router.post("/save")
async def save_file(diagram: UmlDiagram, filename: str = ""):
    """Save a UML diagram to a .uml file. Optional custom filename."""
    filepath = None
    if filename:
        # Ensure .uml extension
        if not filename.endswith(".uml"):
            filename += ".uml"
        filepath = os.path.join(get_settings().uml_dir, filename)
    filepath = save_diagram(diagram, filepath)
    return {"success": True, "filepath": filepath, "filename": os.path.basename(filepath)}


@router.get("/open")
async def open_file(filepath: str):
    """Open a saved UML diagram file."""
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    diagram = load_diagram(filepath)
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


@router.post("/upload/excel")
async def upload_excel(file: UploadFile = File(...)):
    """Upload an Excel test case file."""
    import pandas as pd
    content = await file.read()

    # Save uploaded file
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    filepath = os.path.join(settings.upload_dir, file.filename or "testCase.xlsx")
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
async def browse_directory(path: str = ""):
    """Browse a directory. Returns subdirectories and .uml files."""
    settings = get_settings()
    base = path if path else settings.uml_dir
    if not os.path.isabs(base):
        base = os.path.abspath(base)
    if not os.path.exists(base):
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

    parent = os.path.dirname(base).replace("\\", "/") if base != os.path.abspath(settings.uml_dir) else ""

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

@router.post("/save-review")
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


@router.post("/save-generated")
async def save_generated_code(req: SaveGeneratedRequest):
    """Save generated source and test code to generated/ folder."""
    settings = get_settings()
    base = os.path.abspath(os.path.join(settings.uml_dir, "..", "..", "generated"))

    # Create project folders
    src_dir = os.path.join(base, "src", req.project_name, req.language)
    test_dir = os.path.join(base, "test", req.project_name, req.language)
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(test_dir, exist_ok=True)

    saved = {"src": [], "test": []}

    for fname, content in req.source_files.items():
        fp = os.path.join(src_dir, fname)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        saved["src"].append(fname)

    for fname, content in req.test_files.items():
        fp = os.path.join(test_dir, fname)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(content)
        saved["test"].append(fname)

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
