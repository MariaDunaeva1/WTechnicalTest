"""Wrapper async del cliente OpenAI.

Responsabilidad única: dado un conjunto de respuestas, llamar al LLM con
salida estructurada (tool use) y devolver el bloque de input de la tool
como dict crudo. La validación de ese dict contra nuestro contrato
(Pydantic) vive en domain/, no aquí — este módulo solo sabe hablar con el
proveedor.
"""
import asyncio
import logging

import openai

from app.core.config import Settings
from app.core.exceptions import LLMMalformedResponseError, LLMTimeoutError, LLMError
from app.llm.prompts import PROMPT_REGISTRY, build_user_prompt

logger = logging.getLogger(__name__)

TOOL_NAME = "submit_big_five_profile"


class BigFiveLLMClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = openai.AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds
        )

    async def infer_profile(self, answers: list[tuple[str, str]]) -> dict:
        """Llama al LLM y devuelve el input de la tool call como dict.

        Reintenta con backoff exponencial ante errores transitorios
        (timeout, rate limit, error 5xx del proveedor). No reintenta ante
        errores de autenticación o de payload (4xx de nuestro lado), que
        no se van a arreglar solos.
        """
        prompt = PROMPT_REGISTRY[self._settings.prompt_version]
        user_message = build_user_prompt(answers)

        last_error: Exception | None = None
        for attempt in range(1, self._settings.llm_max_retries + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=self._settings.llm_model,
                    max_tokens=self._settings.llm_max_tokens,
                    messages=[
                        {"role": "system", "content": prompt["system"]},
                        {"role": "user", "content": user_message},
                    ],
                    tools=[prompt["tool_schema"]],
                    tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
                )
                return self._extract_tool_input(response)
                
            except openai.APITimeoutError as exc:
                last_error = exc
                logger.warning("llm_timeout", extra={"attempt": attempt})
            except openai.RateLimitError as exc:
                last_error = exc
                logger.warning("llm_rate_limited", extra={"attempt": attempt})
            except openai.APIStatusError as exc:
                if exc.status_code and exc.status_code < 500:
                    # 4xx: no tiene sentido reintentar (p.ej. API key inválida)
                    raise LLMError(f"Error no reintentable del proveedor: {exc}") from exc
                last_error = exc
                logger.warning("llm_server_error", extra={"attempt": attempt, "status": exc.status_code})

            if attempt < self._settings.llm_max_retries:
                backoff_seconds = 2 ** (attempt - 1)  # 1s, 2s, 4s...
                await asyncio.sleep(backoff_seconds)

        if isinstance(last_error, openai.APITimeoutError):
            raise LLMTimeoutError("El proveedor LLM no respondió a tiempo") from last_error
        raise LLMError(f"Fallaron los {self._settings.llm_max_retries} intentos de llamada al LLM") from last_error

    @staticmethod
    def _extract_tool_input(response) -> dict:
        import json
        message = response.choices[0].message
        if not message.tool_calls:
            raise LLMMalformedResponseError(
                "El LLM no devolvió la tool call esperada (submit_big_five_profile)"
        )
    tool_call = message.tool_calls[0]
    if tool_call.function.name != TOOL_NAME:
        raise LLMMalformedResponseError(f"Tool call inesperada: {tool_call.function.name}")
    return json.loads(tool_call.function.arguments)
    