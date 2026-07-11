from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="Wiselook Big Five Assessment Service",
    version="0.1.0",
    description="Infers a Big Five (OCEAN) personality profile from text answers.",
)

app.include_router(router, prefix="/api/v1")