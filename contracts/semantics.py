"""Executable definitions of the frozen section 9 rules, shared by A (extraction) and B (agents).

These are DEFINITIONS, not agents: small pure functions so "what does fail mean" or "what is P"
has exactly one answer, pinned by backend/tests/test_contract_semantics.py.
B's agents/eligibility.py and agents/scoring.py call these (or must match them exactly);
B still owns operator evaluation, plain-language reasons, library building and state writes.
No LLM is involved anywhere here.
"""
from typing import Literal

from contracts import constants
from contracts.schemas import ProfileAttributes

RuleResult = Literal["pass", "fail", "unknown", "ambiguous"]

RULE_RESULT_MEANING = {
    "pass": "required: condition met | exclusion: condition does NOT apply",
    "fail": "required: condition not met | exclusion: condition DOES apply",
    "unknown": "a profile field the rule needs is missing (never treated as fail)",
    "ambiguous": "operator 'manual' or unclear wording; needs a document or official check",
}


def rule_result(kind: Literal["required", "exclusion"], operator: str, condition: bool | None) -> RuleResult:
    """Map one evaluated condition to a RuleCheck.result.

    condition = whether the rule's field/operator/value test is true for this profile,
    or None if the field is missing. B evaluates the operator; this fixes the meaning.
    """
    if operator == "manual":
        return "ambiguous"
    if condition is None:
        return "unknown"
    if kind == "required":
        return "pass" if condition else "fail"
    return "fail" if condition else "pass"          # exclusion: condition true => user is excluded


def eligibility_status(results: list[RuleResult]) -> str:
    """Section 9 precedence, applied in this exact order."""
    if not results:
        return "NEEDS_VERIFICATION"                 # reason: "Eligibility criteria not extracted yet"
    if "fail" in results:
        return "NOT_ELIGIBLE"
    if all(r == "pass" for r in results):
        return "ELIGIBLE"
    if "unknown" in results:
        return "PARTIALLY_ELIGIBLE"
    return "NEEDS_VERIFICATION"                     # only pass + ambiguous remain


# ── Beneficiary tags: tri-state per tag (True match, False no match, None cannot tell) ──
def evaluate_tags(attrs: ProfileAttributes) -> dict[str, bool | None]:
    """Executable form of constants.BENEFICIARY_TAGS (the derivable ones). Missing field -> None."""
    a = attrs
    age = a.age

    def eq(value, target):
        return None if value is None else value == target

    out = {
        "farmer": eq(a.occupation, "farmer"),
        "student": eq(a.occupation, "student"),
        "unemployed": eq(a.occupation, "unemployed"),
        "woman": eq(a.gender, "female"),
        "sc": eq(a.social_category, "sc"),
        "st": eq(a.social_category, "st"),
        "obc": eq(a.social_category, "obc"),
        "ews": eq(a.social_category, "ews"),
        "senior": None if age is None else age >= 60,
        "youth": None if age is None else 18 <= age <= 35,
        "child": None if age is None else age < 18,
        "widow": eq(a.marital_status, "widowed"),
        "disabled": a.disability,
        "rural": eq(a.area_type, "rural"),
        "urban": eq(a.area_type, "urban"),
        "bpl": a.is_bpl,
    }
    derivable = {t for t, rule in constants.BENEFICIARY_TAGS.items() if rule is not None}
    assert set(out) == derivable, "evaluate_tags out of sync with constants.BENEFICIARY_TAGS"
    return out


# ── Score components (each 0..1) and the frozen formula ──
def profile_relevance(attrs: ProfileAttributes, scheme_tags: list[str]) -> float:
    """P = matched tags / scheme tags this profile CAN evaluate.

    Tags with no profile rule (artisan, shg, ...) or whose field is missing are left out of the
    denominator, so a scheme is not penalised for what the profile cannot tell. 0 evaluable -> 0.0.
    """
    status = evaluate_tags(attrs)
    evaluable = [t for t in dict.fromkeys(scheme_tags) if status.get(t) is not None]
    if not evaluable:
        return 0.0
    return sum(1 for t in evaluable if status[t]) / len(evaluable)


def benefit_relevance(sectors_of_interest: list[str], sector: str, secondary_sectors: list[str]) -> float:
    """B = 1.0 if the primary OR any secondary sector is of interest, else 0.0 (binary: no double count)."""
    return 1.0 if set(sectors_of_interest) & ({sector} | set(secondary_sectors)) else 0.0


def need_relevance(need_similarity: float | None) -> float:
    """N = Candidate.need_similarity clipped to 0..1; None (no needs / not computed) -> 0.0."""
    return 0.0 if need_similarity is None else min(1.0, max(0.0, need_similarity))


def eligibility_fit(status: str) -> float:
    return constants.ELIGIBILITY_FIT[status]


def match_percent(components: dict[str, float]) -> int:
    """round(100 * (0.35P + 0.30E + 0.20N + 0.15B)); components keyed by constants.SCORE_COMPONENTS."""
    w = constants.SCORE_WEIGHTS
    return round(100 * sum(w[k] * components[k] for k in constants.SCORE_COMPONENTS))


def ranking_key(match: int, scheme_id: str) -> tuple[int, str]:
    """Sort ascending with this key: highest match first, ties by scheme_id alphabetically."""
    return (-match, scheme_id)
