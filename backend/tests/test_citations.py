"""Citation service + Summary (no network, no database, no LLM: a fake LLM is injected)."""
import inspect

import pytest

from contracts.schemas import (CitedSentence, EligibilityResult, Evidence, ProfileAttributes, RuleCheck, Scheme,
                               SchemeSummary)
from backend.app.knowledge import citations, summary

DOC_OLD, DOC_NEW = "aaaaaaaaaaaaaaaa", "bbbbbbbbbbbbbbbb"


def ev(doc_id: str, page: int, n: int = 0, bbox=None, version: int = 1) -> Evidence:
    cid = f"{doc_id}-p{page}-c{n}"
    return Evidence(citation_id=cid, chunk_id=cid, doc_id=doc_id, scheme_id="test-scheme", section="Benefits",
                    page=page, text=f"text of {cid}", bbox=bbox, source_url="https://example.gov.in/x.pdf",
                    doc_version=version)


EVIDENCE = [ev(DOC_NEW, 1, bbox=[90.0, 600.0, 520.0, 700.0], version=2), ev(DOC_NEW, 2, version=2)]
GOOD, OTHER = EVIDENCE[0].citation_id, EVIDENCE[1].citation_id


def test_validate_drops_uncited_and_unknown_citations():
    kept, dropped = citations.validate([
        CitedSentence(text="Backed.", citation_ids=[GOOD]),
        CitedSentence(text="No citation.", citation_ids=[]),
        CitedSentence(text="Made-up citation.", citation_ids=["ffffffffffffffff-p9-c9"]),
        CitedSentence(text="Partly real.", citation_ids=["ffffffffffffffff-p9-c9", OTHER, OTHER]),
    ], EVIDENCE)
    assert [(s.text, s.citation_ids) for s in kept] == [("Backed.", [GOOD]), ("Partly real.", [OTHER])]
    assert [s.text for s in dropped] == ["No citation.", "Made-up citation."]


def test_to_target_precision():
    assert citations.to_target(EVIDENCE[0]).precision == "passage"
    t = citations.to_target(EVIDENCE[1])
    assert t.precision == "page" and t.bbox is None and t.file_url == f"/api/documents/{DOC_NEW}/file"


def test_resolve_returns_real_page_and_old_versions_stay_resolvable():
    old = ev(DOC_OLD, 3, version=1)        # chunk of a replaced (non-current) document
    store = {e.citation_id: e for e in [*EVIDENCE, old]}
    target = citations.resolve(old.citation_id, lookup=store.get)
    assert (target.page, target.doc_id, target.doc_version) == (3, DOC_OLD, 1)
    with pytest.raises(KeyError):
        citations.resolve("ffffffffffffffff-p1-c0", lookup=store.get)


def test_db_lookup_does_not_filter_on_is_current():
    from backend.app.knowledge import scheme_store
    assert "is_current" not in inspect.getsource(scheme_store.load_evidence).split('"""')[2]
    assert "load_evidence" in inspect.getsource(citations._db_lookup)


def test_retrieval_excludes_old_versions(monkeypatch):
    """Real local Qdrant (in memory): replaced documents are not retrieved."""
    from qdrant_client import QdrantClient
    from backend.app.knowledge import qdrant_store
    client = QdrantClient(":memory:")
    monkeypatch.setattr(qdrant_store, "get_client", lambda: client)
    qdrant_store.ensure_collection(client)
    vec = [1.0] + [0.0] * 383
    old = ev(DOC_OLD, 1, version=1)
    qdrant_store.upsert_evidence([(old, vec)], is_current=False)
    qdrant_store.upsert_evidence([(EVIDENCE[0], vec)], is_current=True)
    hits = qdrant_store.search(vec, limit=10)
    assert [h.doc_id for h in hits] == [DOC_NEW]


# ── Summary ──
SCHEME = Scheme(scheme_id="test-scheme", name="Test Scheme", sector="financial_inclusion", department="Test Dept",
                level="central", states=["ALL"], beneficiary_tags=[], summary=None, benefits=[],
                max_benefit_inr=None, documents_required=[], application_steps=[], official_url=None,
                application_url=None, doc_ids=[DOC_NEW], facts_status="incomplete", last_checked="2026-10-12")
ELIG = EligibilityResult(scheme_id="test-scheme", status="PARTIALLY_ELIGIBLE", reasons=[], missing_fields=["is_bpl"],
                         checks=[RuleCheck(rule_id="test-scheme-r1", result="pass", reason="Age 45 is between 18 and 70.",
                                           citation_id=OTHER),
                                 RuleCheck(rule_id="test-scheme-r2", result="unknown", reason="BPL status not given.",
                                           citation_id="ffffffffffffffff-p9-c9"),   # not in evidence -> dropped
                                 RuleCheck(rule_id="test-scheme-r3", result="ambiguous", reason="Committee decides.",
                                           citation_id=None)])                    # uncited -> not emitted
ATTRS = ProfileAttributes(age=45, occupation="farmer")


def fake_llm(prompt: str) -> dict:
    assert "farmer" not in prompt and "45" not in prompt.split("Evidence passages:")[0], "profile leaked to LLM"
    return {"overview": [{"text": "Grounded.", "citation_ids": [GOOD]},
                         {"text": "Invented.", "citation_ids": ["ffffffffffffffff-p1-c0"]},
                         {"bad": "shape"}],
            "benefits": [{"text": "No source.", "citation_ids": []}]}


def test_summarize_scheme_signature_has_attrs():
    params = list(inspect.signature(summary.summarize_scheme).parameters)
    assert params[:4] == ["scheme", "eligibility", "evidence", "attrs"]


def test_summary_keeps_only_cited_sentences_and_builds_relevance_from_checks():
    out = summary.summarize_scheme(SCHEME, ELIG, EVIDENCE, ATTRS, llm=fake_llm)
    assert isinstance(out, SchemeSummary)
    assert [s.text for s in out.overview] == ["Grounded."]
    assert out.benefits == [] and out.documents == []
    assert [(s.text, s.citation_ids) for s in out.relevance] == [
        ("Matches your profile: Age 45 is between 18 and 70.", [OTHER])]
    used = {c for name in SchemeSummary.model_fields for s in getattr(out, name) for c in s.citation_ids}
    assert used <= {e.citation_id for e in EVIDENCE}


def test_summary_without_evidence_calls_no_llm():
    def boom(_):
        raise AssertionError("LLM must not be called without evidence")
    out = summary.summarize_scheme(SCHEME, ELIG, [], ATTRS, llm=boom)
    assert all(getattr(out, n) == [] for n in SchemeSummary.model_fields)


def test_default_llm_uses_llm_module_interface(monkeypatch):
    """complete_json(system, user, schema) -> LLMResult(.data); the adapter must return a plain dict."""
    from backend.app.knowledge import llm

    def fake_complete_json(system, user, schema):
        assert system == summary.SUMMARY_SYSTEM and schema is summary.SummaryDraft and "Evidence passages" in user
        assert "relevance" not in schema.model_fields
        return llm.LLMResult(data=schema(overview=[CitedSentence(text="Grounded.", citation_ids=[GOOD])]),
                             provider="fake", model="fake", latency_s=0.0)

    monkeypatch.setattr(llm, "complete_json", fake_complete_json)
    out = summary.summarize_scheme(SCHEME, ELIG, EVIDENCE, ATTRS)        # no llm= -> real default adapter
    assert [s.text for s in out.overview] == ["Grounded."]
