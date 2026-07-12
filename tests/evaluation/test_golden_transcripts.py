"""Evaluation harness: runs golden transcripts against the REAL LLM
provider and checks the resulting scores land in a defensible range.

This is intentionally separate from the regular test suite:
- It costs real API calls (money + latency), so it must not run on
  every `pytest` invocation, only when explicitly requested.
- It's non-deterministic by nature (LLM output varies slightly between
  calls) — that's exactly what it's designed to tolerate via ranges,
  but it means it shouldn't gate CI on every commit the same way a
  fast, deterministic unit test would.

Run explicitly with:
    pytest -m evaluation -v

Requires a real OPENAI_API_KEY in the environment / .env file.
"""
import pytest

from app.core.config import get_settings
from app.domain.assessment_service import AssessmentService
from app.domain.schemas import Answer, AssessmentRequest
from app.llm.client import BigFiveLLMClient
from tests.evaluation.golden_transcripts import GOLDEN_CASES


@pytest.fixture(scope="module")
def real_assessment_service() -> AssessmentService:
    settings = get_settings()
    llm_client = BigFiveLLMClient(settings)
    return AssessmentService(llm_client, settings)


@pytest.mark.evaluation
@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c.name for c in GOLDEN_CASES])
async def test_golden_case_scores_land_in_expected_range(case, real_assessment_service):
    request = AssessmentRequest(
        answers=[
            Answer(question_id=f"q{i}", text=text)
            for i, text in enumerate(case.answers)
        ]
    )

    result = await real_assessment_service.assess(request)

    failures = []
    for dimension, (low, high) in case.expected_ranges.items():
        actual_score = getattr(result.profile, dimension).score
        if not (low <= actual_score <= high):
            failures.append(f"{dimension}: expected {low}-{high}, got {actual_score}")

    assert not failures, (
        f"Case '{case.name}' produced unexpected scores: {failures}. "
        f"Full profile: {result.profile.model_dump()}"
    )

    assert 0.0 <= result.confidence <= 1.0