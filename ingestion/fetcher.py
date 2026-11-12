"""The one polite HTTP client for official sources (used by scrape.py and refresh.py).

Rules enforced here, so callers cannot forget them:
* only hosts in ingestion/allowlist.yaml (redirects to other hosts are refused)
* robots.txt is respected (fetched once per host)
* >= SCRAPER_MIN_DELAY_S between requests to the same host
* bounded retries with backoff, ONLY for timeouts, 429 and 5xx (never for 401/403/404)
* TLS verification always on, using the OS trust store (gov.in servers often omit
  intermediate certificates; Windows fetches them, Python's default store does not)
* body must start with %PDF and stay under SCRAPER_MAX_PDF_MB
* no browser impersonation, no cookies/logins/CAPTCHA handling: a block is recorded as a failure
"""
import socket
import ssl
import time
import urllib.error
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlsplit

import truststore

from ingestion.common import get_logger
from ingestion.config import get_ingestion_settings, load_allowlist

log = get_logger("fetcher")
RETRYABLE_HTTP = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    ok: bool
    data: bytes | None = None
    http_status: int | None = None
    content_type: str = ""
    error: str = ""            # short reason when ok is False (e.g. 'http 403', 'robots.txt disallows')


class _AllowlistRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = (urlsplit(newurl).hostname or "").lower()
        if host not in load_allowlist():
            raise urllib.error.URLError(f"redirect to non-allowlisted host {host!r} refused")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class PoliteFetcher:
    def __init__(self) -> None:
        self.cfg = get_ingestion_settings()
        self.allowlist = load_allowlist()
        self._ssl = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=self._ssl), _AllowlistRedirects())
        self._last_hit: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | str] = {}

    # ── politeness ──
    def _wait(self, host: str) -> None:
        gap = time.monotonic() - self._last_hit.get(host, float("-inf"))
        if gap < self.cfg.scraper_min_delay_s:
            time.sleep(self.cfg.scraper_min_delay_s - gap)
        self._last_hit[host] = time.monotonic()

    def _open(self, url: str, host: str):
        self._wait(host)
        req = urllib.request.Request(url, headers={"User-Agent": self.cfg.user_agent, "Accept": "application/pdf"})
        return self._opener.open(req, timeout=self.cfg.scraper_timeout_s)

    def robots_verdict(self, url: str) -> str:
        """'allowed' | 'disallowed' | 'no-robots' | 'unknown' (unknown = robots.txt unreachable -> we do not fetch)."""
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            try:
                with self._open(base + "/robots.txt", parts.hostname.lower()) as r:
                    rp = urllib.robotparser.RobotFileParser()
                    rp.parse(r.read(512_000).decode("utf-8", "replace").splitlines())
                    self._robots[base] = rp
            except urllib.error.HTTPError as e:
                # RFC 9309: 4xx = no rules; 5xx = treat as unreachable
                self._robots[base] = "no-robots" if 400 <= e.code < 500 else "unknown"
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
                log.warning("robots.txt unreachable for %s: %s", base, e)
                self._robots[base] = "unknown"
        rp = self._robots[base]
        if isinstance(rp, str):
            return rp
        return "allowed" if rp.can_fetch(self.cfg.user_agent, url) else "disallowed"

    # ── main entry ──
    def fetch_pdf(self, url: str) -> FetchResult:
        host = (urlsplit(url).hostname or "").lower()
        if host not in self.allowlist:
            return FetchResult(url, False, error=f"host {host!r} not in allowlist")
        robots = self.robots_verdict(url)
        if robots in ("disallowed", "unknown"):
            return FetchResult(url, False, error=f"robots.txt {robots}")

        max_bytes = self.cfg.scraper_max_pdf_mb * 1024 * 1024
        attempts = self.cfg.scraper_max_retries + 1
        last_error = ""
        for attempt in range(1, attempts + 1):
            try:
                with self._open(url, host) as r:
                    declared = r.headers.get("Content-Length")
                    if declared and declared.isdigit() and int(declared) > max_bytes:
                        return FetchResult(url, False, http_status=r.status, error=f"too large ({int(declared)} bytes)")
                    data = r.read(max_bytes + 1)
                    ctype = r.headers.get("Content-Type", "")
                    if len(data) > max_bytes:
                        return FetchResult(url, False, http_status=r.status, error="too large (> limit)")
                    if not data.lstrip()[:5].startswith(b"%PDF"):
                        return FetchResult(url, False, http_status=r.status, content_type=ctype,
                                           error=f"not a PDF (content-type {ctype!r})")
                    return FetchResult(url, True, data=data, http_status=r.status, content_type=ctype)
            except urllib.error.HTTPError as e:
                last_error = f"http {e.code}"
                if e.code not in RETRYABLE_HTTP:
                    return FetchResult(url, False, http_status=e.code, error=last_error)
            except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError) as e:
                reason = getattr(e, "reason", e)
                last_error = f"{type(reason).__name__}: {reason}"[:200]
                if isinstance(reason, ssl.SSLError):     # certificate problems are not transient
                    return FetchResult(url, False, error=last_error)
            if attempt < attempts:
                backoff = 2 ** attempt
                log.info("retry %d/%d for %s in %ss (%s)", attempt, attempts - 1, url, backoff, last_error)
                time.sleep(backoff)
        return FetchResult(url, False, error=f"gave up after {attempts} attempts: {last_error}")
