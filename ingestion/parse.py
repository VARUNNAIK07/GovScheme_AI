"""Step 3: parse PDFs with Docling -> data/parsed/{doc_id}.json (+ .meta.json quality report).

    python -m ingestion.parse [--only pmsby ...] [--force]

1. Text-layer check per page (pypdfium2): digital pages use embedded text, OCR only when needed.
2. Docling conversion (layout, headings, tables, page numbers, bounding boxes).
3. Quality check: empty pages, garbled text, non-English script. Problems are recorded and
   logged; a document with (almost) no text is marked failed instead of being chunked.
"""
import argparse
import json
from importlib.metadata import version as pkg_version
from pathlib import Path

from ingestion.common import devanagari_ratio, get_logger, now_iso, read_index, update_index_status, write_json
from backend.app.core.config import DOCLING_ARTIFACTS_DIR
from ingestion.config import get_ingestion_settings

log = get_logger("parse")

MIN_TEXT_CHARS_PER_PAGE = 50     # below this a page has no usable text layer
MIN_DOC_CHARS = 200              # below this the whole parse is treated as failed
MIN_ALPHA_RATIO = 0.60           # letters+digits+spaces share of all chars; lower = likely garbled
MAX_DEVANAGARI_RATIO = 0.20      # above this the document is not English (English-only for now)


def text_layer_profile(pdf_path: Path) -> list[int]:
    """Characters in the embedded text layer of each page (0 = scanned image page)."""
    import pypdfium2
    pdf = pypdfium2.PdfDocument(str(pdf_path))
    try:
        counts = []
        for i in range(len(pdf)):
            textpage = pdf[i].get_textpage()
            counts.append(len(textpage.get_text_range().strip()))
            textpage.close()
        return counts
    finally:
        pdf.close()


def classify_text_layer(chars_per_page: list[int]) -> str:
    with_text = sum(c >= MIN_TEXT_CHARS_PER_PAGE for c in chars_per_page)
    if with_text == len(chars_per_page):
        return "digital"
    return "scanned" if with_text == 0 else "mixed"


def _converter(text_layer: str):
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    if not (DOCLING_ARTIFACTS_DIR / "model_artifacts_ok").exists():
        raise RuntimeError("Docling models missing: run  python -m ingestion.download_models")
    opts = PdfPipelineOptions(artifacts_path=DOCLING_ARTIFACTS_DIR)   # local models only, no runtime downloads
    opts.do_table_structure = True
    opts.do_ocr = text_layer != "digital"          # never OCR over good embedded text
    if text_layer == "scanned":
        opts.ocr_options.force_full_page_ocr = True
    return DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)})


def quality_report(doc, n_pages: int) -> dict:
    per_page = {p: 0 for p in range(1, n_pages + 1)}
    all_text = []
    for item, _level in doc.iterate_items():
        text = getattr(item, "text", "") or ""
        table = getattr(item, "data", None)
        if not text and table is not None and hasattr(table, "table_cells"):   # tables keep text in cells
            text = " ".join(cell.text for cell in table.table_cells if cell.text)
        if not text:
            continue
        all_text.append(text)
        for prov in getattr(item, "prov", []) or []:
            per_page[prov.page_no] = per_page.get(prov.page_no, 0) + len(text)
    joined = " ".join(all_text)
    total = len(joined) or 1
    alpha = sum(ch.isalnum() or ch.isspace() for ch in joined) / total
    deva = devanagari_ratio(joined)
    flags = []
    empty_pages = [p for p, c in per_page.items() if c < MIN_TEXT_CHARS_PER_PAGE]
    if empty_pages:
        flags.append(f"low_text_pages:{empty_pages}")
    if alpha < MIN_ALPHA_RATIO:
        flags.append(f"possibly_garbled(alpha_ratio={alpha:.2f})")
    if deva > MAX_DEVANAGARI_RATIO:
        flags.append(f"non_english(devanagari_ratio={deva:.2f})")
    return {"chars_total": len(joined), "chars_per_page": per_page, "alpha_ratio": round(alpha, 3),
            "devanagari_ratio": round(deva, 3), "language": "hi" if deva > 0.5 else ("mixed" if deva > MAX_DEVANAGARI_RATIO else "en"),
            "flags": flags}


def parse_one(row, force: bool = False, recheck: bool = False) -> str:
    """recheck=True: re-run only the quality check on the saved Docling JSON (no re-conversion/OCR)."""
    cfg = get_ingestion_settings()
    pdf_path = cfg.docs_dir / row.local_path
    out_json = cfg.parsed_dir / f"{row.doc_id}.json"
    out_meta = cfg.parsed_dir / f"{row.doc_id}.meta.json"
    up_to_date = out_json.exists() and out_meta.exists() and         json.loads(out_meta.read_text(encoding="utf-8")).get("source_sha256") == row.sha256

    if recheck and up_to_date:
        from docling_core.types.doc import DoclingDocument
        meta = json.loads(out_meta.read_text(encoding="utf-8"))
        doc = DoclingDocument.load_from_json(out_json)
        report = quality_report(doc, meta["pages"])
        meta.update(report, rechecked_at=now_iso())
        write_json(out_meta, meta)
    elif up_to_date and not force:
        return "skipped"
    else:
        layer_chars = text_layer_profile(pdf_path)
        text_layer = classify_text_layer(layer_chars)
        log.info("%s (%s): %d pages, text layer %s -> OCR %s", row.doc_id, row.scheme_id, len(layer_chars),
                 text_layer, "on" if text_layer != "digital" else "off")
        result = _converter(text_layer).convert(pdf_path)
        doc = result.document
        report = quality_report(doc, len(layer_chars))
        meta = {"doc_id": row.doc_id, "scheme_id": row.scheme_id, "source_sha256": row.sha256,
                "pages": len(layer_chars), "text_layer": text_layer, "text_layer_chars_per_page": layer_chars,
                "ocr_used": text_layer != "digital", "conversion_status": str(result.status),
                "docling_version": pkg_version("docling"), "parsed_at": now_iso(), **report}
        out_json.parent.mkdir(parents=True, exist_ok=True)
        doc.save_as_json(out_json)
        write_json(out_meta, meta)

    if report["chars_total"] < MIN_DOC_CHARS:
        update_index_status(row.doc_id, "failed", f"parse: only {report['chars_total']} chars extracted", stage="parse")
        log.error("%s: almost no text extracted -> failed", row.doc_id)
        return "failed"
    if report["flags"]:
        log.warning("%s quality flags: %s", row.doc_id, report["flags"])
    update_index_status(row.doc_id, "parsed", "; ".join(report["flags"]), stage="parse")
    return "parsed"


def run(only: list[str] | None = None, force: bool = False, recheck: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    # smallest documents first: most schemes become searchable early; huge OCR jobs run last
    for row in sorted(read_index().values(), key=lambda r: (r.pages, r.doc_id)):
        if row.status in ("failed", "duplicate") or (only and row.scheme_id not in only):
            continue
        try:
            outcome = parse_one(row, force, recheck)
        except Exception as e:
            update_index_status(row.doc_id, "failed", f"parse error: {e}"[:300], stage="parse")
            log.exception("%s: parse error", row.doc_id)
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1
    log.info("parse done: %s", counts)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true", help="re-parse even if output is up to date")
    ap.add_argument("--recheck", action="store_true", help="re-run only the quality check on saved output")
    a = ap.parse_args()
    run(a.only, a.force, a.recheck)
