"""Comparison matrix rules (no DB: Scheme objects built in memory)."""
import pytest

from contracts import constants
from contracts.schemas import EligibilityResult, RuleCheck, Scheme
from backend.app.knowledge.comparison import compare, format_inr

C = "aaaaaaaaaaaaaaaa-p1-c0"


def scheme(sid, **kw):
    base = dict(scheme_id=sid, name=sid, sector="health", department="d", level="central", states=["ALL"],
                beneficiary_tags=[], summary=None, benefits=[], max_benefit_inr=None, documents_required=[],
                application_steps=[], official_url=None, application_url=None, doc_ids=[], facts_status="extracted",
                last_checked="2026-10-13")
    return Scheme(**{**base, **kw})


def test_indian_number_format():
    assert [format_inr(n) for n in (500, 3000, 200000, 15000000)] == ["Rs 500", "Rs 3,000", "Rs 2,00,000", "Rs 1,50,00,000"]


def test_cells_cite_facts_and_missing_facts_are_not_stated():
    a = scheme("a", summary="Pension for farmers.", benefits=["Rs 3,000 a month"], max_benefit_inr=3000,
               max_benefit_period="per_month", fact_citations={"summary": [C], "benefits": [C], "max_benefit_inr": [C]})
    b = scheme("b")
    el = {"a": EligibilityResult(scheme_id="a", status="ELIGIBLE", checks=[RuleCheck(rule_id="r", result="pass",
          reason="Requirement satisfied: age 18-40", citation_id=C)], reasons=["All passed"], missing_fields=[])}
    m = compare({"a": a, "b": b}, el)
    assert m.fields == list(constants.COMPARISON_FIELDS)
    assert m.cells["a"]["max_benefit_inr"].value == "Up to Rs 3,000 per month" and m.cells["a"]["benefits"].citation_ids == [C]
    assert all(cell.value is None and cell.citation_ids == [] for cell in m.cells["b"].values())


def test_uncited_fact_is_never_shown():
    a = scheme("a", benefits=["Free laptop"])          # text but no fact_citations
    assert compare([a, scheme("b")], {}).cells["a"]["benefits"].value is None


def test_two_to_five_schemes_only():
    with pytest.raises(ValueError):
        compare([scheme("a")], {})
