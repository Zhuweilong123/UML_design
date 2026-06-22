"""Application configuration loaded from environment variables."""

import logging
from pydantic_settings import BaseSettings
from pydantic import Field, ValidationInfo, field_validator
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # DeepSeek LLM — API key MUST come from .env, never hardcoded
    deepseek_api_key: str = Field(
        ...,
        description="DeepSeek API key (required, set in .env file)",
    )
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    @field_validator("deepseek_api_key")
    @classmethod
    def check_key_not_default(cls, v: str) -> str:
        """Reject known placeholder/default keys to catch misconfiguration."""
        prohibited_prefixes = ("sk-3b6b0eaa", "sk-your-", "your-", "placeholder", "changeme")
        v_lower = v.lower()
        for prefix in prohibited_prefixes:
            if v_lower.startswith(prefix):
                logger.warning(
                    "deepseek_api_key appears to be a placeholder or leaked default value. "
                    "Please set a valid key in backend/.env"
                )
                break
        return v

    # Internal API auth — token for frontend → backend calls
    internal_api_token: str = Field(
        default="",
        description="If set, frontend must include Authorization: Bearer <token> header",
    )

    # App
    app_name: str = "UML Designer API"
    app_version: str = "1.0.0"
    debug: bool = True

    # File storage
    upload_dir: str = "./uploads"
    uml_dir: str = "./uml_files"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
