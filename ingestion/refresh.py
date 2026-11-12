"""W6: re-check official sources; re-ingest changed PDFs as new versions (safe to re-run).

    python -m ingestion.refresh                     # every approved 'auto' source
    python -m ingestion.refresh --doc-id <doc_id>   # only the source of one document
    python -m ingestion.refresh --scheme pm-kmy     # only one scheme's sources

Returns contracts.schemas.RefreshResult(changed_docs, affected_schemes). B's controller adds
invalidated_runs (workflow_runs whose scheme_ids overlap affected_schemes).

* Same bytes (SHA-256) = unchanged; nothing is re-processed.
* New bytes = new version: parse -> chunk -> embed -> facts re-extracted for that scheme.
  The previous version stays current until the new one is fully indexed (common.current_versions),
  so a failed refresh never removes a scheme's evidence; old citations keep resolving.
* 'manual' sources cannot be re-checked automatically and are reported, not fetched.
"""
import argparse
from datetime import datetime, timezone

from sqlalchemy import update

from contracts.schemas import RefreshResult
from ingestion import chunk, embed_index, extract_facts, load_db, parse
from ingestion.common import get_logger, load_seed_sources, read_index, record_event, register_pdf
from ingestion.fetcher import PoliteFetcher
from backend.app.db import models as m
from backend.app.db.session import session_scope

log = get_logger("refresh")


def _sources(doc_id: str | None, scheme_id: str | None) -> list[dict]:
    sources = load_seed_sources()
    if doc_id:
        row = read_index().get(doc_id)
        if row is None:
            raise KeyError(f"unknown doc_id {doc_id}")
        sources = [s for s in sources if s["url"] == row.source_url]
    if scheme_id:
        sources = [s for s in sources if s["scheme_id"] == scheme_id]
    return sources


def _record_check(url: str, status: str, robots: str | None) -> None:
    with session_scope() as s:
        s.execute(update(m.Source).where(m.Source.url == url).values(
            last_status=status, robots=robots, last_checked=datetime.now(timezone.utc)))


def run(doc_id: str | None = None, scheme_id: str | None = None) -> RefreshResult:
    fetcher = PoliteFetcher()
    changed_docs: list[str] = []
    affected: list[str] = []
    for src in _sources(doc_id, scheme_id):
        if src["fetch"] != "auto":
            log.info("skip manual source for %s: %s", src["scheme_id"], src["url"])
            continue
        result = fetcher.fetch_pdf(src["url"])
        robots = fetcher.robots_verdict(src["url"])
        if not result.ok:
            _record_check(src["url"], result.error[:60], robots)
            record_event("refresh", "failed", result.error, source_url=src["url"])
            log.warning("%s: re-check failed (%s); current version kept", src["scheme_id"], result.error)
            continue
        _record_check(src["url"], str(result.http_status), robots)
        row, outcome = register_pdf(result.data, src["scheme_id"], src["url"], "auto")
        if outcome != "new_version":
            continue
        log.info("%s: CHANGED -> new version %d (%s)", src["scheme_id"], row.version, row.doc_id)
        record_event("refresh", "ok", f"new version {row.version}", doc_id=row.doc_id, source_url=src["url"])
        # process just this document; each step records failures and keeps the old version current
        if parse.parse_one(row) == "failed":
            continue
        row = read_index()[row.doc_id]
        if chunk.chunk_one(row) == "failed":
            continue
        embed_index.index_one(read_index()[row.doc_id])
        changed_docs.append(row.doc_id)
        affected.append(src["scheme_id"])

    if changed_docs:
        embed_index.sync_current_flags()          # new versions become current, old ones retire
        load_db.run()
        for sid in dict.fromkeys(affected):
            extract_facts.extract_one(sid, force=True)
    result = RefreshResult(changed_docs=changed_docs, affected_schemes=list(dict.fromkeys(affected)))
    log.info("refresh done: %d changed docs, schemes %s", len(changed_docs), result.affected_schemes)
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc-id")
    ap.add_argument("--scheme")
    a = ap.parse_args()
    try:
        print(run(a.doc_id, a.scheme).model_dump_json(indent=1))
    finally:
        from backend.app.knowledge.qdrant_store import close_client
        close_client()
