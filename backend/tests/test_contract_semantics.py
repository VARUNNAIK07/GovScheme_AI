"""Pins the section 9 definitions in contracts/semantics.py (rule meaning, status order, score parts)."""
import pytest

from contracts import constants
from contracts import semantics as s
from contracts.schemas import ProfileAttributes


# ── Rule semantics ──
@pytest.mark.parametrize("kind,op,cond,expected", [
    ("required", "gte", True, "pass"),
    ("required", "gte", False, "fail"),        # requirement not satisfied
    ("exclusion", "is_true", True, "fail"),    # exclusion condition applies
    ("exclusion", "is_true", False, "pass"),
    ("required", "lte", None, "unknown"),      # missing field is never 'fail'
    ("exclusion", "eq", None, "unknown"),
    ("required", "manual", None, "ambiguous"),
    ("exclusion", "manual", True, "ambiguous"),
])
def test_rule_result(kind, op, cond, expected):
    assert s.rule_result(kind, op, cond) == expected


@pytest.mark.parametrize("results,status", [
    ([], "NEEDS_VERIFICATION"),
    (["pass", "pass"], "ELIGIBLE"),
    (["pass", "fail", "unknown", "ambiguous"], "NOT_ELIGIBLE"),   # step 1 wins
    (["pass", "unknown"], "PARTIALLY_ELIGIBLE"),
    (["pass", "unknown", "ambiguous"], "PARTIALLY_ELIGIBLE"),     # step 3 before step 4
    (["pass", "ambiguous"], "NEEDS_VERIFICATION"),
])
def test_status_precedence(results, status):
    assert s.eligibility_status(results) == status


def test_manual_rule_alone_needs_verification():
    assert s.eligibility_status([s.rule_result("required", "manual", None)]) == "NEEDS_VERIFICATION"


# ── Score components ──
FARMER = ProfileAttributes(occupation="farmer", area_type="rural", gender="male", age=45)


def test_profile_relevance_ignores_non_derivable_tags():
    # 'fpo' and 'shg' cannot be judged from a profile -> not in the denominator
    assert s.profile_relevance(FARMER, ["farmer", "rural", "fpo", "shg"]) == 1.0


def test_profile_relevance_ignores_tags_whose_field_is_missing():
    # is_bpl missing -> 'bpl' unknown -> excluded; farmer matches, woman does not
    assert s.profile_relevance(FARMER, ["farmer", "woman", "bpl"]) == 0.5


def test_profile_relevance_nothing_evaluable_is_zero():
    assert s.profile_relevance(ProfileAttributes(), ["farmer", "artisan"]) == 0.0


def test_evaluate_tags_covers_every_derivable_tag():
    derivable = {t for t, r in constants.BENEFICIARY_TAGS.items() if r}
    assert set(s.evaluate_tags(ProfileAttributes())) == derivable


def test_benefit_relevance_counts_secondary_sectors_once():
    assert s.benefit_relevance(["agriculture_rural"], "financial_inclusion", ["agriculture_rural"]) == 1.0
    assert s.benefit_relevance(["agriculture_rural", "financial_inclusion"], "financial_inclusion",
                               ["agriculture_rural"]) == 1.0          # binary, no double count
    assert s.benefit_relevance(["health"], "financial_inclusion", ["agriculture_rural"]) == 0.0


@pytest.mark.parametrize("sim,n", [(None, 0.0), (-0.2, 0.0), (0.42, 0.42), (1.3, 1.0)])
def test_need_relevance_uses_retrieval_value(sim, n):
    assert s.need_relevance(sim) == n


def test_formula_weights_frozen():
    assert constants.SCORE_WEIGHTS == {"profile": 0.35, "eligibility": 0.30, "need": 0.20, "benefit": 0.15}
    assert s.match_percent({"profile": 1, "eligibility": 1, "need": 1, "benefit": 1}) == 100
    assert s.match_percent({"profile": 0.5, "eligibility": 0.6, "need": 0.0, "benefit": 1.0}) == round(100 * 0.505)


def test_eligibility_fit_mapping():
    assert [s.eligibility_fit(x) for x in constants.ELIGIBILITY_STATUSES] == [1.0, 0.6, 0.0, 0.5]


def test_scoring_is_deterministic_and_ties_break_by_scheme_id():
    comps = {"profile": 0.5, "eligibility": 1.0, "need": 0.3, "benefit": 1.0}
    runs = {s.match_percent(dict(comps)) for _ in range(20)}
    assert len(runs) == 1
    ranked = sorted([(70, "pmsby"), (70, "apy"), (80, "pm-kisan")], key=lambda x: s.ranking_key(*x))
    assert [sid for _, sid in ranked] == ["pm-kisan", "apy", "pmsby"]


def test_ui_label():
    assert constants.SCORE_UI_LABEL == "relevance match"
