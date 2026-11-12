"""Step 6: LLM-assisted extraction of scheme facts + eligibility rules -> PostgreSQL.

    python -m ingestion.extract_facts --only pmsby pm-kmy      # selected schemes
    python -m ingestion.extract_facts                          # every scheme with indexed chunks
    python -m ingestion.extract_facts --force                  # re-extract even if inputs are unchanged

The LLM proposes; deterministic code decides what is stored:
* every item must cite chunk_ids that were actually shown to the model -> otherwise DROPPED
* the quoted/stated text must overlap the cited chunk's words -> otherwise kept but FLAGGED
* rules must use a real profile field with a type-correct value -> otherwise converted to a
  'manual' rule (shown to users as NEEDS_VERIFICATION, never as eligible) and FLAGGED
Every run is audited in extraction_runs; the raw model output is saved in data/extractions/.
Facts/rules a human marked 'verified' are never overwritten.
"""
import argparse
import re
import time
import typing
from datetime import datetime, timezone

from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from contracts import constants
from contracts.schemas import ProfileAttributes
from ingestion.common import get_logger, record_event, write_json
from ingestion.config import get_ingestion_settings
from backend.app.db import models as m
from backend.app.db.session import session_scope
from backend.app.knowledge import prompts
from backend.app.knowledge.comparison import format_inr
from backend.app.knowledge.llm import LLMError, complete_json
from backend.app.knowledge.retrieval import get_evidence

log = get_logger("extract")
CHUNKS_PER_TOPIC = 4
MAX_CONTEXT_CHARS = 12_000       # ~3k tokens of evidence: prompt + 3k answer budget stays under Groq's 8k TPM
MIN_WORD_OVERLAP = 0.5           # share of a fact's content words that must appear in its cited chunks
RECITE_OVERLAP = 0.8             # a wrongly cited claim is re-pointed only to a shown chunk this well supporting it
STOP_AFTER_CONSECUTIVE_FAILURES = 3   # providers exhausted: stop instead of failing every remaining scheme
PAUSE_BETWEEN_SCHEMES_S = 20     # spread requests across free-tier per-minute windows


# ── what the model must return ──
class CitedText(BaseModel):
    text: str
    citation_ids: list[str]


class MaxBenefit(BaseModel):
    amount_inr: int
    period: typing.Literal["one_time", "per_year", "per_month"]
    citation_ids: list[str]


class ExtractedRule(BaseModel):
    field: str
    operator: typing.Literal["eq", "in", "not_in", "lte", "gte", "between", "is_true", "is_false", "manual"]
    value: typing.Any = None
    kind: typing.Literal["required", "exclusion"]
    source_text: str
    citation_ids: list[str]
    confidence: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    summary: CitedText | None = None
    benefits: list[CitedText] = []
    documents_required: list[CitedText] = []
    application_steps: list[CitedText] = []
    limitations: list[CitedText] = []
    max_benefit: MaxBenefit | None = None
    rules: list[ExtractedRule] = []


# ── deterministic verification ──
_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "of", "to", "and", "or", "in", "for", "is", "are", "be", "on", "with", "by", "as",
         "at", "this", "that", "under", "will", "shall", "from", "any", "all", "per", "rs", "inr"}
_AMOUNT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|crores?|cr)?(?![a-z])")
_SCALE = {"lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000,
          "crore": 10_000_000, "crores": 10_000_000, "cr": 10_000_000}


def amounts(text: str) -> set[int]:
    """Every number in the text as an integer, understanding Indian forms: '2 Lakh' = '2,00,000' = 200000."""
    out = set()
    for num, scale in _AMOUNT.findall(text.lower().replace(" ", " ")):
        try:
            value = float(num.replace(",", ""))
        except ValueError:
            continue
        out.add(round(value * _SCALE.get(scale, 1)))
    return out


def _words(text: str) -> set[str]:
    """Content words, cut to 5 letters so 'terminates'/'termination' match; numbers normalised."""
    text = text.lower().replace(" ", " ")
    words = {w[:5] for w in _WORD.findall(_AMOUNT.sub(" ", text)) if w not in _STOP and len(w) > 1}
    return words | {str(a) for a in amounts(text)}


def support_ratio(claim: str, chunk_texts: list[str]) -> float:
    """Share of the claim's content words found in the cited chunks (0..1)."""
    claim_words = _words(claim)
    if not claim_words:
        return 0.0
    source = set().union(*(_words(t) for t in chunk_texts)) if chunk_texts else set()
    return len(claim_words & source) / len(claim_words)


