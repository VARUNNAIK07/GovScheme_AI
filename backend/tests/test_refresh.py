"""W6 refresh flow with fakes (no network, no Docling, no DB): order of steps and the RefreshResult."""
from types import SimpleNamespace

from contracts.schemas import RefreshResult
from ingestion import refresh


def test_changed_source_is_reprocessed_and_reported(monkeypatch):
    calls = []
    src = [{"scheme_id": "pmsby", "url": "https://x.gov.in/a.pdf", "fetch": "auto"},
           {"scheme_id": "pm-kmy", "url": "https://x.gov.in/b.pdf", "fetch": "auto"},
           {"scheme_id": "jsy", "url": "https://x.gov.in/c.pdf", "fetch": "manual"}]
    row_new = SimpleNamespace(doc_id="bbbbbbbbbbbbbbbb", version=2)

    class FakeFetcher:
        def fetch_pdf(self, url):
            calls.append(("fetch", url))
            return SimpleNamespace(ok=True, data=url.encode(), http_status=200, error="")

        def robots_verdict(self, url):
            return "allowed"

    monkeypatch.setattr(refresh, "PoliteFetcher", FakeFetcher)
    monkeypatch.setattr(refresh, "load_seed_sources", lambda: src)
    monkeypatch.setattr(refresh, "_record_check", lambda *a: None)
    monkeypatch.setattr(refresh, "record_event", lambda *a, **k: None)
    monkeypatch.setattr(refresh, "register_pdf", lambda data, sid, url, fm:
                        (row_new, "new_version") if sid == "pmsby" else (SimpleNamespace(doc_id="a" * 16), "already_have"))
    monkeypatch.setattr(refresh, "read_index", lambda: {row_new.doc_id: row_new})
    monkeypatch.setattr(refresh.parse, "parse_one", lambda row: calls.append(("parse", row.doc_id)) or "parsed")
    monkeypatch.setattr(refresh.chunk, "chunk_one", lambda row: calls.append(("chunk", row.doc_id)) or "chunked")
    monkeypatch.setattr(refresh.embed_index, "index_one", lambda row: calls.append(("embed", row.doc_id)))
    monkeypatch.setattr(refresh.embed_index, "sync_current_flags", lambda: calls.append(("flags",)))
    monkeypatch.setattr(refresh.load_db, "run", lambda: calls.append(("load",)))
    monkeypatch.setattr(refresh.extract_facts, "extract_one", lambda sid, force: calls.append(("extract", sid, force)))

    result = refresh.run()
    assert result == RefreshResult(changed_docs=["bbbbbbbbbbbbbbbb"], affected_schemes=["pmsby"])
    assert ("fetch", "https://x.gov.in/c.pdf") not in calls                  # manual sources are not fetched
    steps = [c[0] for c in calls if c[0] != "fetch"]
    assert steps == ["parse", "chunk", "embed", "flags", "load", "extract"]  # flags flip only after indexing
    assert ("extract", "pmsby", True) in calls


def test_failed_parse_keeps_old_version_and_reports_nothing(monkeypatch):
    monkeypatch.setattr(refresh, "PoliteFetcher", lambda: SimpleNamespace(
        fetch_pdf=lambda url: SimpleNamespace(ok=True, data=b"%PDF", http_status=200, error=""),
        robots_verdict=lambda url: "allowed"))
    monkeypatch.setattr(refresh, "load_seed_sources", lambda: [{"scheme_id": "s", "url": "u", "fetch": "auto"}])
    monkeypatch.setattr(refresh, "_record_check", lambda *a: None)
    monkeypatch.setattr(refresh, "record_event", lambda *a, **k: None)
    monkeypatch.setattr(refresh, "register_pdf", lambda *a: (SimpleNamespace(doc_id="c" * 16, version=2), "new_version"))
    monkeypatch.setattr(refresh.parse, "parse_one", lambda row: "failed")
    monkeypatch.setattr(refresh.load_db, "run", lambda: (_ for _ in ()).throw(AssertionError("must not load")))
    assert refresh.run() == RefreshResult()
