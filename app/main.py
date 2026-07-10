import logging

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=settings.log_level,
    format='{"level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
)

app = FastAPI(
    title="Wiselook Big Five Assessment Service",
    version="0.1.0",
    description="Infiere un perfil de personalidad Big Five (OCEAN) a partir de respuestas de texto.",
)

app.include_router(router, prefix="/api/v1")