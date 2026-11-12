"""Retrieval Agent functions (Person A): profile -> candidate schemes, scheme -> evidence.

Contract (build plan section 4 + v1.2):
    retrieve_candidates(profile, top_k=30) -> list[Candidate]
    get_evidence(scheme_id, query, k=6)    -> list[Evidence]
No LLM. Deterministic for a given index: same profile -> same candidates in the same order.

How candidates are chosen
1. Pool = active schemes open in the user's state ('ALL' + profile.state).
2. One BGE query built from the profile (who they are + what they need + sectors of interest),
   searched over current chunks of the pool only.
3. retrieval_score = best chunk similarity per scheme (cosine, 0..1).
4. Result = top_k schemes by score, PLUS every pool scheme in the user's sectors of interest
   (score 0.0 if it had no hit), so B's 'more in your sectors' list is never starved.
5. need_similarity = cosine(BGE(needs), BGE(scheme summary)); None if no needs or no summary.
"""
from contracts import constants
from contracts.schemas import Candidate, Evidence, Profile, ProfileAttributes
from contracts.semantics import evaluate_tags
from backend.app.knowledge import qdrant_store
from backend.app.knowledge.embedder import embed_documents, embed_query
from backend.app.knowledge.scheme_store import load_summaries, schemes_available_in

CHUNKS_PER_SCHEME = 4          # how many chunk hits per requested scheme we fetch before grouping
_TAG_WORDS = {
    "farmer": "farmer", "student": "student", "unemployed": "unemployed job seeker", "woman": "woman",
    "sc": "Scheduled Caste (SC)", "st": "Scheduled Tribe (ST)", "obc": "Other Backward Class (OBC)",
    "ews": "economically weaker section (EWS)", "senior": "senior citizen", "youth": "young person",
    "child": "child", "widow": "widow", "disabled": "person with disability", "rural": "rural area",
    "urban": "urban area", "bpl": "below poverty line (BPL) family",
}


def profile_query(attrs: ProfileAttributes) -> str:
    """Plain-English description of the person, used as the search query (no personal identifiers)."""
    who = [_TAG_WORDS[t] for t, hit in evaluate_tags(attrs).items() if hit]
    if attrs.occupation and attrs.occupation not in ("farmer", "student", "unemployed"):
        who.append(attrs.occupation.replace("_", " "))
    parts = ["Government scheme for a " + ", ".join(who) if who else "Government welfare scheme"]
    if attrs.needs:
        parts.append("needs: " + "; ".join(attrs.needs))
    if attrs.sectors_of_interest:
        parts.append("interested in: " + "; ".join(constants.SECTORS.get(s, s) for s in attrs.sectors_of_interest))
    return ". ".join(parts)


_SUMMARY_VECTORS: dict[tuple[str, str], list[float]] = {}     # (scheme_id, summary) -> vector, per process


def _summary_vectors(summaries: dict[str, str]) -> dict[str, list[float]]:
    missing = [(sid, text) for sid, text in summaries.items() if (sid, text) not in _SUMMARY_VECTORS]
    if missing:                                          # one batched model call for all new summaries
        for (sid, text), vec in zip(missing, embed_documents([t for _, t in missing])):
            _SUMMARY_VECTORS[(sid, text)] = vec
    return {sid: _SUMMARY_VECTORS[(sid, text)] for sid, text in summaries.items()}


def need_similarity(needs: list[str], scheme_id: str, summary: str | None,
                    query_vector: list[float] | None = None) -> float | None:
    if not needs or not summary:
        return None
    q = query_vector or embed_query("; ".join(needs))
    s = _summary_vectors({scheme_id: summary})[scheme_id]
    return round(min(1.0, max(0.0, sum(a * b for a, b in zip(q, s)))), 4)   # vectors are normalised


def retrieve_candidates(profile: Profile, top_k: int = 30) -> list[Candidate]:
    attrs = profile.attributes
    pool = schemes_available_in(attrs.state)
    if not pool:
        return []
    hits = qdrant_store.search(embed_query(profile_query(attrs)), limit=top_k * CHUNKS_PER_SCHEME,
                               scheme_ids=sorted(pool))
    best: dict[str, float] = {}
    for h in hits:
        best[h.scheme_id] = max(best.get(h.scheme_id, 0.0), h.score or 0.0)

    interest = set(attrs.sectors_of_interest)
    ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]
    chosen = dict(ranked)
    for sid, info in pool.items():                      # sector matches are always offered
        if interest & info["sectors"] and sid not in chosen:
            chosen[sid] = 0.0

    summaries = load_summaries(list(chosen)) if attrs.needs else {}
    need_vec = embed_query("; ".join(attrs.needs)) if summaries else None
    _summary_vectors(summaries)                          # warm the cache in one batch
    out = [Candidate(scheme_id=sid, retrieval_score=round(score, 4),
                     matched_sectors=sorted(interest & pool[sid]["sectors"]),
                     need_similarity=need_similarity(attrs.needs, sid, summaries.get(sid), need_vec))
           for sid, score in chosen.items()]
    return sorted(out, key=lambda c: (-c.retrieval_score, c.scheme_id))


def get_evidence(scheme_id: str, query: str, k: int = 6) -> list[Evidence]:
    """Top-k current chunks of one scheme for a question (Evidence.score = cosine similarity)."""
    return qdrant_store.search(embed_query(query), limit=k, scheme_ids=[scheme_id])
