import pytest
from pydantic import ValidationError

from app.domain.schemas import Answer, AssessmentRequest, BigFiveProfile, DimensionScore


def test_answer_rejects_blank_text():
    with pytest.raises(ValidationError):
        Answer(question_id="q1", text="   ")


def test_answer_strips_whitespace():
    answer = Answer(question_id="q1", text="  Me gusta planificar todo.  ")
    assert answer.text == "Me gusta planificar todo."


def test_assessment_request_requires_exactly_five_answers():
    answers = [Answer(question_id=f"q{i}", text="respuesta") for i in range(4)]
    with pytest.raises(ValidationError):
        AssessmentRequest(answers=answers)


def test_assessment_request_accepts_five_answers():
    answers = [Answer(question_id=f"q{i}", text="respuesta") for i in range(5)]
    request = AssessmentRequest(answers=answers)
    assert len(request.answers) == 5


@pytest.mark.parametrize("score", [0, 6, -1])
def test_dimension_score_rejects_out_of_range(score):
    with pytest.raises(ValidationError):
        DimensionScore(score=score, rationale="motivo")


def test_dimension_score_accepts_valid_range():
    score = DimensionScore(score=3, rationale="motivo")
    assert score.score == 3


def test_big_five_profile_requires_all_dimensions():
    valid_dim = {"score": 3, "rationale": "motivo"}
    with pytest.raises(ValidationError):
        BigFiveProfile(
            openness=valid_dim,
            conscientiousness=valid_dim,
            extraversion=valid_dim,
            agreeableness=valid_dim,
            # falta neuroticism
        )
