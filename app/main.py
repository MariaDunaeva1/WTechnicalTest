import uuid

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware

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


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Assigns a unique request_id to every HTTP request and returns it
    in the `X-Request-ID` header. This is the observability primitive
    that lets you correlate all log lines belonging to a single HTTP
    request (as opposed to session_id, which correlates lines across
    an entire multi-turn conversation)."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)

app.include_router(router, prefix="/api/v1")