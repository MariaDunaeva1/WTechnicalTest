import logging

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_assessment_service
from app.core.exceptions import LLMError, LLMMalformedResponseError, LLMTimeoutError
from app.domain.assessment_service import AssessmentService
from app.domain.schemas import AssessmentRequest, AssessmentResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/assess", response_model=AssessmentResponse)
async def assess(
    request: AssessmentRequest,
    service: AssessmentService = Depends(get_assessment_service),
) -> AssessmentResponse:
    """Infiera un perfil Big Five a partir de 5 respuestas de texto."""
    try:
        return await service.assess(request)
    except LLMTimeoutError as exc:
        logger.warning("assess_timeout", extra={"error": str(exc)})
        raise HTTPException(status_code=504, detail="El proveedor LLM tardó demasiado en responder") from exc
    except LLMMalformedResponseError as exc:
        logger.error("assess_malformed_llm_output", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="El LLM devolvió una respuesta inválida") from exc
    except LLMError as exc:
        logger.error("assess_llm_error", extra={"error": str(exc)})
        raise HTTPException(status_code=502, detail="Error al comunicarse con el proveedor LLM") from exc


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}