def _field_kind(field: str):
    ann = ProfileAttributes.model_fields[field].annotation
    args = typing.get_args(ann)
    lits = [a for a in args if typing.get_origin(a) is typing.Literal]
    if lits:
        return "choice", set(typing.get_args(lits[0]))
    base = next((a for a in args if a is not type(None)), ann)
    return {int: "number", float: "number", bool: "bool", str: "text"}.get(base, "text"), None


def rule_problem(rule: ExtractedRule) -> str | None:
    """None if the rule is executable by B's evaluate(); else a short reason."""
    if rule.operator == "manual":
        return None
    if rule.field == constants.UNMAPPED_FIELD:
        return "unmapped field needs operator manual"
    if rule.field not in prompts.RULE_FIELDS:
        return f"unknown profile field {rule.field!r}"
    kind, options = _field_kind(rule.field)
    v, op = rule.value, rule.operator
    num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)  # noqa: E731
    if op in ("is_true", "is_false"):
        return None if kind == "bool" else f"{op} needs a yes/no field"
    if op in ("lte", "gte"):
        return None if kind == "number" and num(v) else f"{op} needs a number on a numeric field"
    if op == "between":
        ok = kind == "number" and isinstance(v, list) and len(v) == 2 and all(num(x) for x in v) and v[0] <= v[1]
        return None if ok else "between needs [low, high] on a numeric field"
    if op in ("in", "not_in"):
        if not isinstance(v, list) or not v:
            return f"{op} needs a non-empty list"
        return None if options is None or set(v) <= options else f"values {sorted(set(v) - options)} not allowed"
    if op == "eq":
        if kind == "choice":
            return None if v in options else f"value {v!r} not allowed"
        if kind == "number":
            return None if num(v) else "eq needs a number"
        if kind == "bool":
            return None if isinstance(v, bool) else "eq needs true/false"
        return None if isinstance(v, str) and v else "eq needs a value"
    return f"unsupported operator {op}"


def collect_evidence(scheme_id: str) -> list:
    seen, chunks = set(), []
    for query in prompts.EXTRACTION_TOPICS.values():
        for ev in get_evidence(scheme_id, query, k=CHUNKS_PER_TOPIC):
            if ev.chunk_id not in seen:
                seen.add(ev.chunk_id)
                chunks.append(ev)
    chunks.sort(key=lambda e: -(e.score or 0))
    picked, used = [], 0
    for ev in chunks:                                  # best-scoring chunks first, within the budget
        if used + len(ev.text) > MAX_CONTEXT_CHARS:
            continue
        picked.append(ev)
        used += len(ev.text)
    return sorted(picked, key=lambda e: (e.doc_id, e.page, e.chunk_id))


def verify(ex: Extraction, chunk_text: dict[str, str]) -> tuple[dict, list[str]]:
    """Return storable facts/rules (+ review_status) and a list of notes about what was dropped/flagged."""
    notes, facts, rules = [], [], []

    def check(item_text: str, cites: list[str], label: str):
        valid = [c for c in dict.fromkeys(cites) if c in chunk_text]
        if not valid:
            notes.append(f"dropped {label}: no valid citation ({cites})")
            return None, None
        ratio = support_ratio(item_text, [chunk_text[c] for c in valid])
        if ratio < MIN_WORD_OVERLAP:                     # model may have cited a neighbouring chunk
            best = max(chunk_text, key=lambda c: (support_ratio(item_text, [chunk_text[c]]), c))
            best_ratio = support_ratio(item_text, [chunk_text[best]])
            if best_ratio >= RECITE_OVERLAP:
                notes.append(f"recited {label}: {valid[0]} -> {best} ({ratio:.2f} -> {best_ratio:.2f})")
                valid, ratio = [best], best_ratio
        status = "unreviewed" if ratio >= MIN_WORD_OVERLAP else "flagged"
        if status == "flagged":
            notes.append(f"flagged {label}: weak support ({ratio:.2f})")
        return valid[0], status

    lists = {"benefit": ex.benefits, "document_required": ex.documents_required,
             "application_step": ex.application_steps, "limitation": ex.limitations}
    if ex.summary:
        lists["summary"] = [ex.summary]
    for kind, items in lists.items():
        pos = 0
        for item in items:
            cite, status = check(item.text, item.citation_ids, kind)
            if cite:
                facts.append({"kind": kind, "position": pos, "text": item.text.strip(), "citation_id": cite,
                              "review_status": status})
                pos += 1

    max_benefit = None
    if ex.max_benefit and ex.max_benefit.amount_inr >= 0:
        valid = [c for c in ex.max_benefit.citation_ids if c in chunk_text]
        found = any(ex.max_benefit.amount_inr in amounts(chunk_text[c]) for c in valid)
        if valid and found:
            max_benefit = ex.max_benefit
            facts.append({"kind": "max_benefit", "position": 0, "citation_id": valid[0], "review_status": "unreviewed",
                          "text": f"Up to {format_inr(ex.max_benefit.amount_inr)} ({ex.max_benefit.period.replace('_', ' ')})"})
        else:
            notes.append(f"dropped max_benefit {ex.max_benefit.amount_inr}: amount not found in cited chunks")

    for i, r in enumerate(ex.rules):
        cite, status = check(r.source_text, r.citation_ids, f"rule {i}")
        if not cite:
            continue
        problem = rule_problem(r)
        field, op, value = r.field, r.operator, r.value
        if problem:
            notes.append(f"rule {i} -> manual: {problem}")
            field, op, value, status = constants.UNMAPPED_FIELD, "manual", None, "flagged"
        elif op == "manual":
            value = None
        rules.append({"field": field, "operator": op, "value": value, "kind": r.kind,
                      "source_text": r.source_text.strip(), "citation_id": cite,
                      "confidence": r.confidence, "review_status": status})
    return {"facts": facts, "rules": rules, "max_benefit": max_benefit,
            "summary": ex.summary.text.strip() if ex.summary and any(f["kind"] == "summary" for f in facts) else None}, notes


