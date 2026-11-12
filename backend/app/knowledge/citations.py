"""Citation service: keep only sentences backed by real evidence, and resolve citation_ids for the PDF viewer.

validate(sentences, evidence) -> (kept, dropped)   pure, no I/O
resolve(citation_id) -> CitationTarget             reads PostgreSQL 'chunks' (all versions, so old
                                                   citations keep working after a document is replaced)
"""
from collections.abc import Callable, Iterable

from contracts.schemas import CitationTarget, CitedSentence, Evidence, SchemeSummary

QUOTE_MAX_CHARS = 600


def validate(sentences: Iterable[CitedSentence], evidence: Iterable[Evidence]) -> tuple[list[CitedSentence], list[CitedSentence]]:
    """Strip citation_ids not present in `evidence`; drop sentences left with none (or blank text)."""
    known = {ev.citation_id for ev in evidence}
    kept, dropped = [], []
    for s in sentences:
        ids = list(dict.fromkeys(c for c in s.citation_ids if c in known))
        if ids and s.text.strip():
            kept.append(CitedSentence(text=s.text.strip(), citation_ids=ids))
        else:
            dropped.append(s)
    return kept, dropped


def validate_summary(summary: SchemeSummary, evidence: list[Evidence]) -> tuple[SchemeSummary, list[CitedSentence]]:
    """validate() applied to every section of a SchemeSummary."""
    sections, dropped = {}, []
    for name in SchemeSummary.model_fields:
        kept, gone = validate(getattr(summary, name), evidence)
        sections[name] = kept
        dropped += gone
    return SchemeSummary(**sections), dropped


def to_target(ev: Evidence) -> CitationTarget:
    """'passage' when the chunk has a bbox (UI can draw a box), else 'page' (UI jumps to the page)."""
    return CitationTarget(
        citation_id=ev.citation_id, doc_id=ev.doc_id, file_url=f"/api/documents/{ev.doc_id}/file",
        page=ev.page, bbox=ev.bbox, quote=ev.text[:QUOTE_MAX_CHARS], source_url=ev.source_url,
        doc_version=ev.doc_version, precision="passage" if ev.bbox else "page")


def _db_lookup(citation_id: str) -> Evidence | None:
    from backend.app.knowledge.scheme_store import load_evidence   # lazy: tests need no DATABASE_URL
    found = load_evidence([citation_id])                              # all versions, NOT filtered on is_current
    return found[0] if found else None


def resolve(citation_id: str, lookup: Callable[[str], Evidence | None] = _db_lookup) -> CitationTarget:
    """Raise KeyError for an unknown citation_id (API maps it to 404 'citation_not_found'); never invent one."""
    ev = lookup(citation_id)
    if ev is None:
        raise KeyError(citation_id)
    return to_target(ev)
