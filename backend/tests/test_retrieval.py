"""Retrieval agent unit tests: no database, no Qdrant, no model (all three are replaced by fakes).

Live check against real data (needs indexed chunks):  see test_known_query_finds_scheme_live.
"""
import pytest

from contracts.schemas import Candidate, Evidence, Profile, ProfileAttributes
from backend.app.knowledge import retrieval


def _ev(scheme_id: str, score: float, n: int = 0) -> Evidence:
    cid = f"{'a' * 16}-p1-c{n}"
    return Evidence(citation_id=cid, chunk_id=cid, doc_id="a" * 16, scheme_id=scheme_id, section=None, page=1,
                    text="t", bbox=None, source_url="https://x.gov.in/a.pdf", doc_version=1, score=score)


@pytest.fixture
def fakes(monkeypatch):
    pool = {"pm-kmy": {"sectors": {"financial_inclusion", "agriculture_rural"}},
            "pmsby": {"sectors": {"financial_inclusion"}},
            "midh": {"sectors": {"agriculture_rural"}}}
    calls = {}

    def search(vector, limit, scheme_ids=None):
        calls["scheme_ids"] = scheme_ids
        return [_ev("pmsby", 0.70, 0), _ev("pm-kmy", 0.81, 1), _ev("pm-kmy", 0.60, 2)]

    monkeypatch.setattr(retrieval, "schemes_available_in", lambda state: pool)
    monkeypatch.setattr(retrieval.qdrant_store, "search", search)
    monkeypatch.setattr(retrieval, "embed_query", lambda text: [0.0] * 384)
    monkeypatch.setattr(retrieval, "load_summaries", lambda ids: {})
    return calls


def _profile(**attrs) -> Profile:
    return Profile(user_id="u", version=1, attributes=ProfileAttributes(**attrs), complete=True)


def test_best_chunk_score_per_scheme_and_order(fakes):
    out = retrieval.retrieve_candidates(_profile(occupation="farmer"), top_k=5)
    assert [c.scheme_id for c in out] == ["pm-kmy", "pmsby"]
    assert out[0].retrieval_score == 0.81                      # max of that scheme's chunk scores
    assert all(isinstance(c, Candidate) for c in out)


def test_search_is_limited_to_schemes_open_in_the_state(fakes):
    retrieval.retrieve_candidates(_profile(state="IN-OD"), top_k=5)
    assert fakes["scheme_ids"] == ["midh", "pm-kmy", "pmsby"]   # the pool, sorted


def test_sector_matches_are_always_offered(fakes):
    out = {c.scheme_id: c for c in retrieval.retrieve_candidates(_profile(sectors_of_interest=["agriculture_rural"]))}
    assert out["midh"].retrieval_score == 0.0 and out["midh"].matched_sectors == ["agriculture_rural"]
    assert out["pm-kmy"].matched_sectors == ["agriculture_rural"]


def test_top_k_cuts_search_hits_but_not_sector_matches(fakes):
    out = retrieval.retrieve_candidates(_profile(sectors_of_interest=["agriculture_rural"]), top_k=1)
    assert [c.scheme_id for c in out] == ["pm-kmy", "midh"]


def test_same_profile_same_result(fakes):
    p = _profile(occupation="farmer", needs=["pension"], sectors_of_interest=["financial_inclusion"])
    assert retrieval.retrieve_candidates(p) == retrieval.retrieve_candidates(p)


def test_need_similarity_none_without_needs_or_summary():
    assert retrieval.need_similarity([], "x", "summary") is None
    assert retrieval.need_similarity(["pension"], "x", None) is None


def test_profile_query_describes_the_person_without_identifiers():
    q = retrieval.profile_query(ProfileAttributes(age=67, gender="female", marital_status="widowed",
                                                  is_bpl=True, state="IN-UP", district="Varanasi",
                                                  needs=["widow pension"]))
    assert "senior citizen" in q and "widow" in q and "below poverty line" in q and "widow pension" in q
    assert "Varanasi" not in q and "IN-UP" not in q and "67" not in q
