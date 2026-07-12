"""Async wrapper around the OpenAI client.

Single responsibility: given a set of answers, call the LLM with
structured output (function calling) and return the function input as a
raw dict. Validating that dict against our contract (Pydantic) lives in
domain/, not here — this module only knows how to talk to the provider.
"""
import asyncio
import json
import logging
import time

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
            timeout=settings.llm_timeout_seconds,
        )

    async def infer_profile(self, answers: list[tuple[str, str]]) -> dict:
        """Calls the LLM and returns the function call input as a dict.

        Retries with exponential backoff on transient errors (timeout,
        rate limit, provider 5xx). Does not retry on auth or payload
        errors (4xx on our side), which won't fix themselves.
        """
        prompt = PROMPT_REGISTRY[self._settings.prompt_version]
        user_message = build_user_prompt(answers)

        last_error: Exception | None = None
        for attempt in range(1, self._settings.llm_max_retries + 1):
            call_started = time.monotonic()
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
                latency_ms = round((time.monotonic() - call_started) * 1000, 1)
                logger.info(
                    "llm_call_succeeded",
                    extra={"attempt": attempt, "latency_ms": latency_ms, "model": self._settings.llm_model},
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
                    # 4xx: not worth retrying (e.g. invalid API key)
                    raise LLMError(f"Non-retryable provider error: {exc}") from exc
                last_error = exc
                logger.warning("llm_server_error", extra={"attempt": attempt, "status": exc.status_code})

            if attempt < self._settings.llm_max_retries:
                backoff_seconds = 2 ** (attempt - 1)  # 1s, 2s, 4s...
                await asyncio.sleep(backoff_seconds)

        if isinstance(last_error, openai.APITimeoutError):
            raise LLMTimeoutError("The LLM provider did not respond in time") from last_error
        raise LLMError(f"All {self._settings.llm_max_retries} LLM call attempts failed") from last_error

    @staticmethod
    def _extract_tool_input(response) -> dict:
        message = response.choices[0].message
        if not message.tool_calls:
            raise LLMMalformedResponseError(
                "LLM did not return the expected tool call (submit_big_five_profile)"
            )
        tool_call = message.tool_calls[0]
        if tool_call.function.name != TOOL_NAME:
            raise LLMMalformedResponseError(f"Unexpected tool call: {tool_call.function.name}")
        return json.loads(tool_call.function.arguments)