"""Read side of the knowledge base: PostgreSQL rows -> contract models (Scheme, EligibilityRule).

Used by the Workflow Controller to fill WorkflowState.schemes / .rules (replaces B's
agents/stubs.sample_schemes / sample_rules). Read-only; never calls an LLM.
Facts or rules with review_status 'rejected' are never returned.
"""
from collections import defaultdict

from sqlalchemy import select

from contracts import constants
from contracts.schemas import EligibilityRule, Evidence, Scheme
from backend.app.db import models as m
from backend.app.db.session import session_scope

_KIND_TO_FIELD = {kind: field for field, kind in constants.FACT_KIND_BY_FIELD.items()}


def load_summaries(scheme_ids: list[str]) -> dict[str, str]:
    """scheme_id -> summary (only schemes that have one). One small query; used for need similarity."""
    if not scheme_ids:
        return {}
    with session_scope() as s:
        return dict(s.execute(select(m.SchemeRow.scheme_id, m.SchemeRow.summary)
                              .where(m.SchemeRow.scheme_id.in_(scheme_ids), m.SchemeRow.summary.is_not(None))).all())


def load_schemes(scheme_ids: list[str] | None = None, active_only: bool = True,
                 include_facts: bool = True) -> dict[str, Scheme]:
    """All (or the given) schemes as contract Scheme objects, keyed by scheme_id.
    include_facts=False skips benefits/documents/steps/limitations (library cards and scoring don't use them)."""
    with session_scope() as s:
        q = select(m.SchemeRow)
        if scheme_ids is not None:
            q = q.where(m.SchemeRow.scheme_id.in_(scheme_ids))
        if active_only:
            q = q.where(m.SchemeRow.is_active)
        rows = {r.scheme_id: r for r in s.scalars(q)}
        ids = list(rows)
        if not ids:
            return {}

        def grouped(stmt):
            out = defaultdict(list)
            for key, value in s.execute(stmt):
                out[key].append(value)
            return out

        secondary = grouped(select(m.SchemeSecondarySector.scheme_id, m.SchemeSecondarySector.sector_id)
                            .where(m.SchemeSecondarySector.scheme_id.in_(ids))
                            .order_by(m.SchemeSecondarySector.sector_id))
        states = grouped(select(m.SchemeState.scheme_id, m.SchemeState.state_code)
                         .where(m.SchemeState.scheme_id.in_(ids)).order_by(m.SchemeState.state_code))
        tag_rows = s.execute(select(m.SchemeTag.scheme_id, m.Tag.tag_id, m.Tag.kind).join(m.Tag)
                             .where(m.SchemeTag.scheme_id.in_(ids)).order_by(m.Tag.tag_id)).all()
        doc_ids = grouped(select(m.Source.scheme_id, m.DocumentRow.doc_id).join(m.DocumentRow)
                          .where(m.Source.scheme_id.in_(ids), m.DocumentRow.is_current)
                          .order_by(m.DocumentRow.doc_id))
        facts = s.execute(select(m.SchemeFact)
                          .where(m.SchemeFact.scheme_id.in_(ids), m.SchemeFact.review_status != "rejected")
                          .order_by(m.SchemeFact.scheme_id, m.SchemeFact.kind, m.SchemeFact.position)).scalars().all()             if include_facts else []

        texts: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        cites: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for f in facts:
            field = _KIND_TO_FIELD.get(f.kind)
            if field is None:
                continue
            texts[f.scheme_id][field].append(f.text)
            if f.citation_id not in cites[f.scheme_id][field]:
                cites[f.scheme_id][field].append(f.citation_id)

        out = {}
        for sid, r in rows.items():
            out[sid] = Scheme(
                scheme_id=sid, name=r.name, sector=r.primary_sector, department=r.department, level=r.level,
                states=states.get(sid, []),
                beneficiary_tags=[t for x, t, k in tag_rows if x == sid and k == "beneficiary"],
                benefit_types=[t for x, t, k in tag_rows if x == sid and k == "benefit_type"],
                secondary_sectors=secondary.get(sid, []),
                summary=r.summary, max_benefit_inr=r.max_benefit_inr, max_benefit_period=r.max_benefit_period,
                benefits=texts[sid]["benefits"], documents_required=texts[sid]["documents_required"],
                application_steps=texts[sid]["application_steps"], limitations=texts[sid]["limitations"],
                official_url=r.official_url, application_url=r.application_url,
                doc_ids=doc_ids.get(sid, []), facts_status=r.facts_status,
                last_checked=r.last_checked.isoformat(),
                fact_citations={field: ids_ for field, ids_ in cites[sid].items()},
            )
        return out


