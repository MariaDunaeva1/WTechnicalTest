from functools import lru_cache

from app.core.config import get_settings
from app.domain.assessment_service import AssessmentService
from app.llm.client import BigFiveLLMClient


@lru_cache
def get_assessment_service() -> AssessmentService:
    settings = get_settings()
    llm_client = BigFiveLLMClient(settings)
    return AssessmentService(llm_client, settings)