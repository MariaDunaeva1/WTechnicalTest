import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_assessment_service, get_session_store
from app.core.exceptions import LLMError, LLMMalformedResponseError, LLMTimeoutError
from app.domain.assessment_service import AssessmentService
from app.domain.conversation import (
    ConversationStatus,
    SessionAlreadyCompletedError,
    SessionNotFoundError,
    SessionStore,
)
from app.domain.questions import get_question, total_questions
from app.domain.schemas import (
    AnswerSubmission,
    Answer,
    AssessmentRequest,
    AssessmentResponse,
    ConversationCompletedResponse,
    ConversationNextResponse,
    ConversationStartResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/assess", response_model=AssessmentResponse)
async def assess(
    request: AssessmentRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentResponse:
    """Infer a Big Five profile from 5 text answers."""
    try:
        return await service.assess(request)
    except LLMTimeoutError as exc:
        logger.warning("assess_timeout", extra={"error": str(exc)})
        raise HTTPException(status_code=504, detail="The LLM provider took too long to respond") from exc
    except LLMMalformedResponseError as exc:
        logger.error("assess_malformed_llm_output", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="The LLM returned an invalid response") from exc
    except LLMError as exc:
        logger.error("assess_llm_error", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="Error communicating with the LLM provider") from exc


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# --- Option B: multi-turn conversational flow ---

@router.post("/conversation/start", response_model=ConversationStartResponse)
async def start_conversation(
    store: SessionStore = Depends(get_session_store),
) -> ConversationStartResponse:
    session = await store.create()
    first_question = get_question(0)
    logger.info("conversation_started", extra={"session_id": session.session_id})
    return ConversationStartResponse(
        session_id=session.session_id,
        question_id=first_question.question_id,
        question_text=first_question.text,
        question_number=1,
        total_questions=total_questions(),
    )


@router.post(
    "/conversation/{session_id}/answer",
    response_model=ConversationNextResponse | ConversationCompletedResponse,
)
async def submit_answer(
    session_id: str,
    submission: AnswerSubmission,
    store: SessionStore = Depends(get_session_store),
    service: AssessmentService = Depends(get_assessment_service),
):
    try:
        current = await store.get(session_id)
        if current.status == ConversationStatus.COMPLETED:
            raise SessionAlreadyCompletedError(f"Session already completed: {session_id}")
        answered_question = get_question(current.next_question_index)
        answer = Answer(question_id=answered_question.question_id, text=submission.text)
        session = await store.add_answer(session_id, answer)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SessionAlreadyCompletedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    logger.info(
        "answer_received",
        extra={"session_id": session_id, "question_number": len(session.answers)},
    )

    if not session.is_complete():
        next_question = get_question(session.next_question_index)
        return ConversationNextResponse(
            session_id=session_id,
            question_id=next_question.question_id,
            question_text=next_question.text,
            question_number=len(session.answers) + 1,
            total_questions=total_questions(),
        )

    # Last answer: closes the conversation and infers the profile.
    logger.info("conversation_completed", extra={"session_id": session_id})
    try:
        result = await service.assess(AssessmentRequest(answers=session.answers))
    except LLMTimeoutError as exc:
        logger.warning("assess_timeout", extra={"session_id": session_id, "error": str(exc)})
        raise HTTPException(status_code=504, detail="The LLM provider took too long to respond") from exc
    except LLMMalformedResponseError as exc:
        logger.error("assess_malformed_llm_output", extra={"session_id": session_id, "error": str(exc)})
        raise HTTPException(status_code=502, detail="The LLM returned an invalid response") from exc
    except LLMError as exc:
        logger.error("assess_llm_error", extra={"session_id": session_id, "error": str(exc)})
        raise HTTPException(status_code=502, detail="Error communicating with the LLM provider") from exc

    return ConversationCompletedResponse(session_id=session_id, result=result)