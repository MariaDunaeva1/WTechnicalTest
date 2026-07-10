"""Capa de dominio: orquesta la inferencia del perfil.

No sabe nada de HTTP (eso es de api/) ni de detalles del SDK del proveedor
(eso es de llm/). Su trabajo es: coger el request validado, pedir al
cliente LLM el perfil, y validar la respuesta cruda contra nuestro
contrato antes de devolverla. Si el LLM devuelve algo que no encaja en el
schema, lo tratamos igual que una respuesta malformada, no dejamos que un
ValidationError de Pydantic se escape sin más.
"""
import logging

from pydantic import ValidationError

from app.core.config import Settings
from app.core.exceptions import LLMMalformedResponseError
from app.domain.schemas import AssessmentRequest, AssessmentResponse, BigFiveProfile, ResponseMetadata
from app.llm.client import BigFiveLLMClient

logger = logging.getLogger(__name__)


class AssessmentService:
    def __init__(self, llm_client: BigFiveLLMClient, settings: Settings):
        self._llm_client = llm_client
        self._settings = settings

    async def assess(self, request: AssessmentRequest) -> AssessmentResponse:
        answers = [(a.question_id, a.text) for a in request.answers]

        raw = await self._llm_client.infer_profile(answers)

        confidence = raw.pop("confidence", None)
        try:
            profile = BigFiveProfile.model_validate(raw)
        except ValidationError as exc:
            logger.error("llm_output_failed_validation", extra={"raw": raw})
            raise LLMMalformedResponseError(
                f"La salida del LLM no cumple el schema BigFiveProfile: {exc}"
            ) from exc

        if confidence is None:
            raise LLMMalformedResponseError("La salida del LLM no incluye 'confidence'")

        return AssessmentResponse(
            profile=profile,
            confidence=confidence,
            metadata=ResponseMetadata(
                model=self._settings.llm_model,
                prompt_version=self._settings.prompt_version,
            ),
        )
