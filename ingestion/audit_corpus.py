"""Step 1: audit the local corpus and register manually downloaded PDFs (safe to re-run).

    python -m ingestion.audit_corpus

* data/raw/: every file must be {doc_id}.pdf whose SHA-256 still matches index.csv (raw files
  are never edited); files missing from index.csv are reported, not deleted.
* data/inbox/: PDFs you downloaded in a browser for 'manual' sources. Name each file
  '{scheme_id}.pdf' (e.g. pmkvy-4.pdf). It is matched to that scheme's manual source URL,
  validated (%PDF, size), de-duplicated by hash, copied to raw/, and moved to inbox/registered/.
Report: data/logs/audit_report.json
"""
import shutil

from ingestion.common import (get_logger, load_seed_sources, now_iso, read_index, register_pdf, sha256_file,
                              write_json)
from ingestion.config import get_ingestion_settings

log = get_logger("audit")


def audit_raw() -> dict:
    cfg = get_ingestion_settings()
    index = read_index()
    on_disk = {p.stem: p for p in cfg.raw_dir.glob("*.pdf")}
    problems = {"hash_mismatch": [], "not_in_index": [], "missing_file": []}
    for doc_id, path in on_disk.items():
        if doc_id not in index:
            problems["not_in_index"].append(path.name)
        elif sha256_file(path) != index[doc_id].sha256:
            problems["hash_mismatch"].append(path.name)
    for doc_id, row in index.items():
        if row.status != "failed" and not (cfg.docs_dir / row.local_path).exists():
            problems["missing_file"].append(doc_id)
    for kind, items in problems.items():
        if items:
            log.warning("raw/ %s: %s", kind, items)
    return {"raw_files": len(on_disk), **problems}


def register_inbox() -> dict:
    cfg = get_ingestion_settings()
    manual = {}
    for s in load_seed_sources():
        if s["fetch"] == "manual":
            manual.setdefault(s["scheme_id"], []).append(s["url"])
    max_bytes = cfg.scraper_max_pdf_mb * 1024 * 1024
    done_dir = cfg.inbox_dir / "registered"
    result = {"registered": [], "rejected": []}
    for path in sorted(cfg.inbox_dir.glob("*.pdf")):
        scheme_id = path.stem.split("__")[0]
        urls = manual.get(scheme_id, [])
        reason = None
        if len(urls) != 1:
            reason = f"no unique manual source URL for scheme '{scheme_id}' in seeds/sources.csv"
        elif path.stat().st_size > max_bytes:
            reason = "larger than SCRAPER_MAX_PDF_MB"
        else:
            data = path.read_bytes()
            if not data.lstrip()[:5].startswith(b"%PDF"):
                reason = "not a PDF (missing %PDF header)"
        if reason:
            result["rejected"].append({"file": path.name, "reason": reason})
            log.warning("inbox %s rejected: %s", path.name, reason)
            continue
        try:
            row, outcome = register_pdf(data, scheme_id, urls[0], "manual")
        except Exception as e:
            result["rejected"].append({"file": path.name, "reason": f"unreadable PDF: {e}"[:200]})
            continue
        done_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), done_dir / path.name)
        result["registered"].append({"file": path.name, "doc_id": row.doc_id, "outcome": outcome})
        log.info("inbox %s -> %s (%s)", path.name, row.doc_id, outcome)
    return result


def run() -> dict:
    report = {"at": now_iso(), "raw": audit_raw(), "inbox": register_inbox()}
    index = read_index()
    report["index"] = {status: sum(r.status == status for r in index.values())
                       for status in sorted({r.status for r in index.values()})}
    write_json(get_ingestion_settings().logs_dir / "audit_report.json", report)
    log.info("audit done: %s", report["index"])
    return report


if __name__ == "__main__":
    run()
