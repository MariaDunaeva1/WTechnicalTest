"""Wiring de dependencias para FastAPI.

Centralizar esto aquí (en vez de instanciar el cliente LLM dentro del
endpoint) es lo que permite en los tests sustituir `get_assessment_service`
por un fake que no llama a la API real (ver tests/test_endpoint.py).
"""
from functools import lru_cache

from app.core.config import get_settings
from app.domain.assessment_service import AssessmentService
from app.domain.conversation import SessionStore
from app.llm.client import BigFiveLLMClient


@lru_cache
def get_assessment_service() -> AssessmentService:
    settings = get_settings()
    llm_client = BigFiveLLMClient(settings)
    return AssessmentService(llm_client, settings)


@lru_cache
def get_session_store() -> SessionStore:
    """Singleton in-memory: todas las requests comparten el mismo store,
    así una sesión creada en /conversation/start es visible en la
    siguiente llamada a /conversation/{id}/answer."""
    return SessionStore()
