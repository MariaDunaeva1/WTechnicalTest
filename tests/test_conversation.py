"""Tests for the conversational flow: start -> 5x answer -> final result.

Same as test_endpoint.py, we mock AssessmentService to avoid calling the
real API. SessionStore is real (in-memory) though, since it's our own
logic that we want to actually test, not a system boundary.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_assessment_service, get_session_store
from app.domain.conversation import SessionStore
from app.domain.schemas import AssessmentResponse, BigFiveProfile, DimensionScore, ResponseMetadata
from app.main import app


def _fake_profile_response() -> AssessmentResponse:
    dim = DimensionScore(score=3, rationale="Test rationale.")
    return AssessmentResponse(
        profile=BigFiveProfile(
            openness=dim, conscientiousness=dim, extraversion=dim,
            agreeableness=dim, neuroticism=dim,
        ),
        confidence=0.75,
        metadata=ResponseMetadata(model="fake-model", prompt_version="v1"),
    )


class _FakeService:
    async def assess(self, request):
        return _fake_profile_response()


@pytest.fixture
def client():
    # Important: a single SessionStore instance per test. If the override
    # created a new SessionStore on every call, each request would see an
    # empty store and the session would "disappear" between steps.
    shared_store = SessionStore()
    app.dependency_overrides[get_assessment_service] = lambda: _FakeService()
    app.dependency_overrides[get_session_store] = lambda: shared_store
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_full_conversation_flow_completes_with_profile(client):
    start = client.post("/api/v1/conversation/start")
    assert start.status_code == 200
    body = start.json()
    session_id = body["session_id"]
    assert body["question_number"] == 1
    assert body["total_questions"] == 5

    # Answer the first 4 questions: each one should return the next one.
    for expected_next_number in range(2, 6):
        response = client.post(
            f"/api/v1/conversation/{session_id}/answer",
            json={"text": "Test answer with enough content."},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "in_progress"
        assert payload["question_number"] == expected_next_number

    # The 5th answer closes the conversation and returns the profile.
    final = client.post(
        f"/api/v1/conversation/{session_id}/answer",
        json={"text": "Last test answer."},
    )
    assert final.status_code == 200
    final_body = final.json()
    assert final_body["status"] == "completed"
    assert final_body["result"]["profile"]["openness"]["score"] == 3


def test_answer_to_unknown_session_returns_404(client):
    response = client.post(
        "/api/v1/conversation/does-not-exist/answer",
        json={"text": "answer"},
    )
    assert response.status_code == 404


def test_answer_after_completion_returns_409(client):
    start = client.post("/api/v1/conversation/start")
    session_id = start.json()["session_id"]

    for _ in range(5):
        client.post(
            f"/api/v1/conversation/{session_id}/answer",
            json={"text": "Test answer with enough content."},
        )

    extra = client.post(
        f"/api/v1/conversation/{session_id}/answer",
        json={"text": "one extra answer"},
    )
    assert extra.status_code == 409


def test_blank_answer_is_rejected(client):
    start = client.post("/api/v1/conversation/start")
    session_id = start.json()["session_id"]

    response = client.post(
        f"/api/v1/conversation/{session_id}/answer",
        json={"text": "   "},
    )
    assert response.status_code == 422