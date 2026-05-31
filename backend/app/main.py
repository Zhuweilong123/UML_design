"""FastAPI application entry point."""

import os
os.environ.setdefault("PYTHONUTF8", "1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import get_settings
from app.api.files import router as files_router
from app.api.llm import router as llm_router
from app.api.pipeline import router as pipeline_router
from app.api.testhub import router as testhub_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files_router)
app.include_router(llm_router)
app.include_router(pipeline_router)
app.include_router(testhub_router)

# Static files (uploaded files)
os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.uml_dir, exist_ok=True)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.app_name}", "docs": "/api/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.debug)
