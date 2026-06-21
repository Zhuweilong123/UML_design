"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # DeepSeek LLM
    deepseek_api_key: str = "sk-3b6b0eaa3b374234a8047e0c60844b24"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

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
