"""Domain layer: orchestrates profile inference.

Knows nothing about HTTP (that's api/) or provider SDK details (that's
llm/). Its job is: take the validated request, ask the LLM client for
the profile, and validate the raw response against our contract before
returning it. If the LLM returns something that doesn't fit the schema,
we treat it the same as a malformed response — we don't let a Pydantic
ValidationError leak out unhandled.
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
                f"LLM output does not match the BigFiveProfile schema: {exc}"
            ) from exc

        if confidence is None:
            raise LLMMalformedResponseError("LLM output is missing 'confidence'")

        return AssessmentResponse(
            profile=profile,
            confidence=confidence,
            metadata=ResponseMetadata(
                model=self._settings.llm_model,
                prompt_version=self._settings.prompt_version,
            ),
        )