"""Golden transcripts for the evaluation layer (Option C).

What this measures and why:
We are NOT trying to validate psychometric accuracy — that's out of
scope per the prompt, and there's no ground truth to compare against
for open-ended text answers. Instead, each case pairs a set of answers
that unambiguously lean toward one pole of a dimension with a *score
range* that any reasonable inference should fall into.

This catches regressions, not correctness in an absolute sense: if a
prompt change makes the model start scoring everything near the middle
regardless of input, these cases will fail even though the schema is
still valid. That's the kind of drift unit tests on schemas alone can't
catch, because they never exercise the actual model behavior.

Each case only asserts what's genuinely unambiguous from the text. We
deliberately don't try to pin an exact score (e.g. "must be exactly 5")
since LLM outputs have some legitimate variance between calls; a range
is the right level of strictness here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GoldenCase:
    name: str
    answers: list[str]
    expected_ranges: dict[str, tuple[int, int]]


GOLDEN_CASES: list[GoldenCase] = [
    GoldenCase(
        name="clearly_high_openness_and_low_conscientiousness",
        answers=[
            "I love trying new restaurants, exploring unfamiliar cities, and reading about topics I know absolutely nothing about. Novelty excites me.",
            "I rarely plan ahead. I usually figure things out as I go and often miss deadlines because I forget about them.",
            "I'm fairly reserved, I prefer small groups or being alone over big parties.",
            "I try to be fair but I don't back down easily if I think I'm right.",
            "I handle stress reasonably well, it doesn't overwhelm me for long.",
        ],
        expected_ranges={
            "openness": (4, 5),
            "conscientiousness": (1, 2),
        },
    ),
    GoldenCase(
        name="clearly_high_conscientiousness_and_low_neuroticism",
        answers=[
            "I'm not particularly curious about new things, I tend to stick with what I know works.",
            "I plan everything in detail, use to-do lists daily, and rarely miss a deadline.",
            "I enjoy being around people but it's not a defining part of my personality.",
            "I try to find middle ground in disagreements rather than push my own view.",
            "Unexpected problems rarely stress me out, I stay calm and just deal with them.",
        ],
        expected_ranges={
            "conscientiousness": (4, 5),
            "neuroticism": (1, 2),
        },
    ),
    GoldenCase(
        name="clearly_high_extraversion_and_high_neuroticism",
        answers=[
            "I like some variety but I'm not constantly seeking new experiences.",
            "I keep a rough plan but I'm flexible about changing it.",
            "I absolutely thrive in big groups, parties, and meeting new people. It energizes me.",
            "I tend to go along with others to avoid conflict, even when I disagree.",
            "Unexpected events really throw me off, I get anxious and it takes a while to calm down.",
        ],
        expected_ranges={
            "extraversion": (4, 5),
            "neuroticism": (4, 5),
        },
    ),
]