def load_rules(scheme_ids: list[str] | None = None) -> dict[str, list[EligibilityRule]]:
    """Eligibility rules per scheme (contract EligibilityRule). A scheme with no rules is absent."""
    with session_scope() as s:
        q = select(m.EligibilityRuleRow).where(m.EligibilityRuleRow.review_status != "rejected")
        if scheme_ids is not None:
            q = q.where(m.EligibilityRuleRow.scheme_id.in_(scheme_ids))
        out: dict[str, list[EligibilityRule]] = defaultdict(list)
        for r in s.scalars(q.order_by(m.EligibilityRuleRow.scheme_id, m.EligibilityRuleRow.rule_id)):
            out[r.scheme_id].append(EligibilityRule(
                rule_id=r.rule_id, scheme_id=r.scheme_id, field=r.field, operator=r.operator, value=r.value,
                kind=r.kind, source_text=r.source_text, citation_id=r.citation_id))
        return dict(out)


def schemes_available_in(state_code: str | None) -> dict[str, dict]:
    """Lightweight index for retrieval: scheme_id -> {"sectors": primary + secondary} for schemes open to this state."""
    allowed = {constants.ALL_STATES} | ({state_code} if state_code else set())
    with session_scope() as s:
        rows = s.execute(select(m.SchemeRow.scheme_id, m.SchemeRow.primary_sector)
                         .join(m.SchemeState).where(m.SchemeRow.is_active, m.SchemeState.state_code.in_(allowed))
                         .distinct()).all()
        secondary = s.execute(select(m.SchemeSecondarySector.scheme_id, m.SchemeSecondarySector.sector_id)).all()
    sec = defaultdict(set)
    for sid, sector in secondary:
        sec[sid].add(sector)
    return {sid: {"sectors": {primary} | sec[sid]} for sid, primary in rows}


def load_evidence(chunk_ids: list[str]) -> list[Evidence]:
    """Chunks by id as Evidence, in the given order (one query). Not filtered on is_current, so old
    citations still resolve. Unknown ids are simply absent from the result."""
    if not chunk_ids:
        return []
    with session_scope() as s:
        rows = s.execute(select(m.ChunkRow, m.DocumentRow.version, m.Source.scheme_id, m.Source.url)
                         .join(m.DocumentRow, m.DocumentRow.doc_id == m.ChunkRow.doc_id)
                         .join(m.Source, m.Source.source_id == m.DocumentRow.source_id)
                         .where(m.ChunkRow.chunk_id.in_(list(dict.fromkeys(chunk_ids))))).all()
    found = {c.chunk_id: Evidence(citation_id=c.chunk_id, chunk_id=c.chunk_id, doc_id=c.doc_id, scheme_id=sid,
                                  section=c.section, page=c.page, text=c.text, bbox=c.bbox,
                                  source_url=url, doc_version=ver)
             for c, ver, sid, url in rows}
    return [found[i] for i in dict.fromkeys(chunk_ids) if i in found]


def load_facts(scheme_id: str) -> list[tuple[str, str, str]]:
    """(kind, text, citation_id) for one scheme's non-rejected facts, in display order."""
    with session_scope() as s:
        return [tuple(r) for r in s.execute(
            select(m.SchemeFact.kind, m.SchemeFact.text, m.SchemeFact.citation_id)
            .where(m.SchemeFact.scheme_id == scheme_id, m.SchemeFact.review_status != "rejected")
            .order_by(m.SchemeFact.kind, m.SchemeFact.position)).all()]
