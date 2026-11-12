from contracts.schemas import (Candidate, ComparisonInsights, ComparisonMatrix, EligibilityResult, EligibilityRule,
                               Evidence, Profile, ProfileAttributes, Scheme, SchemeSummary)
from backend.app.agents import stubs
from backend.app.core.config import get_settings


class AgentRegistry:
    """Handshake point between the deterministic agents (B) and the knowledge layer (A).

    use_stubs=True  -> contracts/fixtures (tests, offline demos)
    use_stubs=False -> backend.app.knowledge (PostgreSQL + Qdrant + LLM)
    Both modes have the same method signatures, so the controller never knows which is active.
    """

    def __init__(self, use_stubs: bool | None = None):
        self.use_stubs = get_settings().use_stubs if use_stubs is None else use_stubs

    # ── retrieval + records ──
    def candidates(self, profile: Profile) -> list[Candidate]:
        if self.use_stubs:
            return stubs.sample_candidates()
        from backend.app.knowledge.retrieval import retrieve_candidates
        return retrieve_candidates(profile)

    def schemes(self, scheme_ids: list[str] | None = None, include_facts: bool = True) -> dict[str, Scheme]:
        if self.use_stubs:
            return stubs.sample_schemes()
        from backend.app.knowledge.scheme_store import load_schemes
        return load_schemes(scheme_ids, include_facts=include_facts)

    def rules(self, scheme_ids: list[str] | None = None) -> dict[str, list[EligibilityRule]]:
        if self.use_stubs:
            return stubs.sample_rules()
        from backend.app.knowledge.scheme_store import load_rules
        return load_rules(scheme_ids)

    def evidence(self, scheme: Scheme, query: str | None = None, k: int = 8) -> list[Evidence]:
        """Evidence for one scheme: its stored fact citations + the best chunks for the query."""
        if self.use_stubs:
            return stubs.fixture_evidence() if scheme.scheme_id == stubs.fixture_scheme().scheme_id else []
        from backend.app.knowledge.retrieval import get_evidence
        from backend.app.knowledge.scheme_store import load_evidence
        cited = [cid for ids in scheme.fact_citations.values() for cid in ids]
        found = load_evidence(cited) + get_evidence(scheme.scheme_id, query or f"{scheme.name} benefits eligibility", k=k)
        seen, out = set(), []
        for ev in found:
            if ev.chunk_id not in seen:
                seen.add(ev.chunk_id)
                out.append(ev)
        return out

    # ── explanation ──
    def summarize_scheme(self, scheme: Scheme, eligibility: EligibilityResult, evidence: list[Evidence],
                         attrs: ProfileAttributes) -> SchemeSummary:
        if self.use_stubs:
            return stubs.summarize_scheme(scheme, eligibility, evidence, attrs)
        from backend.app.knowledge import summary
        from backend.app.knowledge.llm import LLMError
        try:
            return summary.summarize_scheme(scheme, eligibility, evidence, attrs)
        except LLMError:
            # LLM unavailable (quota/outage): fall back to the stored, already-verified cited facts
            from backend.app.knowledge.comparison import summary_from_facts
            return summary_from_facts(scheme, eligibility, evidence, attrs)

    def compare(self, schemes: dict[str, Scheme], eligibility: dict[str, EligibilityResult]
                ) -> tuple[ComparisonMatrix, ComparisonInsights, list[Evidence]]:
        if self.use_stubs:
            return stubs.compare()
        from backend.app.knowledge.comparison import compare, evidence_for_matrix, insights_from_matrix
        matrix = compare(schemes, eligibility)
        return matrix, insights_from_matrix(matrix, schemes), evidence_for_matrix(matrix)
