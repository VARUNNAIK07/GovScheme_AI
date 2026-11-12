"""Comparison Agent function (Person A): compare(schemes, eligibility, evidence) -> ComparisonMatrix.

Deterministic, no LLM: every cell comes from facts already extracted and verified in PostgreSQL
(Scheme lists + Scheme.fact_citations) or from the deterministic eligibility result. A missing fact is
value=None ('Not stated in source'), never a guess. The written insights (ComparisonInsights) are the
Summary Agent's job (summary.explain_comparison), which receives this matrix.

    matrix = compare(schemes, eligibility, evidence)
    evidence_for_matrix(matrix) -> list[Evidence]   # the chunks behind every citation in the matrix
"""
from contracts import constants
from contracts.schemas import ComparisonCell, ComparisonMatrix, EligibilityResult, Evidence, Scheme
from backend.app.knowledge.scheme_store import load_evidence

MAX_ITEMS_PER_CELL = 4
_STATUS_TEXT = {"ELIGIBLE": "Eligible", "PARTIALLY_ELIGIBLE": "Partially eligible (more details needed)",
                "NOT_ELIGIBLE": "Not eligible", "NEEDS_VERIFICATION": "Needs official verification"}
_PERIOD = {"one_time": "one time", "per_year": "per year", "per_month": "per month"}


def format_inr(amount: int) -> str:
    """Indian digit grouping: 200000 -> 'Rs 2,00,000'."""
    digits = str(abs(int(amount)))
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        digits = ",".join([head] + groups + [tail]) if head else ",".join(groups + [tail])
    return f"Rs {'-' if amount < 0 else ''}{digits}"


def _cell(items: list[str], citation_ids: list[str], numbered: bool = False) -> ComparisonCell:
    items = [i for i in items if i][:MAX_ITEMS_PER_CELL]
    if not items or not citation_ids:                      # no cited source -> not stated
        return ComparisonCell(value=None, citation_ids=[])
    text = "; ".join(f"{n}. {t}" if numbered else t for n, t in enumerate(items, 1))
    return ComparisonCell(value=text, citation_ids=list(dict.fromkeys(citation_ids)))


def _target_group(scheme: Scheme) -> ComparisonCell:
    # who the scheme is for, in the scheme's own cited summary (exclusions belong in eligibility_status)
    return _cell([scheme.summary] if scheme.summary else [], scheme.fact_citations.get("summary", []))


def _status_cell(el: EligibilityResult | None) -> ComparisonCell:
    if el is None:
        return ComparisonCell(value=None, citation_ids=[])
    reason = el.reasons[0].split(": ", 1)[-1] if el.reasons else ""       # drop the agent's own prefix
    value = f"{_STATUS_TEXT[el.status]}: {reason}" if reason else _STATUS_TEXT[el.status]
    return ComparisonCell(value=value, citation_ids=list(dict.fromkeys(c.citation_id for c in el.checks if c.citation_id)))


def compare(schemes: dict[str, Scheme] | list[Scheme], eligibility: dict[str, EligibilityResult],
            evidence: dict[str, list[Evidence]] | None = None) -> ComparisonMatrix:
    """evidence is accepted for the contract signature; cells cite stored facts, which are always real chunks."""
    items = list(schemes.values()) if isinstance(schemes, dict) else list(schemes)
    if not 2 <= len(items) <= 5:
        raise ValueError("comparison needs 2 to 5 schemes")
    cells: dict[str, dict[str, ComparisonCell]] = {}
    for s in items:
        cites = s.fact_citations
        max_benefit = (_cell([f"Up to {format_inr(s.max_benefit_inr)} {_PERIOD.get(s.max_benefit_period, '')}".strip()],
                             cites.get("max_benefit_inr", []))
                       if s.max_benefit_inr is not None else ComparisonCell(value=None, citation_ids=[]))
        cells[s.scheme_id] = {
            "target_group": _target_group(s),
            "eligibility_status": _status_cell(eligibility.get(s.scheme_id)),
            "benefits": _cell(s.benefits, cites.get("benefits", [])),
            "max_benefit_inr": max_benefit,
            "documents": _cell(s.documents_required, cites.get("documents_required", [])),
            "application_process": _cell(s.application_steps, cites.get("application_steps", []), numbered=True),
            "limitations": _cell(s.limitations, cites.get("limitations", [])),
        }
    return ComparisonMatrix(scheme_ids=[s.scheme_id for s in items], fields=list(constants.COMPARISON_FIELDS),
                            cells=cells)


def evidence_for_matrix(matrix: ComparisonMatrix) -> list[Evidence]:
    """All chunks cited anywhere in the matrix (for ComparisonResponse.evidence and the citation chips)."""
    ids = [cid for row in matrix.cells.values() for cell in row.values() for cid in cell.citation_ids]
    return load_evidence(ids)


# ── deterministic explanations (used when the LLM is unavailable, and for comparison insights) ──
def summary_from_facts(scheme: Scheme, eligibility: EligibilityResult, evidence: list[Evidence],
                       attrs) -> "SchemeSummary":
    """SchemeSummary built only from stored, verified facts (each sentence cites its own chunk)."""
    from contracts.schemas import CitedSentence, SchemeSummary
    from backend.app.knowledge import citations, summary
    from backend.app.knowledge.scheme_store import load_facts
    by_kind: dict[str, list[CitedSentence]] = {}
    for kind, text, cid in load_facts(scheme.scheme_id):
        by_kind.setdefault(kind, []).append(CitedSentence(text=text, citation_ids=[cid]))
    rule_lines = [CitedSentence(text=c.reason.split(": ", 1)[-1], citation_ids=[c.citation_id])
                  for c in eligibility.checks if c.citation_id]
    draft = SchemeSummary(
        overview=by_kind.get("summary", []), relevance=summary.relevance_sentences(eligibility, attrs),
        eligibility=rule_lines, benefits=by_kind.get("benefit", []) + by_kind.get("max_benefit", []),
        documents=by_kind.get("document_required", []), application=by_kind.get("application_step", []))
    kept, _ = citations.validate_summary(draft, evidence)
    return kept


def insights_from_matrix(matrix: ComparisonMatrix, schemes: dict[str, Scheme]) -> "ComparisonInsights":
    """Short cited observations read straight off the matrix (no LLM, nothing uncited)."""
    from contracts.schemas import CitedSentence, ComparisonInsights
    name = {sid: schemes[sid].name if sid in schemes else sid for sid in matrix.scheme_ids}
    out = []
    amounts = [(schemes[sid].max_benefit_inr, sid) for sid in matrix.scheme_ids
               if sid in schemes and schemes[sid].max_benefit_inr is not None
               and matrix.cells[sid]["max_benefit_inr"].citation_ids]
    if len(amounts) >= 2:
        amount, sid = max(amounts)
        out.append(CitedSentence(text=f"{name[sid]} states the largest single benefit: "
                                      f"{matrix.cells[sid]['max_benefit_inr'].value}.",
                                 citation_ids=matrix.cells[sid]["max_benefit_inr"].citation_ids))
    for sid in matrix.scheme_ids:
        cell = matrix.cells[sid]["eligibility_status"]
        if cell.value and cell.citation_ids:
            out.append(CitedSentence(text=f"{name[sid]}: {cell.value}", citation_ids=cell.citation_ids[:3]))
    # 'not stated' is shown per cell by the UI (value None); it is never phrased as a cited insight
    return ComparisonInsights(insights=out)
