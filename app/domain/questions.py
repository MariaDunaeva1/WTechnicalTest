"""Fixed questionnaire for the conversational flow (Option B).

One question per dimension, in fixed order. Not used for Option A (the
client sends all 5 answers at once); for B, the service guides the
conversation question by question using this list.

Inspired by the spirit of the BFI (see prompt), simplified.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    question_id: str
    text: str


QUESTIONNAIRE: list[Question] = [
    Question("q_openness", "What role do curiosity and trying new things play in your daily life?"),
    Question("q_conscientiousness", "How do you organize your tasks and plans? Do you tend to follow a plan or improvise?"),
    Question("q_extraversion", "How do you feel in social situations with lots of people?"),
    Question("q_agreeableness", "When there's a conflict of opinions, how do you usually react?"),
    Question("q_neuroticism", "How do unexpected events or stress affect your daily life?"),
]


def get_question(index: int) -> Question:
    return QUESTIONNAIRE[index]


def total_questions() -> int:
    return len(QUESTIONNAIRE)