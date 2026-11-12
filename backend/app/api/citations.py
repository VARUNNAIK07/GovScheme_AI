from pathlib import Path

from contracts.schemas import CitationTarget

from backend.app.core.config import get_settings


def resolve(citation_id: str) -> CitationTarget:
    """Raises KeyError for an unknown citation (mapped to 404); never invents one."""
    from backend.app.knowledge import citations
    return citations.resolve(citation_id)


def document_path(doc_id: str) -> Path:
    """Local path of an ingested PDF (raw file, never edited). Raises KeyError if unknown or missing."""
    from sqlalchemy import select
    from backend.app.db import models as m
    from backend.app.db.session import session_scope
    with session_scope() as s:
        local = s.scalar(select(m.DocumentRow.local_path).where(m.DocumentRow.doc_id == doc_id))
    if not local:
        raise KeyError(doc_id)
    docs = get_settings().docs_dir.resolve()
    path = (docs / local).resolve()
    if docs not in path.parents or not path.is_file():      # never serve anything outside DOCS_DIR
        raise KeyError(doc_id)
    return path
