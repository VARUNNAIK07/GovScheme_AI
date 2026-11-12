"""Step 5b: mirror seeds + local manifest into PostgreSQL (idempotent upserts).

    python -m ingestion.load_db

Writes: schemes (+ secondary sectors, tags, states), sources, documents, chunks, ingestion_events.
Seed vocabulary is checked against contracts/constants.py first; unknown values stop the load.
Facts and eligibility rules are written by extract_facts.py, not here.
"""
import json
from datetime import date, datetime
from urllib.parse import urlsplit

from sqlalchemy import case, delete, select, update
from sqlalchemy.dialects.postgresql import insert

from contracts import constants
from ingestion.common import (current_versions, get_logger, load_seed_schemes, load_seed_sources, read_index,
                              read_jsonl, sha256_file, write_json)
from ingestion.config import get_ingestion_settings
from backend.app.db import models as m
from backend.app.db.session import get_engine, session_scope

log = get_logger("load_db")


def _split(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(";") if v.strip()]


def _scheme_states(seed: dict) -> list[str]:
    """Central schemes cover 'ALL'; state schemes list ISO codes in the 'states' column."""
    return [constants.ALL_STATES] if seed["level"] == "central" else _split(seed.get("states", ""))


def validate_seeds(schemes: dict[str, dict]) -> None:
    errors = []
    for sid, s in schemes.items():
        secondary = _split(s["secondary_sectors"])
        if s["primary_sector"] not in constants.SECTORS:
            errors.append(f"{sid}: unknown primary_sector {s['primary_sector']!r}")
        if bad := [x for x in secondary if x not in constants.SECTORS]:
            errors.append(f"{sid}: unknown secondary sectors {bad}")
        if s["primary_sector"] in secondary or len(secondary) > constants.MAX_SECONDARY_SECTORS:
            errors.append(f"{sid}: secondary sectors break rule R5 ({secondary})")
        if bad := [t for t in _split(s["beneficiary_tags"]) if t not in constants.BENEFICIARY_TAGS]:
            errors.append(f"{sid}: unknown beneficiary tags {bad}")
        if bad := [t for t in _split(s["benefit_types"]) if t not in constants.BENEFIT_TYPES]:
            errors.append(f"{sid}: unknown benefit types {bad}")
        states = _scheme_states(s)
        if not states or any(c not in constants.STATES and c != constants.ALL_STATES for c in states):
            errors.append(f"{sid}: level {s['level']!r} needs valid state codes, got {s.get('states')!r}")
    if errors:
        raise ValueError("Seed validation failed:\n  " + "\n  ".join(errors))


def _upsert(session, model, rows: list[dict], keys: list[str]) -> None:
    if not rows:
        return
    stmt = insert(model).values(rows)
    update_cols = {c: stmt.excluded[c] for c in rows[0] if c not in keys}
    stmt = stmt.on_conflict_do_update(index_elements=keys, set_=update_cols) if update_cols \
        else stmt.on_conflict_do_nothing(index_elements=keys)
    session.execute(stmt)


