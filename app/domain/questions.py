"""Cuestionario fijo para el flujo conversacional (Option B).

Una pregunta por dimensión, en orden fijo. Para Option A esto no se usa
(el cliente manda las 5 respuestas de golpe); para B, el servicio guía la
conversación pregunta a pregunta usando esta lista.

Inspiradas en el espíritu del BFI (ver enunciado), simplificadas.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    question_id: str
    text: str


QUESTIONNAIRE: list[Question] = [
    Question("q_openness", "¿Qué papel juegan la curiosidad y probar cosas nuevas en tu día a día?"),
    Question("q_conscientiousness", "¿Cómo organizas tus tareas y planes? ¿Sueles seguir un plan o improvisas?"),
    Question("q_extraversion", "¿Cómo te sientes en situaciones sociales con mucha gente?"),
    Question("q_agreeableness", "Cuando hay un conflicto de opiniones, ¿cómo sueles reaccionar?"),
    Question("q_neuroticism", "¿Cómo te afectan los imprevistos o el estrés en el día a día?"),
]


def get_question(index: int) -> Question:
    return QUESTIONNAIRE[index]


def total_questions() -> int:
    return len(QUESTIONNAIRE)
