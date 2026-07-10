"""Configuración de la aplicación, cargada desde variables de entorno.

Usamos pydantic-settings para tener validación y tipado de la config,
en vez de leer os.environ a mano por todo el código.
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

    # Nombre/versión del prompt activo. Ver app/llm/prompts.py
    prompt_version: str = "v1"


@lru_cache
def get_settings() -> Settings:
    """Settings cacheadas (singleton) para no releer el entorno en cada request."""
    return Settings()
