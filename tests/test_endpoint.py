"""Test for the /assess endpoint with the LLM mocked.

We don't call the real Anthropic API in tests: we swap AssessmentService
for a fake via FastAPI's dependency override. This tests the HTTP
contract (status codes, JSON shape, error handling) fast, deterministically,
and with no cost or network calls.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_assessment_service
from app.core.exceptions import LLMTimeoutError
from app.domain.schemas import AssessmentResponse, BigFiveProfile, DimensionScore, ResponseMetadata
from app.main import app

VALID_PAYLOAD = {
    "answers": [
        {"question_id": f"q{i}", "text": f"Sample answer number {i}."}
        for i in range(1, 6)
    ]
}


def _fake_profile_response() -> AssessmentResponse:
    dim = DimensionScore(score=4, rationale="Sample test rationale.")
    return AssessmentResponse(
        profile=BigFiveProfile(
            openness=dim,
            conscientiousness=dim,
            extraversion=dim,
            agreeableness=dim,
            neuroticism=dim,
        ),
        confidence=0.8,
        metadata=ResponseMetadata(model="fake-model", prompt_version="v1"),
    )


class _FakeServiceOk:
    async def assess(self, request):
        return _fake_profile_response()


class _FakeServiceTimeout:
    async def assess(self, request):
        raise LLMTimeoutError("simulated timeout")


@pytest.fixture
def client_with_fake_service():
    app.dependency_overrides[get_assessment_service] = lambda: _FakeServiceOk()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_assess_returns_valid_profile(client_with_fake_service):
    response = client_with_fake_service.post("/api/v1/assess", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["openness"]["score"] == 4
    assert 0 <= body["confidence"] <= 1
    assert body["metadata"]["prompt_version"] == "v1"


def test_assess_rejects_wrong_number_of_answers(client_with_fake_service):
    bad_payload = {"answers": VALID_PAYLOAD["answers"][:3]}
    response = client_with_fake_service.post("/api/v1/assess", json=bad_payload)

    assert response.status_code == 422


def test_assess_maps_llm_timeout_to_504():
    app.dependency_overrides[get_assessment_service] = lambda: _FakeServiceTimeout()
    with TestClient(app) as c:
        response = c.post("/api/v1/assess", json=VALID_PAYLOAD)
    app.dependency_overrides.clear()

    assert response.status_code == 504


def test_health_endpoint():
    with TestClient(app) as c:
        response = c.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}