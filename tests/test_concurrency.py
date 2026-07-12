"""Concurrency behavior (Option C).

What we're demonstrating and why:
FastAPI/Starlette run each request in the same event loop; `async def`
endpoints don't block each other while awaiting I/O (like the LLM
call). The risk this test targets is state bleed: could two concurrent
conversations accidentally interfere with each other's session state
because of a shared SessionStore?

We simulate N concurrent full conversations (start -> 5 answers each)
using httpx.AsyncClient talking to the app in-process (no real network
hop, but the same ASGI request-handling path FastAPI uses in
production), and assert every session ends up with its own distinct,
correct set of 5 answers — none mixed with another session's.

Latency note: with the LLM mocked, this test doesn't measure real
external latency, only that our own concurrency handling (the
asyncio.Lock in SessionStore) doesn't serialize unrelated sessions or
corrupt state under concurrent load. Measuring real end-to-end latency
under concurrency would require running this against the live API,
which is exactly what the `evaluation` marked suite is for — this test
intentionally stays fast and free.
"""
import asyncio

import httpx
import pytest

from app.api.dependencies import get_assessment_service, get_session_store
from app.domain.conversation import SessionStore
from app.domain.schemas import AssessmentResponse, BigFiveProfile, DimensionScore, ResponseMetadata
from app.main import app

CONCURRENT_SESSIONS = 10


def _fake_profile_response() -> AssessmentResponse:
    dim = DimensionScore(score=3, rationale="Concurrency test rationale.")
    return AssessmentResponse(
        profile=BigFiveProfile(
            openness=dim, conscientiousness=dim, extraversion=dim,
            agreeableness=dim, neuroticism=dim,
        ),
        confidence=0.7,
        metadata=ResponseMetadata(model="fake-model", prompt_version="v1"),
    )


class _FakeService:
    async def assess(self, request):
        # Small artificial delay simulates a real LLM round-trip, so
        # concurrent requests genuinely overlap in time instead of
        # completing instantly and never actually running in parallel.
        await asyncio.sleep(0.05)
        return _fake_profile_response()


async def _run_full_conversation(client: httpx.AsyncClient, conversation_index: int) -> tuple[str, list[str]]:
    start = await client.post("/api/v1/conversation/start")
    session_id = start.json()["session_id"]

    submitted_answers = []
    for question_number in range(5):
        answer_text = f"conversation-{conversation_index}-answer-{question_number}"
        submitted_answers.append(answer_text)
        response = await client.post(
            f"/api/v1/conversation/{session_id}/answer",
            json={"text": answer_text},
        )
        assert response.status_code == 200

    return session_id, submitted_answers


@pytest.mark.asyncio
async def test_concurrent_conversations_do_not_leak_state_between_sessions():
    shared_store = SessionStore()
    app.dependency_overrides[get_assessment_service] = lambda: _FakeService()
    app.dependency_overrides[get_session_store] = lambda: shared_store

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            results = await asyncio.gather(*[
                _run_full_conversation(client, i) for i in range(CONCURRENT_SESSIONS)
            ])
    finally:
        app.dependency_overrides.clear()

    session_ids = [session_id for session_id, _ in results]
    assert len(set(session_ids)) == CONCURRENT_SESSIONS, "Each conversation must get its own unique session_id"

    for conversation_index, (session_id, submitted_answers) in enumerate(results):
        session = await shared_store.get(session_id)
        stored_texts = [a.text for a in session.answers]
        assert stored_texts == submitted_answers, (
            f"Session {session_id} has mismatched answers — possible state leak "
            f"from another concurrent conversation. Expected {submitted_answers}, got {stored_texts}"
        )