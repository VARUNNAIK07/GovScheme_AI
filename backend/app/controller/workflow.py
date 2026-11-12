"""Workflow Controller: runs W1-W6. Agents never call each other; the controller loads what they
need (schemes, rules) into the WorkflowState, calls them in order, records a trace, and caches results
in workflow_runs keyed by the user's profile_version (a profile change never reuses an old result)."""
import time
from datetime import datetime, timezone
from uuid import uuid4

from contracts.schemas import (ComparisonResponse, LibraryCard, Profile, RefreshResult, SchemeDetail, TraceStep,
                               WorkflowState)
from backend.app.agents.eligibility import evaluate
from backend.app.agents.profiling import next_question
from backend.app.agents.registry import AgentRegistry
from backend.app.agents.scoring import build_library, score_scheme
from backend.app.controller.cache import WorkflowCache


class _Trace:
    def __init__(self):
        self.steps: list[TraceStep] = []

    def run(self, agent: str, fn, *args, **kwargs):
        started, t0 = datetime.now(timezone.utc).isoformat(timespec="seconds"), time.monotonic()
        try:
            out = fn(*args, **kwargs)
            self.steps.append(TraceStep(agent=agent, status="ok", started_at=started,
                                        duration_ms=int((time.monotonic() - t0) * 1000)))
            return out
        except Exception as e:
            self.steps.append(TraceStep(agent=agent, status="error", started_at=started,
                                        duration_ms=int((time.monotonic() - t0) * 1000), message=str(e)[:200]))
            raise


class WorkflowController:
    def __init__(self, registry: AgentRegistry | None = None, cache: WorkflowCache | None = None):
        self.registry = registry or AgentRegistry()          # USE_STUBS in .env decides stubs vs knowledge layer
        self._cache = cache

    @property
    def cache(self) -> WorkflowCache | None:
        # stub mode (tests/offline) never touches the database
        if self._cache is None and not self.registry.use_stubs:
            self._cache = WorkflowCache()
        return self._cache

    # ── W1 onboarding ──
    def onboarding_next(self, profile: Profile) -> WorkflowState:
        return WorkflowState(run_id=str(uuid4()), workflow="W1", user_id=profile.user_id, profile=profile,
                             profile_version=profile.version, next_question=next_question(profile))

    # ── W2 library ──
    def library(self, profile: Profile, use_cache: bool = True) -> WorkflowState:
        if use_cache and self.cache and (hit := self.cache.get("W2", profile.user_id, profile.version)):
            return hit.model_copy(update={"skipped": ["W2 served from cache"]})
        trace = _Trace()
        candidates = trace.run("retrieval", self.registry.candidates, profile)
        ids = [c.scheme_id for c in candidates]
        schemes = trace.run("load_schemes", self.registry.schemes, ids if not self.registry.use_stubs else None,
                            include_facts=False)          # cards + scoring need metadata only
        rules = trace.run("load_rules", self.registry.rules, ids if not self.registry.use_stubs else None)
        eligibility = trace.run("eligibility", lambda: {
            sid: evaluate(profile.attributes, sid, rules.get(sid, [])) for sid in schemes})
        scores = trace.run("scoring", lambda: {
            c.scheme_id: score_scheme(profile.attributes, schemes[c.scheme_id], c, eligibility[c.scheme_id])
            for c in candidates if c.scheme_id in schemes})
        library = trace.run("build_library", build_library, profile.version, schemes, eligibility, scores,
                            candidates=candidates if not self.registry.use_stubs else None)
        state = WorkflowState(run_id=str(uuid4()), workflow="W2", user_id=profile.user_id, profile=profile,
                              profile_version=profile.version, candidates=candidates, schemes=schemes, rules=rules,
                              eligibility=eligibility, scores=scores, library=library, trace=trace.steps)
        if self.cache:
            self.cache.set(state, list(schemes))
        return state

    # ── W3 scheme detail ──
    def scheme_detail(self, profile: Profile, scheme_id: str) -> SchemeDetail:
        if self.cache and (hit := self.cache.get("W3", profile.user_id, profile.version, [scheme_id])):
            return SchemeDetail(scheme=hit.schemes[scheme_id], eligibility=hit.eligibility[scheme_id],
                                summary=hit.summary, evidence=hit.evidence.get(scheme_id, []))
        trace = _Trace()
        schemes = trace.run("load_schemes", self.registry.schemes, [scheme_id] if not self.registry.use_stubs else None)
        if scheme_id not in schemes:
            raise KeyError(f"Unknown scheme: {scheme_id}")
        scheme = schemes[scheme_id]
        rules = trace.run("load_rules", self.registry.rules, [scheme_id] if not self.registry.use_stubs else None)
        eligibility = trace.run("eligibility", evaluate, profile.attributes, scheme_id, rules.get(scheme_id, []))
        evidence = trace.run("retrieval", self.registry.evidence, scheme)
        summary = trace.run("summary", self.registry.summarize_scheme, scheme, eligibility, evidence, profile.attributes)
        cited = {cid for section in summary.model_dump().values() for s in section for cid in s["citation_ids"]}
        evidence = [ev for ev in evidence if ev.chunk_id in cited] or evidence
        if self.cache:
            self.cache.set(WorkflowState(run_id=str(uuid4()), workflow="W3", user_id=profile.user_id,
                                         profile_version=profile.version, scheme_ids=[scheme_id],
                                         schemes={scheme_id: scheme}, rules={scheme_id: rules.get(scheme_id, [])},
                                         eligibility={scheme_id: eligibility}, evidence={scheme_id: evidence},
                                         summary=summary, trace=trace.steps), [scheme_id])
        return SchemeDetail(scheme=scheme, eligibility=eligibility, summary=summary, evidence=evidence)

    # ── W4 comparison ──
    def comparison_options(self, profile: Profile) -> list[LibraryCard]:
        return self.library(profile).library.top

    def compare(self, profile: Profile, scheme_ids: list[str]) -> ComparisonResponse:
        ids = list(dict.fromkeys(scheme_ids))
        if not 2 <= len(ids) <= 5:
            raise ValueError("Choose 2 to 5 schemes to compare")
        allowed = {c.scheme_id for c in self.comparison_options(profile)}
        if not set(ids) <= allowed:
            raise ValueError("Only schemes from your top recommendations can be compared: "
                             + ", ".join(sorted(set(ids) - allowed)))
        schemes = self.registry.schemes(ids if not self.registry.use_stubs else None)
        rules = self.registry.rules(ids if not self.registry.use_stubs else None)
        eligibility = {sid: evaluate(profile.attributes, sid, rules.get(sid, [])) for sid in ids if sid in schemes}
        matrix, insights, evidence = self.registry.compare({sid: schemes[sid] for sid in ids if sid in schemes},
                                                           eligibility)
        if self.cache:
            self.cache.repo.save_comparison(profile.user_id, ids, None)
        return ComparisonResponse(matrix=matrix, insights=insights, evidence=evidence)

    # ── W5 profile change: invalidate cached runs, then rebuild the library ──
    def after_profile_change(self, profile: Profile) -> WorkflowState:
        if self.cache:
            self.cache.invalidate_user(profile.user_id)
        return self.library(profile, use_cache=False)

    # ── W6 refresh sources ──
    def refresh(self, doc_id: str | None = None) -> RefreshResult:
        from ingestion import refresh as refresh_job          # offline pipeline, run on demand by an admin
        result = refresh_job.run(doc_id=doc_id)
        invalidated = self.cache.invalidate_schemes(result.affected_schemes) if self.cache else []
        return result.model_copy(update={"invalidated_runs": invalidated})
