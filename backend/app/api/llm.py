"""LLM integration API – code generation, UML optimization, chat."""

from fastapi import APIRouter, HTTPException

from app.models.uml import (
    LlmRequest, LlmResponse,
    CodeGenRequest, CodeGenResponse,
    UmlOptimizeRequest, UmlOptimizeResponse,
)
from app.services.llm_service import chat
from app.services.code_generator import (
    SUPPORTED_LANGUAGES, generate_code, optimize_uml,
)

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.post("/chat", response_model=LlmResponse)
async def llm_chat(req: LlmRequest):
    """Send a prompt to the LLM and get a response."""
    content = await chat(
        prompt=req.prompt,
        system_prompt=req.system_prompt,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
    )
    return LlmResponse(content=content)


@router.get("/languages")
async def get_languages():
    """Get the list of supported programming languages."""
    return {"languages": SUPPORTED_LANGUAGES}


@router.post("/generate-code", response_model=CodeGenResponse)
async def generate_code_endpoint(req: CodeGenRequest):
    """Generate code from a UML diagram for a specific language."""
    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {req.language}. Supported: {SUPPORTED_LANGUAGES}",
        )
    files = await generate_code(req.diagram, req.language)
    return CodeGenResponse(language=req.language, files=files)


@router.post("/optimize-uml", response_model=UmlOptimizeResponse)
async def optimize_uml_endpoint(req: UmlOptimizeRequest):
    """Ask LLM to analyze and optimize a UML diagram design."""
    import traceback
    try:
        result = await optimize_uml(req.diagram, req.instructions)

        from app.models.uml import UmlDiagram as UD
        optimized = UD(**result.get("optimized", req.diagram.model_dump()))

        return UmlOptimizeResponse(
            original=req.diagram,
            optimized=optimized,
            changes_summary=result.get("changes_summary", ""),
            diff=result.get("diff", ""),
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}")