def run() -> dict[str, int]:
    cfg = get_ingestion_settings()
    schemes = load_seed_schemes()
    validate_seeds(schemes)
    today = date.today()
    counts = {}
    # Short, separate transactions: long ones hold row locks that block extraction's updates.
    with session_scope() as s:                                     # 1. scheme seeds + link tables
        _upsert(s, m.SchemeRow, [{
            "scheme_id": sid, "name": r["name"], "department": r["department"], "level": r["level"],
            "primary_sector": r["primary_sector"], "official_url": r["official_url"] or None, "last_checked": today,
        } for sid, r in schemes.items()], ["scheme_id"])
        ids = list(schemes)
        # link tables are replaced wholesale from the seed (the seed is the source of truth for them)
        for model in (m.SchemeSecondarySector, m.SchemeTag, m.SchemeState):
            s.execute(delete(model).where(model.scheme_id.in_(ids)))
        _upsert(s, m.SchemeSecondarySector, [{"scheme_id": sid, "sector_id": x}
                for sid, r in schemes.items() for x in _split(r["secondary_sectors"])], ["scheme_id", "sector_id"])
        _upsert(s, m.SchemeTag, [{"scheme_id": sid, "tag_id": t} for sid, r in schemes.items()
                for t in dict.fromkeys(_split(r["beneficiary_tags"]) + _split(r["benefit_types"]))],
                ["scheme_id", "tag_id"])
        _upsert(s, m.SchemeState, [{"scheme_id": sid, "state_code": code}
                for sid, r in schemes.items() for code in _scheme_states(r)], ["scheme_id", "state_code"])
        _upsert(s, m.Source, [{"scheme_id": x["scheme_id"], "url": x["url"], "host": urlsplit(x["url"]).hostname,
                               "approved": True} for x in load_seed_sources()], ["url"])
    counts["schemes"] = len(schemes)

    index = read_index()
    current = current_versions(index)
    with session_scope() as s:                                     # 2. documents
        source_ids = dict(s.execute(select(m.Source.url, m.Source.source_id)).all())
        doc_rows = []
        for r in index.values():
            if r.status == "duplicate":
                continue
            meta_path = cfg.parsed_dir / f"{r.doc_id}.meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            doc_rows.append({
                "doc_id": r.doc_id, "sha256": r.sha256, "source_id": source_ids[r.source_url], "version": r.version,
                "is_current": r.version == current.get(r.source_url), "title": schemes[r.scheme_id]["name"],
                "local_path": r.local_path, "pages": r.pages, "language": meta.get("language", "en"),
                "text_layer": meta.get("text_layer"), "fetch_method": r.fetch_method,
                "ingestion_status": r.status, "error": r.error or None,
                "fetched_at": datetime.fromisoformat(r.fetched_at), "last_checked": datetime.fromisoformat(r.last_checked)})
        _upsert(s, m.DocumentRow, doc_rows, ["doc_id"])
    counts["sources"], counts["documents"] = len(source_ids), len(doc_rows)

    n_chunks, failed_docs = 0, []
    loaded = _chunk_load_marks()
    for r in index.values():                                       # 3. chunks: one transaction per document
        path = cfg.chunks_dir / f"{r.doc_id}.jsonl"
        if not path.exists():
            continue
        marker = cfg.chunks_dir / f"{r.doc_id}.indexed.json"
        stamp = f"{sha256_file(path)}|{marker.exists()}"
        if loaded.get(r.doc_id) == stamp:
            continue                                               # unchanged since last load into this DB
        embedded_at = datetime.fromtimestamp(marker.stat().st_mtime).astimezone() if marker.exists() else None
        rows = [{"chunk_id": c["chunk_id"], "doc_id": c["doc_id"], "page": c["page"], "section": c["section"],
                 "text": c["text"], "bbox": c["bbox"], "token_count": c["token_count"], "embedded_at": embedded_at}
                for c in read_jsonl(path)]
        try:
            with session_scope() as s:
                _replace_chunks(s, r.doc_id, rows)
        except Exception as e:                                     # one bad document must not block the others
            log.error("%s: chunks not loaded: %s", r.doc_id, str(e).splitlines()[0][:200])
            failed_docs.append(r.doc_id)
            continue
        loaded[r.doc_id] = stamp
        _save_chunk_load_marks(loaded)                             # only after that document committed
        n_chunks += len(rows)
    counts["chunks_loaded"] = n_chunks
    if failed_docs:
        counts["chunk_load_failed"] = len(failed_docs)

    with session_scope() as s:                                     # 4. processing events
        counts["events"], events_pos = _load_events(s, source_ids,
                                                    {r.doc_id for r in index.values() if r.status != "duplicate"})
    # the transaction has committed here; only now remember how far events.jsonl was loaded
    if events_pos is not None:
        positions = _event_positions()
        positions[_db_key()] = events_pos
        write_json(cfg.logs_dir / "events.loaded.json", positions)
    log.info("load_db done: %s", counts)
    return counts


def _norm(text: str) -> str:
    return " ".join(text.split()).lower()


