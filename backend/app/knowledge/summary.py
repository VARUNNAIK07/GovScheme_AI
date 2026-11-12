"""Summary Agent helper: summarize_scheme(scheme, eligibility, evidence, attrs) -> SchemeSummary.

* overview / eligibility / benefits / documents / application: written by the LLM (JSON mode) from the
  evidence only, then filtered by citations.validate (uncited or wrongly cited sentences are dropped).
* relevance: personal, so built WITHOUT the LLM from the deterministic eligibility checks; each sentence
  carries the citation of the rule it checks. The profile itself is never sent to the LLM.
"""
from collections.abc import Callable

from pydantic import BaseModel, Field

from contracts.schemas import CitedSentence, EligibilityResult, Evidence, ProfileAttributes, Scheme, SchemeSummary
from backend.app.knowledge import citations

SUMMARY_PROMPT_VERSION = "summary-v1"

SUMMARY_PROMPT = """You summarise an Indian government scheme for a citizen.
Use ONLY the evidence passages below. Do not use outside knowledge. Do not guess amounts, dates or rules.
Every sentence must list the citation_ids of the passages that support it. If the evidence says
nothing for a section, return an empty list for that section.

Scheme: {name}

Evidence passages:
{passages}

Return JSON only, exactly this shape:
{{"overview": [{{"text": "...", "citation_ids": ["..."]}}],
  "eligibility": [], "benefits": [], "documents": [], "application": []}}
"""

SUMMARY_SYSTEM = "You write short, factual, evidence-cited summaries. Output JSON only."


class SummaryDraft(BaseModel):
    """JSON schema the LLM must return (sent to llm.complete_json); relevance is never asked for."""
    overview: list[CitedSentence] = Field(default_factory=list)
    eligibility: list[CitedSentence] = Field(default_factory=list)
    benefits: list[CitedSentence] = Field(default_factory=list)
    documents: list[CitedSentence] = Field(default_factory=list)
    application: list[CitedSentence] = Field(default_factory=list)


LLMJson = Callable[[str], dict]          # prompt -> parsed JSON object
LLM_SECTIONS = ("overview", "eligibility", "benefits", "documents", "application")
RESULT_PREFIX = {"pass": "Matches your profile", "fail": "Does not match your profile",
                 "unknown": "Needs more profile details", "ambiguous": "Needs an official check"}


def _default_llm() -> LLMJson:
    from backend.app.knowledge import llm  # provider-agnostic client (Groq first, Gemini fallback)
    return lambda prompt: llm.complete_json(SUMMARY_SYSTEM, prompt, SummaryDraft).data.model_dump()


def build_prompt(scheme: Scheme, evidence: list[Evidence]) -> str:
    passages = "\n".join(f"[{ev.citation_id}] (page {ev.page}, {ev.section or 'no section'}) {ev.text}"
                         for ev in evidence)
    return SUMMARY_PROMPT.format(name=scheme.name, passages=passages)


def relevance_sentences(eligibility: EligibilityResult, attrs: ProfileAttributes) -> list[CitedSentence]:
    """One sentence per eligibility check that cites its rule. `attrs` decides nothing here beyond what
    B's deterministic checks already used; a sentence with no rule citation is not emitted."""
    out = []
    for check in eligibility.checks:
        if check.citation_id and check.reason.strip():
            out.append(CitedSentence(text=f"{RESULT_PREFIX[check.result]}: {check.reason.strip()}",
                                     citation_ids=[check.citation_id]))
    if attrs.needs and not out:
        return []          # no grounded link between the user's needs and this scheme: say nothing
    return out


def summarize_scheme(scheme: Scheme, eligibility: EligibilityResult, evidence: list[Evidence],
                     attrs: ProfileAttributes, llm: LLMJson | None = None) -> SchemeSummary:
    if not evidence:
        return SchemeSummary(overview=[], relevance=[], eligibility=[], benefits=[], documents=[], application=[])
    raw = (llm or _default_llm())(build_prompt(scheme, evidence))
    sections = {}
    for name in LLM_SECTIONS:
        items = raw.get(name) if isinstance(raw, dict) else None
        parsed = []
        for item in items if isinstance(items, list) else []:
            try:
                parsed.append(CitedSentence.model_validate(item))
            except Exception:
                continue   # malformed item from the LLM: drop it, never repair it into a claim
        sections[name] = parsed
    sections["relevance"] = relevance_sentences(eligibility, attrs)
    summary, _dropped = citations.validate_summary(SchemeSummary(**sections), evidence)
    return summary
