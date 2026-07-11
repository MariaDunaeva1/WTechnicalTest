"""Logging estructurado en JSON.

Usamos el logging estándar de Python (no traemos structlog como
dependencia extra) pero con un formatter que vuelca cualquier campo
`extra={...}` que pasemos al logger, así los logs quedan correlacionados
por `session_id` sin acoplarnos a una librería más.
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
        # Cualquier atributo añadido vía `extra=` se incluye tal cual
        # (p.ej. session_id, attempt, status) — esto es lo que permite
        # filtrar/correlacionar logs de una misma conversación.
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
