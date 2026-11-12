"""Shared helpers for all ingestion steps: IDs, atomic file writes, JSONL, seeds, the
data/index.csv manifest, and logging. Keep step-specific logic out of this module."""
import csv
import hashlib
import io
import json
import logging
import os
import tempfile
import time
import unicodedata
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path

from ingestion.config import SEEDS_DIR, get_ingestion_settings


# ── IDs ──────────────────────────────────────────────────────────────────────
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def doc_id_from_sha(sha256: str) -> str:
    return sha256[:16]


def chunk_id(doc_id: str, page: int, n: int) -> str:
    return f"{doc_id}-p{page}-c{n}"


def devanagari_ratio(text: str) -> float:
    """Share of characters in Devanagari script (Hindi, Marathi, ...); 0.0 for empty text."""
    if not text:
        return 0.0
    return sum("DEVANAGARI" in unicodedata.name(ch, "") for ch in text if ord(ch) > 127) / len(text)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Files ────────────────────────────────────────────────────────────────────
def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write to a temp file in the same folder, then rename: a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def write_json(path: Path, obj) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=1))


def write_jsonl(path: Path, records: Iterable[dict]) -> None:
    atomic_write_text(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))


def read_jsonl(path: Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


# ── Seeds (approved list, committed to git) ──────────────────────────────────
def load_seed_schemes() -> dict[str, dict]:
    with open(SEEDS_DIR / "schemes.csv", newline="", encoding="utf-8") as f:
        return {r["scheme_id"]: r for r in csv.DictReader(f)}


def load_seed_sources() -> list[dict]:
    with open(SEEDS_DIR / "sources.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── data/index.csv: one row per downloaded file (local manifest; mirrored to DB by load_db) ──
@dataclass
class IndexRow:
    doc_id: str
    sha256: str
    scheme_id: str
    source_url: str
    version: int
    local_path: str          # relative to DOCS_DIR
    pages: int
    fetch_method: str        # auto | manual
    status: str              # downloaded | parsed | indexed | failed | duplicate
    error: str
    fetched_at: str
    last_checked: str


INDEX_FIELDS = [f.name for f in fields(IndexRow)]


def read_index() -> dict[str, IndexRow]:
    path = get_ingestion_settings().index_csv
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        rows = {}
        for r in csv.DictReader(f):
            r["version"], r["pages"] = int(r["version"]), int(r["pages"])
            rows[r["doc_id"]] = IndexRow(**r)
        return rows


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    atomic_write_text(path, buf.getvalue())


def write_index(rows: dict[str, IndexRow]) -> None:
    ordered = sorted(rows.values(), key=lambda r: (r.scheme_id, r.version, r.doc_id))
    write_csv(get_ingestion_settings().index_csv, INDEX_FIELDS, (asdict(r) for r in ordered))


def record_event(stage: str, status: str, message: str = "", doc_id: str | None = None,
                 source_url: str | None = None) -> None:
    """Append one processing event to data/logs/events.jsonl (loaded into ingestion_events by load_db)."""
    path = get_ingestion_settings().logs_dir / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {"at": now_iso(), "stage": stage, "status": status, "doc_id": doc_id,
             "source_url": source_url, "message": message[:500]}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def current_versions(rows: dict[str, IndexRow]) -> dict[str, int]:
    """source_url -> the version that retrieval should use (contract: DocumentMeta.is_current).

    A new version becomes current only once it is 'indexed'; until then the newest indexed
    version stays current, so a failed re-download never hides a scheme's existing evidence.
    If nothing is indexed yet, the newest non-failed version is current.
    """
    current: dict[str, int] = {}
    for url in {r.source_url for r in rows.values()}:
        versions = [r for r in rows.values() if r.source_url == url and r.status not in ("duplicate", "failed")]
        indexed = [r.version for r in versions if r.status == "indexed"]
        if indexed or versions:
            current[url] = max(indexed) if indexed else max(r.version for r in versions)
    return current


@contextmanager
def index_lock(timeout_s: float = 60.0, stale_s: float = 300.0):
    """Cross-process lock for read-modify-write of index.csv, so parallel steps (parse, chunk,
    embed) never overwrite each other's status updates. A lock older than stale_s is broken."""
    lock = get_ingestion_settings().docs_dir / "index.csv.lock"
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_s:
                    lock.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"index.csv is locked by another process ({lock})")
            time.sleep(0.1)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def update_index_status(doc_id: str, status: str, error: str = "", stage: str = "") -> None:
    with index_lock():
        rows = read_index()
        rows[doc_id].status = status
        rows[doc_id].error = error
        rows[doc_id].last_checked = now_iso()
        write_index(rows)
    if stage:
        record_event(stage, "failed" if status == "failed" else "ok", error, doc_id=doc_id)


def count_pdf_pages(path: Path) -> int:
    import pypdfium2  # installed with docling
    pdf = pypdfium2.PdfDocument(str(path))
    try:
        return len(pdf)
    finally:
        pdf.close()


def register_pdf(data: bytes, scheme_id: str, source_url: str, fetch_method: str) -> tuple[IndexRow, str]:
    """Store a validated PDF as data/raw/{doc_id}.pdf and record it in index.csv.

    Returns (row, outcome) with outcome 'new' | 'new_version' | 'already_have' | 'duplicate_of_other_source'.
    Same bytes = same document: nothing is written twice.
    """
    with index_lock():
        return _register_pdf_locked(data, scheme_id, source_url, fetch_method)


def _register_pdf_locked(data: bytes, scheme_id: str, source_url: str, fetch_method: str) -> tuple[IndexRow, str]:
    cfg = get_ingestion_settings()
    rows = read_index()
    sha = sha256_bytes(data)
    doc_id = doc_id_from_sha(sha)
    if doc_id in rows:
        existing = rows[doc_id]
        existing.last_checked = now_iso()
        write_index(rows)
        return existing, "already_have" if existing.source_url == source_url else "duplicate_of_other_source"

    raw_path = cfg.raw_dir / f"{doc_id}.pdf"
    atomic_write_bytes(raw_path, data)
    try:
        pages = count_pdf_pages(raw_path)
    except Exception:
        raw_path.unlink(missing_ok=True)       # corrupt PDF: keep no orphan file; caller records the failure
        raise
    prior = [r.version for r in rows.values() if r.source_url == source_url]
    stamp = now_iso()
    row = IndexRow(doc_id=doc_id, sha256=sha, scheme_id=scheme_id, source_url=source_url,
                   version=max(prior, default=0) + 1, local_path=raw_path.relative_to(cfg.docs_dir).as_posix(),
                   pages=pages, fetch_method=fetch_method, status="downloaded", error="",
                   fetched_at=stamp, last_checked=stamp)
    rows[doc_id] = row
    write_index(rows)
    record_event("download", "ok", f"{fetch_method}, {pages} pages", doc_id=doc_id, source_url=source_url)
    return row, "new_version" if prior else "new"


# ── Logging: console + data/logs/ingestion.log ───────────────────────────────
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"ingestion.{name}")
    root = logging.getLogger("ingestion")
    if not root.handlers:
        logs_dir = get_ingestion_settings().logs_dir
        logs_dir.mkdir(parents=True, exist_ok=True)
        fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
        for handler in (logging.StreamHandler(), logging.FileHandler(logs_dir / "ingestion.log", encoding="utf-8")):
            handler.setFormatter(fmt)
            root.addHandler(handler)
        root.setLevel(logging.INFO)
    return logger
