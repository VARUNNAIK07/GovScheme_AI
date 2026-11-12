"""Step 4: section-aware chunks -> data/chunks/{doc_id}.jsonl (one Evidence per line).

    python -m ingestion.chunk [--only pmsby ...] [--force]

* Docling HybridChunker: splits on document structure (headings, lists, tables), never
  across a section, then merges small neighbours up to the token limit (BGE tokenizer).
* chunk_id = {doc_id}-p{page}-c{n}: page = page where the chunk starts, n = 0-based per page.
* bbox = union of the chunk's boxes on its start page, PDF points, origin bottom-left.
* Each line = Evidence fields + token_count + embed_text. embed_text = headings + a short
  tail of the previous chunk in the same section + the chunk text (overlap helps retrieval);
  Evidence.text stays the exact source text that users see and citations quote.
* English only for now: chunks that are mostly Devanagari (e.g. the Hindi half of a bilingual
  PDF) are not indexed; their count is recorded in the .meta.json for later multilingual support.
"""
import argparse
import json

from contracts.schemas import Evidence
from ingestion.common import (chunk_id, devanagari_ratio, get_logger, record_event, read_index, sha256_file, update_index_status, write_json,
                              write_jsonl)
from ingestion.config import get_ingestion_settings
from backend.app.knowledge.embedder import get_tokenizer

log = get_logger("chunk")
CHUNKER_VERSION = "hybrid-v4-en"     # v3: unreadable chunks dropped; v4: TOC/form filler dropped
MAX_CHUNK_DEVANAGARI = 0.5
MAX_UNREADABLE_RATIO = 0.2       # share of U+FFFD replacement characters above which a chunk is garbage
MAX_FILLER_RATIO = 0.25          # share of '.', '_' and '-' filler (TOC leaders, form blanks) above which a chunk is noise


def _filler_ratio(text: str) -> float:
    compact = "".join(text.split())
    return sum(ch in "._-" for ch in compact) / len(compact) if compact else 1.0


def _chunker(cfg):
    from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    tok = HuggingFaceTokenizer(tokenizer=get_tokenizer(), max_tokens=cfg.chunk_max_tokens - cfg.chunk_overlap_tokens)
    return HybridChunker(tokenizer=tok, merge_peers=True)


def _start_page_and_bbox(chunk, doc) -> tuple[int, list[float] | None]:
    provs = [p for item in chunk.meta.doc_items for p in (item.prov or [])]
    if not provs:
        raise ValueError("chunk has no provenance (page unknown)")
    page = min(p.page_no for p in provs)
    height = doc.pages[page].size.height
    boxes = [p.bbox.to_bottom_left_origin(height) for p in provs if p.page_no == page]
    if not boxes:
        return page, None
    return page, [round(min(b.l for b in boxes), 2), round(min(b.b for b in boxes), 2),
                  round(max(b.r for b in boxes), 2), round(max(b.t for b in boxes), 2)]


def chunk_one(row, force: bool = False) -> str:
    from docling_core.types.doc import DoclingDocument
    cfg = get_ingestion_settings()
    parsed = cfg.parsed_dir / f"{row.doc_id}.json"
    out = cfg.chunks_dir / f"{row.doc_id}.jsonl"
    out_meta = cfg.chunks_dir / f"{row.doc_id}.meta.json"
    stamp = {"parsed_sha256": sha256_file(parsed), "chunker": CHUNKER_VERSION,
             "max_tokens": cfg.chunk_max_tokens, "overlap_tokens": cfg.chunk_overlap_tokens}
    if not force and out.exists() and out_meta.exists() and \
            {k: v for k, v in json.loads(out_meta.read_text(encoding="utf-8")).items() if k in stamp} == stamp:
        return "skipped"

    doc = DoclingDocument.load_from_json(parsed)
    tokenizer = get_tokenizer()
    per_page_counter: dict[int, int] = {}
    records, prev_text, prev_headings, skipped_non_english, skipped_unreadable, skipped_filler = [], "", None, 0, 0, 0
    for ch in _chunker(cfg).chunk(dl_doc=doc):
        text = ch.text.strip()
        if not text:
            continue
        if devanagari_ratio(text) > MAX_CHUNK_DEVANAGARI:
            skipped_non_english += 1
            continue
        if text.count("\ufffd") / len(text) > MAX_UNREADABLE_RATIO or not tokenizer.encode(text, add_special_tokens=False):
            skipped_unreadable += 1                # broken font encoding: nothing a citation could quote
            continue
        if _filler_ratio(text) > MAX_FILLER_RATIO:
            skipped_filler += 1                    # table-of-contents dot leaders / blank form lines
            continue
        page, bbox = _start_page_and_bbox(ch, doc)
        n = per_page_counter.get(page, 0)
        per_page_counter[page] = n + 1
        headings = list(ch.meta.headings or [])
        overlap = ""
        if prev_text and headings == prev_headings and cfg.chunk_overlap_tokens:
            tail_ids = tokenizer.encode(prev_text, add_special_tokens=False)[-cfg.chunk_overlap_tokens:]
            overlap = tokenizer.decode(tail_ids)
        embed_text = "\n".join([*headings, f"{overlap} … {text}" if overlap else text])
        cid = chunk_id(row.doc_id, page, n)
        ev = Evidence(citation_id=cid, chunk_id=cid, doc_id=row.doc_id, scheme_id=row.scheme_id,
                      section=" > ".join(headings) or None, page=page, text=text, bbox=bbox,
                      source_url=row.source_url, doc_version=row.version)
        records.append({**ev.model_dump(exclude={"score"}),
                        "token_count": len(tokenizer.encode(text, add_special_tokens=False)),
                        "embed_text": embed_text})
        prev_text, prev_headings = text, headings

    if not records:
        update_index_status(row.doc_id, "failed", "chunk: no chunks produced", stage="chunk")
        return "failed"
    write_jsonl(out, records)
    write_json(out_meta, {**stamp, "doc_id": row.doc_id, "chunks": len(records),
                          "skipped_non_english": skipped_non_english, "skipped_unreadable": skipped_unreadable,
                          "skipped_filler": skipped_filler,
                          "with_bbox": sum(r["bbox"] is not None for r in records),
                          "max_token_count": max(r["token_count"] for r in records)})
    log.info("%s (%s): %d chunks (%d non-English skipped)", row.doc_id, row.scheme_id, len(records),
             skipped_non_english)
    record_event("chunk", "ok", f"{len(records)} chunks, {skipped_non_english} non-English skipped", doc_id=row.doc_id)
    return "chunked"


def run(only: list[str] | None = None, force: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in read_index().values():
        if row.status not in ("parsed", "indexed") or (only and row.scheme_id not in only):
            continue
        try:
            outcome = chunk_one(row, force)
        except Exception as e:
            update_index_status(row.doc_id, "failed", f"chunk error: {e}"[:300], stage="chunk")
            log.exception("%s: chunk error", row.doc_id)
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1
    log.info("chunk done: %s", counts)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run(a.only, a.force)