def _replace_chunks(s, doc_id: str, rows: list[dict]) -> None:
    """Replace one document's chunks WITHOUT breaking citations.

    Re-chunking can shift chunk_ids on a page. Facts/rules citing a chunk whose id changed are
    re-pointed to the new chunk with the identical text (deterministic, no LLM). A cited chunk with
    no identical successor is kept (old citations must keep resolving). If an id now holds
    different text and its citation could not be re-pointed, the fact/rule is flagged for review.
    """
    old = dict(s.execute(select(m.ChunkRow.chunk_id, m.ChunkRow.text).where(m.ChunkRow.doc_id == doc_id)).all())
    new_text = {c["chunk_id"]: c["text"] for c in rows}
    new_by_text = {}
    for cid, text in new_text.items():
        new_by_text.setdefault(_norm(text), cid)
    moved = {oid: new_by_text.get(_norm(t)) for oid, t in old.items()
             if oid not in new_text or _norm(new_text[oid]) != _norm(t)}
    cited = set(s.scalars(select(m.SchemeFact.citation_id).where(m.SchemeFact.citation_id.in_(list(moved))))) |         set(s.scalars(select(m.EligibilityRuleRow.citation_id).where(m.EligibilityRuleRow.citation_id.in_(list(moved)))))
    for start in range(0, len(rows), 500):
        _upsert(s, m.ChunkRow, rows[start:start + 500], ["chunk_id"])
    remap = {oid: nid for oid, nid in moved.items() if oid in cited and nid and nid != oid}
    for table in (m.SchemeFact, m.EligibilityRuleRow):
        if remap:
            s.execute(update(table).where(table.citation_id.in_(list(remap)))
                      .values(citation_id=case(remap, value=table.citation_id)))
        broken = [oid for oid in cited if oid in new_text and oid not in remap]   # id reused for other text
        if broken:
            s.execute(update(table).where(table.citation_id.in_(broken), table.review_status != "verified")
                      .values(review_status="flagged"))
    still_cited = set(s.scalars(select(m.SchemeFact.citation_id).where(m.SchemeFact.citation_id.in_(list(old))))) |         set(s.scalars(select(m.EligibilityRuleRow.citation_id).where(m.EligibilityRuleRow.citation_id.in_(list(old)))))
    s.execute(delete(m.ChunkRow).where(m.ChunkRow.doc_id == doc_id, m.ChunkRow.chunk_id.not_in(list(new_text)),
                                       m.ChunkRow.chunk_id.not_in(list(still_cited) or [""])))
    if remap:
        log.info("%s: re-pointed %d citations to re-chunked passages", doc_id, len(remap))


def _chunk_load_marks() -> dict[str, str]:
    path = get_ingestion_settings().logs_dir / "chunks.loaded.json"
    marks = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return marks.get(_db_key(), {})


def _save_chunk_load_marks(doc_marks: dict[str, str]) -> None:
    path = get_ingestion_settings().logs_dir / "chunks.loaded.json"
    marks = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    marks[_db_key()] = doc_marks
    write_json(path, marks)


def _db_key() -> str:
    """Identifies the target database (no password), so each database tracks its own position."""
    return get_engine().url.render_as_string(hide_password=True)


def _event_positions() -> dict[str, int]:
    path = get_ingestion_settings().logs_dir / "events.loaded.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_events(session, source_ids: dict[str, int], known_docs: set[str]) -> tuple[int, int | None]:
    """Insert events.jsonl lines not loaded yet. Returns (inserted, new position for events.loaded)."""
    logs = get_ingestion_settings().logs_dir
    path = logs / "events.jsonl"
    if not path.exists():
        return 0, None
    done = _event_positions().get(_db_key(), 0)
    lines = path.read_text(encoding="utf-8").splitlines()
    new = [json.loads(line) for line in lines[done:] if line.strip()]
    rows = [{"stage": e["stage"], "status": e["status"], "message": e["message"] or None,
             "doc_id": e["doc_id"] if e["doc_id"] in known_docs else None,
             "source_id": source_ids.get(e["source_url"]), "created_at": datetime.fromisoformat(e["at"])}
            for e in new]
    if rows:
        session.execute(insert(m.IngestionEvent).values(rows))
    return len(rows), len(lines)


if __name__ == "__main__":
    run()
