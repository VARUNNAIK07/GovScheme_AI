"""LLM client rules, tested with fake providers (no network, no keys, no cost)."""
import pytest
from pydantic import BaseModel

from backend.app.knowledge import llm


class Out(BaseModel):
    answer: str


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(llm, "configured_providers", lambda: [("groq", "g-model", "k1"), ("gemini", "m-model", "k2")])
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    calls = []

    def install(groq_behaviour, gemini_behaviour):
        behaviours = {"groq": list(groq_behaviour), "gemini": list(gemini_behaviour)}

        def make(name):
            def call(model, key, timeout, system, user, schema):
                calls.append((name, user))
                step = behaviours[name].pop(0)
                if isinstance(step, Exception):
                    raise step
                return step
            return call
        monkeypatch.setattr(llm, "_ADAPTERS", {"groq": make("groq"), "gemini": make("gemini")})
        return calls
    return install


def test_primary_answers(setup):
    calls = setup(['{"answer": "x"}'], [])
    r = llm.complete_json("s", "u", Out)
    assert (r.provider, r.data.answer) == ("groq", "x") and len(calls) == 1


def test_quota_exhausted_falls_back_immediately(setup):
    calls = setup([llm._Fatal("quota exhausted")], ['{"answer": "y"}'])
    r = llm.complete_json("s", "u", Out)
    assert r.provider == "gemini" and [c[0] for c in calls] == ["groq", "gemini"]


def test_transient_errors_are_retried_a_bounded_number_of_times(setup, monkeypatch):
    monkeypatch.setattr(llm.get_settings(), "llm_max_retries", 2)
    calls = setup([llm._Transient("timeout")] * 3, ['{"answer": "z"}'])
    r = llm.complete_json("s", "u", Out)
    assert r.provider == "gemini" and [c[0] for c in calls].count("groq") == 3   # 1 try + 2 retries


def test_invalid_output_gets_one_repair_then_fails_without_switching(setup):
    calls = setup(['not json', '{"wrong": 1}'], ['{"answer": "never used"}'])
    with pytest.raises(llm.LLMInvalidOutput):
        llm.complete_json("s", "u", Out)
    assert [c[0] for c in calls] == ["groq", "groq"]
    assert "previous answer was invalid" in calls[1][1]


def test_repair_succeeds(setup):
    setup(['{"answer": 5}', '{"answer": "fixed"}'], [])
    assert llm.complete_json("s", "u", Out).data.answer == "fixed"


def test_all_providers_failing_raises_with_attempt_log(setup):
    setup([llm._Fatal("HTTP 401 (check key/model name)")], [llm._Fatal("quota exhausted")])
    with pytest.raises(llm.LLMError) as e:
        llm.complete_json("s", "u", Out)
    assert len(e.value.attempts) == 2 and "k1" not in str(e.value) and "k2" not in str(e.value)


def test_request_too_large_falls_back_to_next_provider(setup):
    calls = setup([llm._Fatal("HTTP 413 (request too large for this provider)")], ['{"answer": "ok"}'])
    assert llm.complete_json("s", "u", Out).provider == "gemini"


def test_gemini_network_timeout_is_transient(monkeypatch):
    import httpx
    from google import genai

    class FakeModels:
        def generate_content(self, **kw):
            raise httpx.ReadTimeout("read timed out")

    monkeypatch.setattr(genai, "Client", lambda **kw: type("C", (), {"models": FakeModels()})())
    with pytest.raises(llm._Transient):
        llm._call_gemini("m", "k", 5, "s", "u", {})
