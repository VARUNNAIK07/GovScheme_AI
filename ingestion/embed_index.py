"""Step 5: embed chunks with BGE and upsert them into Qdrant 'scheme_chunks'.

    python -m ingestion.embed_index [--only pmsby ...] [--force]

Point IDs are uuid5(chunk_id), so re-running overwrites instead of duplicating.
is_current (retrieval filters on it): new points are written with is_current=False; after
indexing, flags are reconciled with common.current_versions, so a new version replaces the
old one only once it is fully indexed.
"""
import argparse
import json

from contracts.schemas import Evidence
from ingestion.common import (current_versions, get_logger, read_index, read_jsonl, record_event, sha256_file,
                              update_index_status,
                              write_json)
from ingestion.config import get_ingestion_settings
from backend.app.knowledge import qdrant_store
from backend.app.knowledge.embedder import embed_documents

log = get_logger("embed_index")


def _target() -> str:
    cfg = get_ingestion_settings()
    return cfg.qdrant_url or f"local:{cfg.qdrant_path}"


def index_one(row, force: bool = False) -> str:
    cfg = get_ingestion_settings()
    chunks_path = cfg.chunks_dir / f"{row.doc_id}.jsonl"
    marker = cfg.chunks_dir / f"{row.doc_id}.indexed.json"
    stamp = {"chunks_sha256": sha256_file(chunks_path), "collection": qdrant_store.collection_name(),
             "target": _target(), "model": cfg.embed_model}
    if not force and marker.exists() and json.loads(marker.read_text(encoding="utf-8")) == stamp:
        return "skipped"
    records = list(read_jsonl(chunks_path))
    vectors = embed_documents([r["embed_text"] for r in records])
    evidence = [Evidence(**{k: v for k, v in r.items() if k in Evidence.model_fields}) for r in records]
    if marker.exists():                     # re-index: drop the old points first (removed chunks must not linger)
        qdrant_store.delete_document(row.doc_id)
    qdrant_store.upsert_evidence(list(zip(evidence, vectors)), is_current=False)   # store batches + retries
    write_json(marker, stamp)
    update_index_status(row.doc_id, "indexed", stage="embed")
    log.info("%s (%s): %d chunks indexed", row.doc_id, row.scheme_id, len(records))
    return "indexed"


def sync_current_flags() -> None:
    """Set is_current on every indexed document's points from common.current_versions."""
    index = read_index()
    current = current_versions(index)
    for r in index.values():
        if r.status == "indexed":
            qdrant_store.set_is_current(r.doc_id, r.version == current.get(r.source_url))


def run(only: list[str] | None = None, force: bool = False) -> dict[str, int]:
    cfg = get_ingestion_settings()
    index = read_index()
    rows = [r for r in index.values()
            if r.status in ("parsed", "indexed") and (cfg.chunks_dir / f"{r.doc_id}.jsonl").exists()
            and (not only or r.scheme_id in only)]
    qdrant_store.ensure_collection()
    counts: dict[str, int] = {}
    for row in rows:
        try:
            outcome = index_one(row, force=force)
        except Exception as e:
            log.exception("%s: indexing error", row.doc_id)
            update_index_status(row.doc_id, row.status, f"embed error: {e}"[:300])   # keep status; error noted
            record_event("embed", "failed", str(e), doc_id=row.doc_id)
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1
    sync_current_flags()
    log.info("embed_index done: %s", counts)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    try:
        run(a.only, a.force)
    finally:
        qdrant_store.close_client()
