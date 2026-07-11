"""Custom exceptions, to avoid leaking provider SDK exceptions up to the
API layer. This way the API layer only knows these types and decides the
right status code, without coupling to the Anthropic/OpenAI SDK."""


class LLMError(Exception):
    """Generic error communicating with the LLM provider."""


class LLMTimeoutError(LLMError):
    """The provider did not respond within the configured timeout."""


class LLMMalformedResponseError(LLMError):
    """The LLM responded, but not in the expected structured format
    (missing tool call, or a payload that fails schema validation)."""