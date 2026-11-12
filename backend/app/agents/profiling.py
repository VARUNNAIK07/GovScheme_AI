import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from contracts.schemas import Profile, ProfileAttributes, Question


QUESTION_BANK_PATH = Path(__file__).with_name("question_bank.json")


def load_question_bank(path: Path = QUESTION_BANK_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _field_value(attrs: ProfileAttributes, field: str) -> Any:
    return getattr(attrs, field)


def _answered(attrs: ProfileAttributes, field: str) -> bool:
    value = _field_value(attrs, field)
    return bool(value) if isinstance(value, list) else value is not None


def condition_met(attrs: ProfileAttributes, cond: dict[str, Any] | None) -> bool:
    """Evaluate a question-bank condition against the profile. An unanswered field never satisfies one.

    {"field": f, "equals": v} | {"field": f, "in": [..]} | {"field": f, "not_in": [..]}
    {"field": f, "gte": n} | {"field": f, "lte": n} | {"all": [...]} | {"any": [...]} | {"not": {...}}
    """
    if not cond:
        return True
    if "all" in cond:
        return all(condition_met(attrs, c) for c in cond["all"])
    if "any" in cond:
        return any(condition_met(attrs, c) for c in cond["any"])
    if "not" in cond:
        return not condition_met(attrs, cond["not"])
    value = _field_value(attrs, cond["field"])
    if value is None or value == []:
        return False
    if "equals" in cond:
        return value == cond["equals"]
    if "in" in cond:
        return bool(set(value) & set(cond["in"])) if isinstance(value, list) else value in cond["in"]
    if "not_in" in cond:
        return value not in cond["not_in"]
    if "gte" in cond:
        return value >= cond["gte"]
    if "lte" in cond:
        return value <= cond["lte"]
    raise ValueError(f"Unsupported condition {cond}")


def _visible(attrs: ProfileAttributes, raw: dict[str, Any]) -> bool:
    return condition_met(attrs, raw.get("show_if"))


def _build(raw: dict[str, Any], attrs: ProfileAttributes, progress: float) -> Question:
    """The question as THIS person sees it: wording and options adapt to earlier answers."""
    text = next((t["text"] for t in raw.get("text_if", []) if condition_met(attrs, t["when"])), raw["text"])
    option_rules = raw.get("option_show_if", {})
    options = [o for o in raw.get("options", []) if condition_met(attrs, option_rules.get(o))]
    labels = {o: lbl for o, lbl in raw.get("option_labels", {}).items() if o in options}
    return Question(question_id=raw["question_id"], field=raw["field"], text=text, type=raw["type"],
                    options=options, option_labels=labels, progress=progress)


def visible_questions(attrs: ProfileAttributes, bank: list[dict[str, Any]] | None = None) -> list[Question]:
    """Every question that applies to this profile right now (used by the profile edit page)."""
    visible = [q for q in (bank or load_question_bank()) if _visible(attrs, q)]
    return [_build(raw, attrs, i / max(len(visible), 1)) for i, raw in enumerate(visible)]


def next_question(profile: Profile, bank: list[dict[str, Any]] | None = None) -> Question | None:
    questions = bank or load_question_bank()
    visible = [q for q in questions if _visible(profile.attributes, q)]
    for index, raw in enumerate(visible):
        if not _answered(profile.attributes, raw["field"]):
            return _build(raw, profile.attributes, index / max(len(visible), 1))
    return None


def prune_hidden(attrs: ProfileAttributes, bank: list[dict[str, Any]] | None = None) -> ProfileAttributes:
    """Clear answers to conditional questions that no longer apply (e.g. land size after a
    farmer changes occupation), so stale answers never drive eligibility."""
    data = attrs.model_dump()
    for raw in bank or load_question_bank():
        if raw.get("show_if") and not _visible(attrs, raw):
            default = ProfileAttributes.model_fields[raw["field"]].default
            data[raw["field"]] = list(default) if isinstance(default, list) else default
    return ProfileAttributes(**data)


NUMBER_RANGES = {"age": (0, 120), "annual_family_income_inr": (0, 1_000_000_000),
                 "land_holding_acres": (0, 100_000), "disability_percent": (0, 100)}


def validate_answer(field: str, value: Any, bank: list[dict[str, Any]] | None = None) -> list[str]:
    """Plain-language errors for an answer (empty list = valid). Choice answers must be option codes."""
    question = next((q for q in (bank or load_question_bank()) if q["field"] == field), None)
    if question is None:
        return [f"Unknown question for field '{field}'"]
    options, kind = question.get("options", []), question["type"]
    if kind == "single_choice" and value not in options:
        return ["Please choose one of the listed options"]
    if kind == "multi_choice":
        if not isinstance(value, list) or not value:
            return ["Please choose at least one option"]
        if not set(value) <= set(options):
            return ["Please choose only from the listed options"]
    if kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return ["Please enter a number"]
        low, high = NUMBER_RANGES.get(field, (0, float("inf")))
        if not low <= value <= high:
            return [f"Please enter a number between {low} and {high:,}"]
    if kind == "boolean" and not isinstance(value, bool):
        return ["Please answer yes or no"]
    return []


def apply_answer(profile: Profile, field: str, value: Any) -> Profile:
    if not hasattr(profile.attributes, field):
        raise ValueError(f"Unknown profile field: {field}")
    errors = validate_answer(field, value)
    if errors:
        raise ValueError(errors[0])

    data = profile.attributes.model_dump()
    data[field] = value
    try:
        attrs = prune_hidden(ProfileAttributes(**data))
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    complete = next_question(Profile(
        user_id=profile.user_id,
        version=profile.version,
        attributes=attrs,
        complete=False,
    )) is None
    return Profile(
        user_id=profile.user_id,
        version=profile.version + 1,
        attributes=attrs,
        complete=complete,
    )

