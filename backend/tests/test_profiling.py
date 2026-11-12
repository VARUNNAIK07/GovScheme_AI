"""Dynamic questioning agent: which questions appear, how they are worded, which options are offered."""
from contracts.schemas import Profile, ProfileAttributes
from backend.app.agents import profiling


def _fields(**attrs) -> list[str]:
    return [q.field for q in profiling.visible_questions(ProfileAttributes(**attrs))]


def _question(field: str, **attrs):
    return next(q for q in profiling.visible_questions(ProfileAttributes(**attrs)) if q.field == field)


def test_condition_operators():
    a = ProfileAttributes(age=30, occupation="farmer", needs=["savings scheme"])
    assert profiling.condition_met(a, {"field": "age", "gte": 18})
    assert not profiling.condition_met(a, {"field": "age", "lte": 25})
    assert profiling.condition_met(a, {"field": "occupation", "in": ["farmer", "student"]})
    assert profiling.condition_met(a, {"field": "needs", "in": ["savings scheme"]})
    assert profiling.condition_met(a, {"any": [{"field": "age", "lte": 10}, {"field": "occupation", "equals": "farmer"}]})
    assert not profiling.condition_met(a, {"all": [{"field": "age", "gte": 18}, {"not": {"field": "occupation", "equals": "farmer"}}]})
    assert not profiling.condition_met(a, {"field": "gender", "equals": "female"})   # unanswered never matches


def test_follow_up_questions_depend_on_answers():
    assert "land_holding_acres" not in _fields(occupation="student", age=40)
    assert "land_holding_acres" in _fields(occupation="farmer", age=40)
    assert "education_level" in _fields(occupation="student", age=40)
    assert "education_level" in _fields(occupation="salaried", age=22)
    assert "education_level" not in _fields(occupation="salaried", age=40)
    assert "disability_percent" in _fields(disability=True)
    assert "disability_percent" not in _fields(disability=False)
    assert "marital_status" not in _fields(age=15)


def test_wording_and_options_adapt():
    assert "studying" in _question("education_level", occupation="student").text
    young_woman = _question("needs", age=22, gender="female", occupation="student").options
    assert "scholarship or education support" in young_woman and "support for women or children" in young_woman
    assert "pension or old-age support" not in young_woman
    elderly_man = _question("needs", age=70, gender="male", occupation="retired").options
    assert "pension or old-age support" in elderly_man and "scholarship or education support" not in elderly_man
    assert "job, skill training or apprenticeship" not in elderly_man
    assert set(_question("needs", age=30).option_labels) == set(_question("needs", age=30).options)


def test_every_option_has_a_label():
    for q in profiling.load_question_bank():
        assert set(q.get("option_labels", {})) == set(q.get("options", [])), q["field"]


def test_onboarding_skips_hidden_questions_and_completes():
    p = Profile(user_id="u", version=1, attributes=ProfileAttributes(), complete=False)
    answers = {"age": 40, "gender": "male", "state": "IN-UP", "area_type": "urban", "occupation": "salaried",
               "social_category": "general", "annual_family_income_inr": 300000, "is_bpl": False,
               "disability": False, "marital_status": "married", "needs": ["savings scheme"],
               "sectors_of_interest": ["financial_inclusion"]}
    asked = []
    while (q := profiling.next_question(p)) is not None:
        asked.append(q.field)
        p = profiling.apply_answer(p, q.field, answers[q.field])
    assert p.complete and "land_holding_acres" not in asked and "education_level" not in asked


def test_changing_occupation_clears_stale_follow_up():
    p = Profile(user_id="u", version=1, attributes=ProfileAttributes(occupation="farmer", land_holding_acres=2.5),
                complete=False)
    p = profiling.apply_answer(p, "occupation", "salaried")
    assert p.attributes.land_holding_acres is None


def test_invalid_answers_rejected():
    assert profiling.validate_answer("age", 200)
    assert profiling.validate_answer("state", "Uttar Pradesh")
    assert profiling.validate_answer("needs", ["anything"])
    assert profiling.validate_answer("is_bpl", "yes")
    assert not profiling.validate_answer("state", "IN-UP")
