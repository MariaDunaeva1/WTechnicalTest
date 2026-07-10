"""Excepciones propias, para no filtrar excepciones del SDK del proveedor
hasta la capa de API. Así la capa API solo conoce estos tipos y decide el
status code adecuado, sin acoplarse al SDK de Anthropic/OpenAI."""


class LLMError(Exception):
    """Error genérico al comunicarse con el proveedor de LLM."""


class LLMTimeoutError(LLMError):
    """El proveedor no respondió dentro del timeout configurado."""


class LLMMalformedResponseError(LLMError):
    """El LLM respondió pero no en el formato estructurado esperado
    (tool call ausente o payload que no valida contra el schema)."""
