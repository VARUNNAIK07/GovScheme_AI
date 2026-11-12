from contracts import constants
from contracts.schemas import (
    Candidate,
    EligibilityResult,
    LibraryCard,
    LibraryResult,
    ProfileAttributes,
    Scheme,
    ScoreResult,
)
from contracts.semantics import (
    benefit_relevance,
    eligibility_fit,
    match_percent,
    need_relevance,
    profile_relevance,
    ranking_key,
)


def score_scheme(
    attrs: ProfileAttributes,
    scheme: Scheme,
    candidate: Candidate,
    eligibility: EligibilityResult,
) -> ScoreResult:
    components = {
        "profile": profile_relevance(attrs, scheme.beneficiary_tags),
        "eligibility": eligibility_fit(eligibility.status),
        "need": need_relevance(candidate.need_similarity),
        "benefit": benefit_relevance(attrs.sectors_of_interest, scheme.sector, scheme.secondary_sectors),
    }
    return ScoreResult(
        scheme_id=scheme.scheme_id,
        match_percent=match_percent(components),
        components=components,
    )


def build_library(
    profile_version: int,
    schemes: dict[str, Scheme],
    eligibility: dict[str, EligibilityResult],
    scores: dict[str, ScoreResult],
    top_n: int = constants.LIBRARY_TOP_N,
    more_n: int = constants.LIBRARY_MORE_N,
    candidates: list[Candidate] | None = None,
) -> LibraryResult:
    """Section 9 library selection.

    top  = the top_n highest match scores among schemes that are not NOT_ELIGIBLE (ties by scheme_id).
    more = next schemes whose sector matches the user's sectors of interest (candidate.matched_sectors),
           not already in top, ordered by retrieval_score, up to more_n, with match_percent=None.
    Fewer cards are returned if fewer qualify; nothing is padded.
    """
    def card(scheme_id: str, match: int | None) -> LibraryCard:
        scheme, result = schemes[scheme_id], eligibility[scheme_id]
        return LibraryCard(
            scheme_id=scheme_id, name=scheme.name, department=scheme.department, sector=scheme.sector,
            eligibility_status=result.status,
            eligibility_reason=result.reasons[0] if result.reasons else "No eligibility reason available.",
            match_percent=match)

    ranked = sorted((sid for sid in scores if sid in schemes and eligibility[sid].status != "NOT_ELIGIBLE"),
                    key=lambda sid: ranking_key(scores[sid].match_percent, sid))
    top = [card(sid, scores[sid].match_percent) for sid in ranked[:top_n]]
    taken = {c.scheme_id for c in top}
    if candidates is None:                      # B's original behaviour: next best by score
        more_ids = [sid for sid in ranked[top_n:]]
    else:
        more_ids = [c.scheme_id for c in sorted(candidates, key=lambda c: (-c.retrieval_score, c.scheme_id))
                    if c.matched_sectors and c.scheme_id in schemes and c.scheme_id not in taken]
    more = [card(sid, None) for sid in more_ids[:more_n]]
    return LibraryResult(profile_version=profile_version, top=top, more=more)