def _already_done(s, scheme_id: str) -> bool:
    """Done = a successful run with the current prompt version AND stored facts or rules.
    Re-chunking alone does not trigger re-extraction (citations are re-pointed by load_db);
    changed source PDFs are re-extracted by refresh.py with force=True."""
    ok = s.scalar(select(m.ExtractionRun.run_id).where(
        m.ExtractionRun.scheme_id == scheme_id, m.ExtractionRun.status.in_(("ok", "partial")),
        m.ExtractionRun.prompt_version == prompts.EXTRACTION_PROMPT_VERSION).limit(1))
    has_output = s.scalar(select(m.SchemeFact.fact_id).where(m.SchemeFact.scheme_id == scheme_id).limit(1)) or         s.scalar(select(m.EligibilityRuleRow.rule_id).where(m.EligibilityRuleRow.scheme_id == scheme_id).limit(1))
    return bool(ok and has_output)


def extract_one(scheme_id: str, force: bool = False) -> str:
    cfg = get_ingestion_settings()
    with session_scope() as s:
        scheme = s.get(m.SchemeRow, scheme_id)
    if not force:
        with session_scope() as s:
            if _already_done(s, scheme_id):
                return "skipped"                  # checked BEFORE any search or LLM call
    chunks = collect_evidence(scheme_id)
    if not chunks:
        return "no_evidence"
    chunk_ids = [c.chunk_id for c in chunks]
    chunk_text = {c.chunk_id: c.text for c in chunks}
    context = "\n\n".join(f"[{c.chunk_id}] (page {c.page}{', ' + c.section if c.section else ''})\n{c.text}"
                          for c in chunks)
    user = prompts.EXTRACTION_USER.format(name=scheme.name, scheme_id=scheme_id, department=scheme.department,
                                          chunks=context)
    started = datetime.now(timezone.utc)
    stamp = started.strftime("%Y%m%dT%H%M%S")
    raw_path = cfg.extractions_dir / f"{scheme_id}_{stamp}.json"
    try:
        result = complete_json(prompts.EXTRACTION_SYSTEM, user, Extraction)
        elig = [c.chunk_id for c in chunks if "eligib" in f"{c.section or ''} {c.text}".lower()]
        if not result.data.rules and elig:          # silent omission: ask once, naming the chunks
            log.warning("%s: no rules returned although %d chunks mention eligibility; asking again", scheme_id, len(elig))
            retry = complete_json(prompts.EXTRACTION_SYSTEM, user + "\n\nYou returned no eligibility rules, but chunks "
                                  + ", ".join(elig) + " state eligibility conditions. Extract every condition as a rule "
                                  "(use field _unmapped with operator manual when no profile field fits).", Extraction)
            if retry.data.rules:
                result = retry
    except LLMError as e:
        with session_scope() as s:
            s.add(m.ExtractionRun(scheme_id=scheme_id, provider="-", model="-", input_chunk_ids=chunk_ids,
                                  prompt_version=prompts.EXTRACTION_PROMPT_VERSION, status=(
                                      "invalid_json" if "schema" in str(e) else "failed"),
                                  error=str(e)[:1000], started_at=started, finished_at=datetime.now(timezone.utc)))
        record_event("extract", "failed", f"{scheme_id}: {e}"[:300])
        log.error("%s: extraction failed: %s", scheme_id, e)
        return "failed"

    stored, notes = verify(result.data, chunk_text)
    empty = not stored["facts"] and not stored["rules"]
    if empty:
        notes.append("empty extraction - needs review (previous facts, if any, were kept)")
    if not stored["rules"] and any("eligib" in f"{c.section or ''} {c.text}".lower() for c in chunks):
        notes.append("no eligibility rules extracted although the evidence mentions eligibility - needs review")
    write_json(raw_path, {"scheme_id": scheme_id, "provider": result.provider, "model": result.model,
                          "prompt_version": prompts.EXTRACTION_PROMPT_VERSION, "input_chunk_ids": chunk_ids,
                          "output": result.data.model_dump(), "verification_notes": notes})
    with session_scope() as s:
        run = m.ExtractionRun(scheme_id=scheme_id, provider=result.provider, model=result.model,
                              prompt_version=prompts.EXTRACTION_PROMPT_VERSION, input_chunk_ids=chunk_ids,
                              raw_output_path=raw_path.relative_to(cfg.docs_dir).as_posix(),
                              status="partial" if notes else "ok", error="; ".join(notes)[:2000] or None,
                              started_at=started, finished_at=datetime.now(timezone.utc))
        s.add(run)
        s.flush()
        if empty:                                   # never wipe existing knowledge with an empty answer
            log.warning("%s: empty extraction; existing facts kept", scheme_id)
            return "empty"
        # replace previous machine output; keep anything a human verified
        s.execute(delete(m.SchemeFact).where(m.SchemeFact.scheme_id == scheme_id, m.SchemeFact.review_status != "verified"))
        s.execute(delete(m.EligibilityRuleRow).where(m.EligibilityRuleRow.scheme_id == scheme_id,
                                                     m.EligibilityRuleRow.review_status != "verified"))
        kept = {(k, p) for k, p in s.execute(select(m.SchemeFact.kind, m.SchemeFact.position)
                                             .where(m.SchemeFact.scheme_id == scheme_id))}
        for f in stored["facts"]:
            pos = f["position"]
            while (f["kind"], pos) in kept:          # never collide with a human-verified fact
                pos += 1
            kept.add((f["kind"], pos))
            s.add(m.SchemeFact(scheme_id=scheme_id, run_id=run.run_id, **{**f, "position": pos}))
        taken = set(s.scalars(select(m.EligibilityRuleRow.rule_id).where(m.EligibilityRuleRow.scheme_id == scheme_id)))
        n = 0
        for r in stored["rules"]:
            n += 1
            while f"{scheme_id}-r{n}" in taken:
                n += 1
            s.add(m.EligibilityRuleRow(rule_id=f"{scheme_id}-r{n}", scheme_id=scheme_id, run_id=run.run_id, **r))
        mb = stored["max_benefit"]
        s.execute(update(m.SchemeRow).where(m.SchemeRow.scheme_id == scheme_id).values(
            summary=stored["summary"], max_benefit_inr=mb.amount_inr if mb else None,
            max_benefit_period=mb.period if mb else None,
            facts_status="extracted" if stored["facts"] else "incomplete",
            updated_at=datetime.now(timezone.utc)))
    record_event("extract", "ok", f"{scheme_id}: {len(stored['facts'])} facts, {len(stored['rules'])} rules, "
                 f"{len(notes)} notes via {result.provider}")
    log.info("%s: %d facts, %d rules (%d notes) via %s/%s", scheme_id, len(stored["facts"]), len(stored["rules"]),
             len(notes), result.provider, result.model)
    return "extracted"


