"""contracts/fixtures + personas.json: valid contract shapes, real provenance, consistent semantics."""
import hashlib
import json
from pathlib import Path

import pytest

from contracts import schemas as c
from contracts import semantics
from backend.app.knowledge.citations import to_target

ROOT = Path(__file__).resolve().parents[2]
FX = ROOT / "contracts" / "fixtures"
MODELS = {"profile.json": c.Profile, "question.json": c.OnboardingNext, "library.json": c.LibraryResult,
          "scheme_detail.json": c.SchemeDetail, "comparison.json": c.ComparisonResponse,
          "citation.json": c.CitationTarget}


def load(name):
    return json.loads((FX / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_fixture_validates_and_is_labelled(name):
    raw = load(name)
    assert raw.pop("_fixture") is True and raw.pop("_model") == MODELS[name].__name__
    raw.pop("_note")
    MODELS[name].model_validate(raw, strict=False)
    # every contract field is present in the JSON (so MSW responses look exactly like the real API)
    assert set(MODELS[name].model_fields) <= set(raw)


def _cited_ids(detail: c.SchemeDetail):
    ids = {i for n in c.SchemeSummary.model_fields for s in getattr(detail.summary, n) for i in s.citation_ids}
    ids |= {k.citation_id for k in detail.eligibility.checks if k.citation_id}
    ids |= {i for v in detail.scheme.fact_citations.values() for i in v}
    return ids


def test_scheme_detail_citations_are_in_its_evidence_and_facts_are_verbatim():
    d = c.SchemeDetail.model_validate(load("scheme_detail.json"))
    ev = {e.citation_id: e for e in d.evidence}
    assert _cited_ids(d) <= set(ev)
    for n in c.SchemeSummary.model_fields:
        for s in getattr(d.summary, n):
            if n != "relevance":   # relevance text comes from eligibility check reasons, not a quote
                assert any(s.text in ev[i].text for i in s.citation_ids), f"{n}: not verbatim: {s.text[:60]}"
    facts = {"benefits": d.scheme.benefits, "documents_required": d.scheme.documents_required,
             "application_steps": d.scheme.application_steps, "limitations": d.scheme.limitations,
             "summary": [d.scheme.summary]}
    for field, values in facts.items():
        for v in values:
            assert any(v in ev[i].text for i in d.scheme.fact_citations[field]), f"{field} not in its cited chunk"
    assert d.eligibility.status == semantics.eligibility_status([k.result for k in d.eligibility.checks])


def test_comparison_citations_are_in_its_evidence():
    r = c.ComparisonResponse.model_validate(load("comparison.json"))
    ev = {e.citation_id for e in r.evidence}
    used = {i for row in r.matrix.cells.values() for cell in row.values() for i in cell.citation_ids}
    used |= {i for s in r.insights.insights for i in s.citation_ids}
    assert used <= ev
    assert set(r.matrix.cells) == set(r.matrix.scheme_ids) and 2 <= len(r.matrix.scheme_ids) <= 5
    for row in r.matrix.cells.values():
        assert set(row) == set(r.matrix.fields)
        for cell in row.values():
            assert cell.value is not None or cell.citation_ids == []   # 'Not stated in source' has no citation


def test_citation_fixture_matches_resolver_mapping():
    target = c.CitationTarget.model_validate(load("citation.json"))
    d = c.SchemeDetail.model_validate(load("scheme_detail.json"))
    ev = next(e for e in d.evidence if e.citation_id == target.citation_id)
    assert to_target(ev) == target


def test_fixture_evidence_still_matches_real_chunks():
    """Fails if re-chunking changed the PMSBY chunks: then run python -m contracts.fixtures.build_fixtures."""
    d = c.SchemeDetail.model_validate(load("scheme_detail.json"))
    path = ROOT / "data" / "chunks" / f"{d.evidence[0].doc_id}.jsonl"
    if not path.exists():
        pytest.skip("chunk file not present on this machine")
    real = {r["chunk_id"]: r for r in map(json.loads, path.read_text(encoding="utf-8").splitlines())}
    for e in d.evidence:
        assert e.citation_id in real and real[e.citation_id]["text"] == e.text, f"stale fixture chunk {e.citation_id}"


def test_sample_pdf_is_the_real_document():
    d = c.SchemeDetail.model_validate(load("scheme_detail.json"))
    data = (FX / "sample.pdf").read_bytes()
    assert data.startswith(b"%PDF") and hashlib.sha256(data).hexdigest()[:16] == d.evidence[0].doc_id


def test_library_rules():
    lib = c.LibraryResult.model_validate(load("library.json"))
    ids = [x.scheme_id for x in lib.top + lib.more]
    assert len(ids) == len(set(ids)) and len(lib.top) <= 5 and len(lib.more) <= 5
    assert all(x.match_percent is not None and x.eligibility_status != "NOT_ELIGIBLE" for x in lib.top)
    assert all(x.match_percent is None for x in lib.more)
    assert [x.scheme_id for x in lib.top] == [x.scheme_id for x in
                                              sorted(lib.top, key=lambda x: semantics.ranking_key(x.match_percent, x.scheme_id))]


def test_question_labels_cover_options():
    q = c.OnboardingNext.model_validate(load("question.json")).question
    assert set(q.option_labels) == set(q.options)


def test_personas():
    raw = json.loads((ROOT / "contracts" / "personas.json").read_text(encoding="utf-8"))
    assert raw["_fixture"] is True
    people = {p["persona_id"]: c.ProfileAttributes.model_validate(p["attributes"]) for p in raw["personas"]}
    assert set(people) == {"farmer_rural", "student_sc_female", "senior_widow_bpl"}
    f, s, w = people["farmer_rural"], people["student_sc_female"], people["senior_widow_bpl"]
    assert f.occupation == "farmer" and f.area_type == "rural"
    assert s.gender == "female" and s.social_category == "sc" and s.occupation == "student"
    assert w.marital_status == "widowed" and w.is_bpl and w.age >= 60
