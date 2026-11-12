"""Step 2: download approved sources that are not downloaded yet (safe to re-run).

    python -m ingestion.scrape                       # all approved 'auto' sources
    python -m ingestion.scrape --only pmsby pm-kmy   # selected schemes

Sources marked fetch=manual are never downloaded automatically; put those files in
data/inbox/ and run ingestion.audit_corpus. Failures are written to data/logs/scrape_failures.csv.
"""
import argparse

from ingestion.common import (get_logger, load_seed_sources, now_iso, read_index, record_event, register_pdf,
                              write_csv)
from ingestion.config import get_ingestion_settings
from ingestion.fetcher import PoliteFetcher

log = get_logger("scrape")


def run(only: list[str] | None = None) -> dict[str, int]:
    cfg = get_ingestion_settings()
    have_urls = {r.source_url for r in read_index().values() if r.status != "failed"}
    sources = [s for s in load_seed_sources() if s["fetch"] == "auto" and (not only or s["scheme_id"] in only)]
    fetcher = PoliteFetcher()
    counts = {"downloaded": 0, "skipped": 0, "failed": 0}
    failures = []
    for s in sources:
        if s["url"] in have_urls:
            counts["skipped"] += 1
            continue
        result = fetcher.fetch_pdf(s["url"])
        if not result.ok:
            counts["failed"] += 1
            failures.append({"scheme_id": s["scheme_id"], "url": s["url"], "error": result.error, "at": now_iso()})
            log.warning("FAILED %s: %s", s["scheme_id"], result.error)
            record_event("download", "failed", result.error, source_url=s["url"])
            continue
        try:
            row, outcome = register_pdf(result.data, s["scheme_id"], s["url"], "auto")
        except Exception as e:  # corrupt PDF etc. — recorded, not hidden
            counts["failed"] += 1
            failures.append({"scheme_id": s["scheme_id"], "url": s["url"], "error": f"unreadable PDF: {e}"[:200], "at": now_iso()})
            log.warning("FAILED %s: unreadable PDF (%s)", s["scheme_id"], e)
            record_event("download", "failed", f"unreadable PDF: {e}", source_url=s["url"])
            continue
        counts["downloaded"] += 1
        log.info("%s %s -> %s (%d pages, %s)", outcome, s["scheme_id"], row.doc_id, row.pages, row.local_path)

    if failures:
        path = cfg.logs_dir / "scrape_failures.csv"
        write_csv(path, ["scheme_id", "url", "error", "at"], failures)
        log.warning("%d failures listed in %s", len(failures), path)
    log.info("scrape done: %s", counts)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="scheme_ids to process")
    run(ap.parse_args().only)
