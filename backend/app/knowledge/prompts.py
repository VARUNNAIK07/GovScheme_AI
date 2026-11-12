"""Prompt templates owned by Person A (fact extraction). Versioned: every extraction_runs row
records PROMPT_VERSION, so a prompt change is traceable. (The summary prompt lives in summary.py.)"""
import typing

from contracts.schemas import ProfileAttributes

EXTRACTION_PROMPT_VERSION = "extract-v2"   # v2: monthly->annual income, rules required when eligibility text exists

# Fields an eligibility rule may test (free-text / list fields are not rule targets).
RULE_FIELDS = [f for f in ProfileAttributes.model_fields if f not in ("district", "needs", "sectors_of_interest")]


def _field_lines() -> str:
    lines = []
    for name in RULE_FIELDS:
        ann = ProfileAttributes.model_fields[name].annotation
        lits = [a for a in typing.get_args(ann) if typing.get_origin(a) is typing.Literal]
        if lits:
            kind = "one of " + ", ".join(repr(v) for v in typing.get_args(lits[0]))
        else:
            base = [a for a in typing.get_args(ann) if a is not type(None)]
            kind = getattr(base[0], "__name__", str(base[0])) if base else str(ann)
        lines.append(f"- {name}: {kind}")
    return "\n".join(lines)


EXTRACTION_SYSTEM = f"""You extract facts about ONE Indian government scheme from numbered source chunks.

STRICT RULES
1. Use ONLY the chunks provided. Never use outside knowledge. If something is not stated, leave it out
   (empty list) or use null. Never guess numbers, dates or eligibility.
2. Every item must cite the chunk_ids (exactly as given, e.g. "a60ec28b4d4344a6-p3-c1") whose text supports it.
3. Write facts in short, plain English sentences a citizen can understand. Amounts in INR as integers.
4. Eligibility rules: one rule per condition. Use a profile field from this list ONLY:
{_field_lines()}
   operators: eq, in, not_in, lte, gte, between ([low, high]), is_true, is_false, manual.
   kind = "required" (must be true to qualify) or "exclusion" (if true, the person is NOT eligible).
   Land is in ACRES: convert hectares with 1 hectare = 2.471 acres (round to 2 decimals).
   Income is ANNUAL family income in INR: a monthly limit x 12 (Rs 30,000 per month -> 360000).
   Disability percentage limits go to disability_percent (e.g. "40% or more" -> gte 40).
   If the chunks state ANY eligibility condition, you MUST return at least one rule for it.
   "Small and marginal farmer" without a size in the text -> operator "manual".
   If a condition cannot be expressed with these fields (e.g. income-tax payer, government employee,
   member of another scheme, holds a bank account, pregnant, owns a house, decided by a committee),
   use field "_unmapped" with operator "manual" and value null. Do NOT invent a field.
   source_text = the exact wording from the chunk (short quote).
   confidence = 0..1, how clearly the text states the condition.
5. max_benefit: the largest single benefit amount clearly stated for one beneficiary, with its period
   ("one_time", "per_year", "per_month"); null if not clearly stated.
6. Sector, tags and targeting are NOT your job; only the fields in the JSON schema."""

EXTRACTION_USER = """Scheme: {name} ({scheme_id}), {department}

SOURCE CHUNKS:
{chunks}

Return the JSON object."""

# Retrieval questions used to collect the chunks shown to the model (one search per topic).
EXTRACTION_TOPICS = {
    "overview": "objective and overview of the scheme",
    "eligibility": "who is eligible, eligibility criteria, age, income, category conditions",
    "exclusions": "who is not eligible, exclusion criteria",
    "benefits": "benefits, financial assistance amount, subsidy, pension, insurance cover",
    "documents": "documents required to apply",
    "application": "how to apply, application process, procedure, steps",
    "limitations": "limitations, conditions, restrictions, termination, penalties",
}
