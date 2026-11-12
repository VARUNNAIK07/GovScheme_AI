"""The ONE LLM client (Groq + Gemini behind a common interface). JSON output only.

    result = complete_json(system, user, MyPydanticModel)   # -> LLMResult(data, provider, model, ...)

Behaviour (configurable in .env: LLM_PROVIDER_PRIORITY, *_MODEL, LLM_TIMEOUT_S, LLM_MAX_RETRIES):
* Providers are tried in priority order. A provider is skipped when it is not configured.
* Transient errors (timeout, connection, 5xx, short rate limit) -> bounded retries with backoff
  on the SAME provider, then fall back to the next provider.
* Quota exhausted / bad key / model not found -> fall back to the next provider immediately.
* A valid HTTP answer that is not valid JSON for the schema -> ONE repair attempt on the same
  provider (the validation error is sent back); then LLMInvalidOutput. We never switch provider
  just because a model gave a poor answer.
* Logs provider, model, outcome and latency only; never keys or prompts.
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from backend.app.core.config import get_settings

log = logging.getLogger("knowledge.llm")
# Free tiers count prompt + RESERVED answer tokens against per-minute limits (Groq: 8k TPM), so the
# answer budget is capped explicitly instead of using the provider default.
MAX_OUTPUT_TOKENS = 3000
T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """No provider produced an answer. .attempts lists what happened (no secrets)."""

    def __init__(self, message: str, attempts: list[str]):
        super().__init__(f"{message}: {' | '.join(attempts)}")
        self.attempts = attempts


class LLMInvalidOutput(LLMError):
    """A provider answered, but the answer did not match the schema even after one repair try."""


@dataclass
class LLMResult:
    data: BaseModel
    provider: str
    model: str
    latency_s: float
    attempts: list[str] = field(default_factory=list)


class _Transient(Exception):
    pass


class _Fatal(Exception):          # quota / auth / model-not-found: move to the next provider
    pass


# ── provider adapters: (system, user, json_schema) -> raw text ──
def _call_groq(model: str, key: str, timeout: float, system: str, user: str, schema: dict) -> str:
    import groq
    client = groq.Groq(api_key=key, timeout=timeout, max_retries=0)
    try:
        extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}   # thinking tokens count against limits
        resp = client.chat.completions.create(
            model=model, temperature=0, max_completion_tokens=MAX_OUTPUT_TOKENS, **extra,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system + "\n\nReturn ONLY a JSON object matching this JSON schema:\n"
                       + json.dumps(schema)},
                      {"role": "user", "content": user}])
        return resp.choices[0].message.content or ""
    except (groq.APITimeoutError, groq.APIConnectionError, groq.InternalServerError) as e:
        raise _Transient(type(e).__name__) from e
    except groq.RateLimitError as e:
        text = str(e).lower()
        if "per day" in text or "quota" in text or "tokens per day" in text:
            raise _Fatal("quota exhausted") from e
        raise _Transient("rate limited") from e
    except (groq.AuthenticationError, groq.PermissionDeniedError, groq.NotFoundError) as e:
        raise _Fatal(f"{type(e).__name__} (check key/model name)") from e
    except groq.APIStatusError as e:              # any other HTTP status, e.g. 413 request too large
        if e.status_code >= 500:
            raise _Transient(f"HTTP {e.status_code}") from e
        raise _Fatal(f"HTTP {e.status_code} ({'request too large for this provider' if e.status_code == 413 else 'rejected'})") from e


def _call_gemini(model: str, key: str, timeout: float, system: str, user: str, schema: dict) -> str:
    from google import genai
    from google.genai import errors, types
    client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=int(timeout * 1000)))
    try:
        resp = client.models.generate_content(
            model=model, contents=user,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0,
                                               response_mime_type="application/json",
                                               max_output_tokens=MAX_OUTPUT_TOKENS,
                                               response_json_schema=schema))
        return resp.text or ""
    except errors.APIError as e:
        code = getattr(e, "code", None)
        if code == 429:
            raise (_Fatal("quota exhausted") if "quota" in str(e).lower() else _Transient("rate limited")) from e
        if code in (401, 403, 404):
            raise _Fatal(f"HTTP {code} (check key/model name)") from e
        if code is None or code >= 500:
            raise _Transient(f"HTTP {code}") from e
        raise _Fatal(f"HTTP {code}") from e
    except (TimeoutError, ConnectionError, OSError, httpx.TransportError) as e:   # incl. httpx.ReadTimeout
        raise _Transient(type(e).__name__) from e


_ADAPTERS = {"groq": _call_groq, "gemini": _call_gemini}


def _parse(raw: str, schema: type[T]) -> T:
    text = raw.strip()
    if text.startswith("```"):                       # tolerate a fenced block, nothing more
        text = text.strip("`").removeprefix("json").strip()
    return schema.model_validate_json(text)


def configured_providers() -> list[tuple[str, str, str]]:
    s = get_settings()
    out = []
    for name in [p.strip().lower() for p in s.llm_provider_priority.split(",") if p.strip()]:
        key, model = getattr(s, f"{name}_api_key", None), getattr(s, f"{name}_model", None)
        if name in _ADAPTERS and key and model:
            out.append((name, model, key.get_secret_value()))
            fallback = getattr(s, f"{name}_fallback_model", None)
            if fallback and fallback != model:          # same provider, separate per-model quota
                out.append((name, fallback, key.get_secret_value()))
    return out


def complete_json(system: str, user: str, schema: type[T]) -> LLMResult:
    s = get_settings()
    providers = configured_providers()
    if not providers:
        raise LLMError("no LLM provider configured", ["set GROQ_*/GEMINI_* in .env"])
    json_schema = schema.model_json_schema()
    attempts: list[str] = []
    for name, model, key in providers:
        call = _ADAPTERS[name]
        prompt = user
        repaired = False
        tries = 0
        while True:
            tries += 1
            started = time.monotonic()
            try:
                raw = call(model, key, s.llm_timeout_s, system, prompt, json_schema)
            except _Transient as e:
                attempts.append(f"{name}: transient ({e}) try {tries}")
                log.warning("llm %s/%s transient error: %s (try %d)", name, model, e, tries)
                if tries > s.llm_max_retries:
                    break                                   # fall back to next provider
                time.sleep(min(2 ** tries, 20))
                continue
            except _Fatal as e:
                attempts.append(f"{name}: {e}")
                log.warning("llm %s/%s unavailable: %s", name, model, e)
                break
            latency = time.monotonic() - started
            try:
                data = _parse(raw, schema)
            except (ValidationError, ValueError) as e:
                attempts.append(f"{name}: invalid JSON for schema")
                if repaired:
                    log.error("llm %s/%s invalid output after repair", name, model)
                    raise LLMInvalidOutput("model output did not match the schema", attempts) from e
                repaired = True
                prompt = (f"{user}\n\nYour previous answer was invalid for the required JSON schema. "
                          f"Errors: {str(e)[:1500]}\nReturn corrected JSON only.")
                continue
            attempts.append(f"{name}: ok")
            log.info("llm %s/%s ok in %.1fs", name, model, latency)
            return LLMResult(data=data, provider=name, model=model, latency_s=round(latency, 2), attempts=attempts)
    raise LLMError("all LLM providers failed", attempts)
