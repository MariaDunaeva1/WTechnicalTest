"""Structured JSON logging.

We use Python's standard logging (no extra structlog dependency) with a
formatter that dumps any `extra={...}` field passed to the logger, so
logs stay correlated by `session_id` without adding another library.
"""
import json
import logging

_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Any attribute added via `extra=` is included as-is (e.g.
        # session_id, attempt, status) — this is what allows filtering /
        # correlating logs from the same conversation.
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and key != "message":
                payload[key] = value
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)