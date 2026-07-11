"""FastAPI dependency wiring.

Centralizing this here (instead of instantiating the LLM client inside
the endpoint) is what lets tests swap `get_assessment_service` for a
fake that doesn't call the real API (see tests/test_endpoint.py).
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
    """In-memory singleton: all requests share the same store, so a
    session created in /conversation/start is visible on the next call
    to /conversation/{id}/answer."""
    return SessionStore()