"""Versioned prompts ("prompt as code").

Every meaningful change to the prompt bumps the version. The active
version is set in Settings.prompt_version and travels in the response
(metadata), so results can be correlated with the prompt version that
generated them.
"""

SYSTEM_PROMPT_V1 = """You are an assistant that infers a Big Five (OCEAN) \
personality profile from a user's answers to a short questionnaire. You \
must rely solely on the content of the answers provided, without \
inventing information that isn't present in them.

For each of the five dimensions (openness, conscientiousness, \
extraversion, agreeableness, neuroticism):
- Assign an integer score from 1 to 5 (1 = low pole, 5 = high pole).
- Write a brief rationale (1-2 sentences) referencing concrete evidence \
from the user's answers.

Additionally, include a "confidence" value between 0 and 1 reflecting \
how much textual evidence supports the inferred profile (less text or \
ambiguous answers should yield lower confidence).

Always use the `submit_big_five_profile` tool to respond. Do not \
respond with free text."""


def build_user_prompt(answers: list[tuple[str, str]]) -> str:
    """Builds the user message from (question_id, text) pairs.

    Kept as a pure, testable function: given the same input, always the
    same output prompt.
    """
    lines = ["User's answers to the questionnaire:\n"]
    for question_id, text in answers:
        lines.append(f"- [{question_id}] {text}")
    return "\n".join(lines)


# Tool definition to force structured output (tool use / function
# calling). We avoid parsing free text: the model must fill in this
# schema, and we validate it again with Pydantic when we receive it.
BIG_FIVE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_big_five_profile",
        "description": "Submit the inferred Big Five profile with a score and rationale per dimension.",
        "parameters": {
            "type": "object",
            "properties": {
                "openness": {"$ref": "#/$defs/dimension"},
                "conscientiousness": {"$ref": "#/$defs/dimension"},
                "extraversion": {"$ref": "#/$defs/dimension"},
                "agreeableness": {"$ref": "#/$defs/dimension"},
                "neuroticism": {"$ref": "#/$defs/dimension"},
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Overall confidence in the inferred profile (0-1)",
                },
            },
            "required": [
                "openness",
                "conscientiousness",
                "extraversion",
                "agreeableness",
                "neuroticism",
                "confidence",
            ],
            "$defs": {
                "dimension": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "rationale": {"type": "string", "maxLength": 500},
                    },
                    "required": ["score", "rationale"],
                }
            },
        },
    },
}

PROMPT_REGISTRY = {
    "v1": {
        "system": SYSTEM_PROMPT_V1,
        "tool_schema": BIG_FIVE_TOOL_SCHEMA,
    }
}