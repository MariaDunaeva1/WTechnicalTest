"""Prompts versionados ("prompt as code").

Cada cambio relevante en el prompt sube de versión. La versión activa se
fija en Settings.prompt_version y viaja en la respuesta (metadata), para
poder correlacionar resultados con la versión de prompt que los generó.
"""

SYSTEM_PROMPT_V1 = """Eres un asistente que infiere un perfil de personalidad \
Big Five (OCEAN) a partir de las respuestas de un usuario a un breve \
cuestionario. Debes basarte únicamente en el contenido de las respuestas \
proporcionadas, sin inventar información no presente en ellas.

Para cada una de las cinco dimensiones (openness, conscientiousness, \
extraversion, agreeableness, neuroticism):
- Asigna un score entero de 1 a 5 (1 = polo bajo, 5 = polo alto).
- Escribe una justificación breve (1-2 frases) que referencie evidencia \
concreta de las respuestas del usuario.

Además, incluye un valor de "confidence" entre 0 y 1 que refleje cuánta \
evidencia textual sustenta el perfil inferido (menos texto o respuestas \
ambiguas deberían dar una confianza más baja).

Usa siempre la herramienta `submit_big_five_profile` para responder. No \
respondas con texto libre."""


def build_user_prompt(answers: list[tuple[str, str]]) -> str:
    """Construye el mensaje de usuario a partir de (question_id, texto).

    Mantenemos esto como función pura y testeable: dado un input, siempre
    el mismo prompt de salida.
    """
    lines = ["Respuestas del usuario al cuestionario:\n"]
    for question_id, text in answers:
        lines.append(f"- [{question_id}] {text}")
    return "\n".join(lines)


# Definición de la tool para forzar salida estructurada (tool use / function
# calling). Evitamos parsear texto libre: el modelo debe rellenar este
# schema, y encima lo validamos otra vez con Pydantic al recibirlo.
BIG_FIVE_TOOL_SCHEMA = {
    "name": "submit_big_five_profile",
    "description": "Envía el perfil Big Five inferido con score y rationale por dimensión.",
    "input_schema": {
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
                "description": "Confianza global del perfil inferido (0-1)",
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
}

PROMPT_REGISTRY = {
    "v1": {
        "system": SYSTEM_PROMPT_V1,
        "tool_schema": BIG_FIVE_TOOL_SCHEMA,
    }
}
