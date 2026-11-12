"""Run the offline pipeline in order. Every step skips work that is already done.

    python -m ingestion.run_all                         # everything approved
    python -m ingestion.run_all --only pmsby pm-kmy     # selected schemes
    python -m ingestion.run_all --skip-db               # files + Qdrant only (no PostgreSQL)

Order: preflight -> audit_corpus -> scrape -> parse -> chunk -> embed_index -> load_db
(extract_facts runs separately once LLM keys are configured.)
"""
import argparse
import sys

from ingestion import audit_corpus, chunk, embed_index, load_db, parse, preflight, scrape
from ingestion.common import get_logger

log = get_logger("run_all")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="scheme_ids to process")
    ap.add_argument("--skip-db", action="store_true", help="do not require or write PostgreSQL")
    a = ap.parse_args()

    if not a.skip_db and not preflight.run():
        log.error("preflight failed; fix .env / connectivity first (or use --skip-db)")
        return 1
    audit_corpus.run()
    scrape.run(a.only)
    parse.run(a.only)
    chunk.run(a.only)
    embed_index.run(a.only)
    if not a.skip_db:
        load_db.run()
    audit_corpus.run()      # final status summary in data/logs/audit_report.json
    return 0


if __name__ == "__main__":
    sys.exit(main())
