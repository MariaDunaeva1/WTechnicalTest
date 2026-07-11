"""Application configuration, loaded from environment variables.

We use pydantic-settings for validated, typed config instead of reading
os.environ by hand throughout the codebase.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # --- LLM provider ---
    openai_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    llm_max_tokens: int = 1024
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 3

    # --- App ---
    app_env: str = "local"
    log_level: str = "INFO"

    # Active prompt name/version. See app/llm/prompts.py
    prompt_version: str = "v1"


@lru_cache
def get_settings() -> Settings:
    """Cached settings (singleton) so we don't re-read the environment on every request."""
    return Settings()