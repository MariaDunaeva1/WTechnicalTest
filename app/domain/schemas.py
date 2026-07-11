"""Contrato de datos del servicio (Pydantic).

Diseño:
- `AssessmentRequest`: 5 respuestas de texto libre del usuario.
- `BigFiveProfile`: perfil inferido, con score 1-5 + rationale por dimensión.
- `AssessmentResponse`: envuelve el perfil con metadata (modelo, versión de
  prompt, timestamp) para trazabilidad — importante si luego cambias el
  prompt y necesitas comparar resultados entre versiones.
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
    """Una respuesta individual del usuario a una pregunta del cuestionario."""

    question_id: str = Field(..., min_length=1, description="Identificador de la pregunta")
    text: str = Field(..., min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("La respuesta no puede estar vacía")
        return v.strip()


class AssessmentRequest(BaseModel):
    """Payload de entrada: exactamente 5 respuestas para Option A."""

    answers: list[Answer] = Field(..., min_length=5, max_length=5)


class DimensionScore(BaseModel):
    """Score de una dimensión OCEAN, validado en rango 1-5."""

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


# --- Option B: contrato del flujo conversacional ---

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
            raise ValueError("La respuesta no puede estar vacía")
        return v.strip()


class ConversationNextResponse(BaseModel):
    """Se devuelve mientras la conversación sigue en curso."""

    session_id: str
    status: str = "in_progress"
    question_id: str
    question_text: str
    question_number: int
    total_questions: int


class ConversationCompletedResponse(BaseModel):
    """Se devuelve cuando la última respuesta cierra la conversación."""

    session_id: str
    status: str = "completed"
    result: AssessmentResponse
