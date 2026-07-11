"""Service data contract (Pydantic).

Design:
- `AssessmentRequest`: 5 free-text answers from the user.
- `BigFiveProfile`: inferred profile, with score 1-5 + rationale per dimension.
- `AssessmentResponse`: wraps the profile with metadata (model, prompt
  version, timestamp) for traceability — important if you later change
  the prompt and need to compare results across versions.
"""
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Dimension(str, Enum):
    OPENNESS = "openness"
    CONSCIENTIOUSNESS = "conscientiousness"
    EXTRAVERSION = "extraversion"
    AGREEABLENESS = "agreeableness"
    NEUROTICISM = "neuroticism"


class Answer(BaseModel):
    """A single answer from the user to a questionnaire question."""

    question_id: str = Field(..., min_length=1, description="Question identifier")
    text: str = Field(..., min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Answer cannot be blank")
        return v.strip()


class AssessmentRequest(BaseModel):
    """Input payload: exactly 5 answers for Option A."""

    answers: list[Answer] = Field(..., min_length=5, max_length=5)


class DimensionScore(BaseModel):
    """Score for one OCEAN dimension, validated in range 1-5."""

    score: int = Field(..., ge=1, le=5)
    rationale: str = Field(..., min_length=1, max_length=500)


class BigFiveProfile(BaseModel):
    openness: DimensionScore
    conscientiousness: DimensionScore
    extraversion: DimensionScore
    agreeableness: DimensionScore
    neuroticism: DimensionScore


class ResponseMetadata(BaseModel):
    model: str
    prompt_version: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AssessmentResponse(BaseModel):
    profile: BigFiveProfile
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: ResponseMetadata


# --- Option B: conversational flow contract ---

class ConversationStartResponse(BaseModel):
    session_id: str
    question_id: str
    question_text: str
    question_number: int
    total_questions: int


class AnswerSubmission(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Answer cannot be blank")
        return v.strip()


class ConversationNextResponse(BaseModel):
    """Returned while the conversation is still in progress."""

    session_id: str
    status: str = "in_progress"
    question_id: str
    question_text: str
    question_number: int
    total_questions: int


class ConversationCompletedResponse(BaseModel):
    """Returned when the last answer closes the conversation."""

    session_id: str
    status: str = "completed"
    result: AssessmentResponse