def run(only: list[str] | None = None, force: bool = False) -> dict[str, int]:
    with session_scope() as s:
        ids = list(s.scalars(select(m.Source.scheme_id).join(m.DocumentRow)
                             .where(m.DocumentRow.ingestion_status == "indexed", m.DocumentRow.is_current)
                             .distinct().order_by(m.Source.scheme_id)))
    counts: dict[str, int] = {}
    consecutive_failures = 0
    for sid in ids:
        if only and sid not in only:
            continue
        if consecutive_failures >= STOP_AFTER_CONSECUTIVE_FAILURES:
            log.error("stopping: %d schemes in a row failed on every LLM provider (quota/rate limits). "
                      "Re-run later; finished schemes are skipped.", consecutive_failures)
            counts["not_attempted"] = counts.get("not_attempted", 0) + 1
            continue
        try:
            outcome = extract_one(sid, force)
        except Exception as e:
            log.exception("%s: extraction error", sid)
            record_event("extract", "failed", f"{sid}: {e}"[:300])
            outcome = "failed"
        counts[outcome] = counts.get(outcome, 0) + 1
        consecutive_failures = consecutive_failures + 1 if outcome == "failed" else 0
        if outcome == "extracted":
            time.sleep(PAUSE_BETWEEN_SCHEMES_S)
    log.info("extract done: %s", counts)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    try:
        run(a.only, a.force)
    finally:
        from backend.app.knowledge.qdrant_store import close_client
        close_client()
