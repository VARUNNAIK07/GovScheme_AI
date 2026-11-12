"""Ingestion unit tests (no network, no database). Real-data checks run only if data exists."""
import io
import json
import re

import pytest

from contracts import constants
from contracts.schemas import Evidence


@pytest.fixture
def tmp_docs(tmp_path, monkeypatch):
    """Point DOCS_DIR at a temp folder and reset cached settings."""
    from backend.app.core.config import get_settings
    from ingestion.config import get_ingestion_settings
    monkeypatch.setenv("DOCS_DIR", str(tmp_path))
    monkeypatch.setenv("SCRAPER_CONTACT_EMAIL", "test@example.org")
    get_settings.cache_clear()
    get_ingestion_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()
    get_ingestion_settings.cache_clear()


def _tiny_pdf(pages: int = 1, width: int = 200) -> bytes:
    import pypdfium2
    pdf = pypdfium2.PdfDocument.new()
    for _ in range(pages):
        pdf.new_page(width, 200)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    return buf.getvalue()


def test_ids_match_contract_formats():
    from ingestion.common import chunk_id, doc_id_from_sha, sha256_bytes
    doc_id = doc_id_from_sha(sha256_bytes(b"%PDF-1.4 test"))
    assert re.fullmatch(constants.DOC_ID_RE, doc_id)
    assert re.fullmatch(constants.CHUNK_ID_RE, chunk_id(doc_id, 3, 0))


def test_register_dedupes_and_versions(tmp_docs):
    from ingestion.common import read_index, register_pdf
    a, b = _tiny_pdf(1), _tiny_pdf(2)
    row, outcome = register_pdf(a, "pmsby", "https://example.gov.in/a.pdf", "auto")
    assert outcome == "new" and row.version == 1 and row.pages == 1
    assert register_pdf(a, "pmsby", "https://example.gov.in/a.pdf", "auto")[1] == "already_have"
    assert register_pdf(a, "pmsby", "https://example.gov.in/mirror.pdf", "auto")[1] == "duplicate_of_other_source"
    row2, outcome2 = register_pdf(b, "pmsby", "https://example.gov.in/a.pdf", "auto")
    assert outcome2 == "new_version" and row2.version == 2
    assert len(read_index()) == 2
    assert len(list((tmp_docs / "raw").glob("*.pdf"))) == 2


def test_register_rejects_corrupt_pdf_without_leftovers(tmp_docs):
    from ingestion.common import read_index, register_pdf
    with pytest.raises(Exception):
        register_pdf(b"%PDF-1.4 this is not really a pdf", "pmsby", "https://example.gov.in/bad.pdf", "auto")
    assert read_index() == {}
    assert not list((tmp_docs / "raw").glob("*.pdf"))


def test_fetcher_refuses_hosts_outside_allowlist(tmp_docs):
    from ingestion.fetcher import PoliteFetcher
    result = PoliteFetcher().fetch_pdf("https://example.com/scheme.pdf")
    assert not result.ok and "allowlist" in result.error


def test_text_layer_classification():
    from ingestion.parse import classify_text_layer
    assert classify_text_layer([500, 800]) == "digital"
    assert classify_text_layer([0, 3]) == "scanned"
    assert classify_text_layer([500, 0]) == "mixed"


def test_seed_vocabulary_is_valid():
    from ingestion.common import load_seed_schemes, load_seed_sources
    from ingestion.load_db import validate_seeds
    schemes = load_seed_schemes()
    validate_seeds(schemes)
    assert all(re.fullmatch(constants.SCHEME_ID_RE, sid) for sid in schemes)
    assert {s["scheme_id"] for s in load_seed_sources()} <= set(schemes)
    assert {s["fetch"] for s in load_seed_sources()} <= {"auto", "manual"}


def test_real_chunks_are_valid_evidence():
    """Runs against data/chunks if the pipeline has produced any."""
    from ingestion.config import get_ingestion_settings
    files = list(get_ingestion_settings().chunks_dir.glob("*.jsonl"))
    if not files:
        pytest.skip("no chunk files yet")
    for path in files:
        seen = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            ev = Evidence(**rec)
            assert ev.chunk_id == ev.citation_id and ev.chunk_id.startswith(ev.doc_id)
            assert re.fullmatch(constants.CHUNK_ID_RE, ev.chunk_id) and ev.chunk_id not in seen
            seen.add(ev.chunk_id)
            assert int(ev.chunk_id.split("-p")[1].split("-c")[0]) == ev.page
            if ev.bbox:
                x0, y0, x1, y1 = ev.bbox
                assert x0 <= x1 and y0 <= y1, f"{ev.chunk_id}: bbox not normalised"
            assert 0 < rec["token_count"] <= 512 and ev.text.strip()


def test_current_version_waits_until_new_version_is_indexed():
    from ingestion.common import IndexRow, current_versions
    def row(doc, ver, status, url="https://example.gov.in/a.pdf"):
        return IndexRow(doc, doc * 4, "pmsby", url, ver, f"raw/{doc}.pdf", 1, "auto", status, "", "t", "t")
    v1 = row("1" * 16, 1, "indexed")
    assert current_versions({"a": v1, "b": row("2" * 16, 2, "failed")}) == {v1.source_url: 1}
    assert current_versions({"a": v1, "b": row("2" * 16, 2, "parsed")}) == {v1.source_url: 1}
    assert current_versions({"a": v1, "b": row("2" * 16, 2, "indexed")}) == {v1.source_url: 2}
    assert current_versions({"b": row("2" * 16, 1, "downloaded")}) == {v1.source_url: 1}   # nothing indexed yet


def test_index_lock_blocks_a_second_writer(tmp_docs):
    from ingestion.common import index_lock
    with index_lock():
        with pytest.raises(TimeoutError):
            with index_lock(timeout_s=0.3):
                pass
    with index_lock(timeout_s=0.3):        # released after the first holder exits
        pass


def test_toc_and_form_filler_is_detected():
    from ingestion.chunk import MAX_FILLER_RATIO, _filler_ratio
    assert _filler_ratio("IMPLEMENTATION...........................................6") > MAX_FILLER_RATIO
    assert _filler_ratio("STATE: _____________________________ YEAR ___________") > MAX_FILLER_RATIO
    assert _filler_ratio("Farmers aged 18-40 years can join. Pension Rs. 3,000 per month.") < MAX_FILLER_RATIO
