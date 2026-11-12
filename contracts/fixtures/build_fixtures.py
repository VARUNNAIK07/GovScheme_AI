"""Rebuild contracts/fixtures/*.json, sample.pdf and contracts/personas.json through the contract models.

    python -m contracts.fixtures.build_fixtures        (repo root; needs data/chunks/195a99298e85821b.jsonl)

Evidence comes from the real PMSBY chunks, scheme facts are verbatim substrings of them (quote() fails
if the wording is not there). Statuses/scores are synthetic and marked [FIXTURE].
"""
import csv
import json
import shutil
from pathlib import Path

from contracts import constants as K
from contracts import schemas as c

ROOT = Path(__file__).resolve().parents[2]
FX = ROOT / "contracts" / "fixtures"
DOC = "195a99298e85821b"
TAG = "[FIXTURE] "
NOTE = ("Contract fixture for stubs/MSW. Evidence/citations are REAL chunks of the official PMSBY Rules PDF "
        "(jansuraksha.gov.in, doc_id 195a99298e85821b, copied to fixtures/sample.pdf). Statuses, scores and "
        "anything marked [FIXTURE] are synthetic and must never be shown as real results.")

# ── real evidence ──
chunks = [json.loads(l) for l in (ROOT / "data/chunks" / f"{DOC}.jsonl").read_text(encoding="utf-8").splitlines()]
EV = {r["chunk_id"]: c.Evidence(**{k: v for k, v in r.items() if k in c.Evidence.model_fields}) for r in chunks}
P1C0, P1C1, P2C0, P3C0 = (f"{DOC}-p1-c0", f"{DOC}-p1-c1", f"{DOC}-p2-c0", f"{DOC}-p3-c0")
assert set(EV) == {P1C0, P1C1, P2C0, P3C0}


def quote(cid: str, start: str, end: str) -> str:
    """Verbatim substring of a real chunk (fails loudly if the wording is not in the chunk)."""
    t = EV[cid].text
    i = t.index(start)
    j = t.index(end, i) + len(end)
    return t[i:j]


def cs(cid: str, start: str, end: str) -> c.CitedSentence:
    return c.CitedSentence(text=quote(cid, start, end), citation_ids=[cid])


seeds = {r["scheme_id"]: r for r in csv.DictReader((ROOT / "ingestion/seeds/schemes.csv").open(encoding="utf-8"))}


def card(sid, status, reason, match):
    s = seeds[sid]
    return c.LibraryCard(scheme_id=sid, name=s["name"], department=s["department"], sector=s["primary_sector"],
                         eligibility_status=status, eligibility_reason=TAG + reason, match_percent=match)


def split(v):
    return [x for x in v.split(";") if x]


# ── personas (synthetic) ──
personas = [
    {"persona_id": "farmer_rural", "label": "Farmer in a rural district", "attributes": c.ProfileAttributes(
        age=45, gender="male", state="IN-UP", district="Barabanki", area_type="rural", social_category="obc",
        annual_family_income_inr=90000, is_bpl=False, occupation="farmer", education_level="secondary",
        disability=False, marital_status="married", land_holding_acres=2.5,
        sectors_of_interest=["agriculture_rural", "financial_inclusion"], needs=["crop insurance", "pension"])},
    {"persona_id": "student_sc_female", "label": "Female SC student", "attributes": c.ProfileAttributes(
        age=19, gender="female", state="IN-MH", district="Pune", area_type="urban", social_category="sc",
        annual_family_income_inr=180000, is_bpl=False, occupation="student", education_level="undergraduate",
        disability=False, marital_status="single", sectors_of_interest=["education", "employment_skills"],
        needs=["scholarship", "hostel fees"])},
    {"persona_id": "senior_widow_bpl", "label": "Widowed senior citizen on BPL", "attributes": c.ProfileAttributes(
        age=67, gender="female", state="IN-BR", district="Gaya", area_type="rural", social_category="general",
        annual_family_income_inr=36000, is_bpl=True, occupation="homemaker", education_level="none",
        disability=False, marital_status="widowed", sectors_of_interest=["social_welfare", "health"],
        needs=["widow pension", "free medical treatment"])},
]
for p in personas:
    p["attributes"] = p["attributes"].model_dump()
farmer = c.ProfileAttributes(**personas[0]["attributes"])

# ── scheme detail (PMSBY, facts quoted verbatim from the real chunks) ──
s = seeds["pmsby"]
benefits = [quote(P1C1, "a, Table of Benefits = Death", "Rs. 2 Lakh."),
            quote(P1C1, "c, Table of Benefits", "Rs. 1 Lakh")]
docs = [quote(P2C0, "Enrolment form / Auto-debit authorization", "retained by the participating bank/ Post office.")]
steps = [quote(P1C0, "Enrolment Modality / Period:", "by 31st May of every year.")]
limitations = [quote(P1C1, "Termination of cover:", "1) On attaining age 70 years (age nearest birthday).")]
scheme = c.Scheme(
    scheme_id="pmsby", name=s["name"], sector=s["primary_sector"], department=s["department"], level=s["level"],
    states=[K.ALL_STATES], beneficiary_tags=split(s["beneficiary_tags"]), summary=quote(P1C0, "PMSBY is", "year to year."),
    benefits=benefits, max_benefit_inr=200000, documents_required=docs, application_steps=steps,
    official_url=s["official_url"] or None, application_url=None, doc_ids=[DOC], facts_status="incomplete",
    last_checked="2026-10-12", secondary_sectors=split(s["secondary_sectors"]), benefit_types=split(s["benefit_types"]),
    max_benefit_period="one_time",
    fact_citations={"summary": [P1C0], "benefits": [P1C1], "max_benefit_inr": [P1C1],
                    "documents_required": [P2C0], "application_steps": [P1C0], "limitations": [P1C1]},
    limitations=limitations)
eligibility = c.EligibilityResult(
    scheme_id="pmsby", status="NEEDS_VERIFICATION", missing_fields=[],
    reasons=[TAG + "Age requirement met; bank/Post office account holding cannot be checked from the profile."],
    checks=[c.RuleCheck(rule_id="pmsby-r1", result="pass", reason=TAG + "Age 45 is between 18 and 70.", citation_id=P1C1),
            c.RuleCheck(rule_id="pmsby-r2", result="ambiguous",
                        reason=TAG + "Needs a bank or Post office account; not asked in the profile.", citation_id=P1C1)])
summary = c.SchemeSummary(
    overview=[cs(P1C0, "PMSBY is", "year to year.")],
    relevance=[c.CitedSentence(text=f"Matches your profile: {eligibility.checks[0].reason}", citation_ids=[P1C1]),
               c.CitedSentence(text=f"Needs an official check: {eligibility.checks[1].reason}", citation_ids=[P1C1])],
    eligibility=[cs(P1C1, "Eligibility Conditions:", "will be enrolled into the scheme.")],
    benefits=[cs(P1C1, "a, Table of Benefits = Death", "Rs. 1 Lakh"), cs(P1C1, "Premium:", "per annum per member.")],
    documents=[cs(P2C0, "Enrolment form / Auto-debit authorization", "retained by the participating bank/ Post office.")],
    application=[cs(P1C0, "Enrolment Modality / Period:", "by 31st May of every year.")])
detail = c.SchemeDetail(scheme=scheme, eligibility=eligibility, summary=summary, evidence=list(EV.values()))

# ── library (real seed names; statuses/scores synthetic) ──
library = c.LibraryResult(profile_version=1, top=[
    card("pm-kisan", "PARTIALLY_ELIGIBLE", "Land ownership details needed.", 78),
    card("pm-kmy", "NEEDS_VERIFICATION", "Some exclusions need an official check.", 66),
    card("pmsby", "NEEDS_VERIFICATION", "Bank account holding needs a check.", 52),
    card("pmjjby", "NEEDS_VERIFICATION", "Eligibility criteria not extracted yet.", 41),
], more=[card("pmfby", "NEEDS_VERIFICATION", "Eligibility criteria not extracted yet.", None)]
)

# ── comparison: PMSBY (real cells) vs PMJJBY (no evidence -> value null) ──
def cell(v, ids):
    return c.ComparisonCell(value=v, citation_ids=ids)

cells = {
    "pmsby": {"target_group": cell(quote(P1C1, "Individual bank/", "70 years (age nearer birthday)"), [P1C1]),
              "eligibility_status": cell("NEEDS_VERIFICATION", [P1C1]),
              "benefits": cell("; ".join(benefits), [P1C1]),
              "max_benefit_inr": cell("200000", [P1C1]),
              "documents": cell(docs[0], [P2C0]),
              "application_process": cell(steps[0], [P1C0]),
              "limitations": cell(limitations[0], [P1C1])},
    "pmjjby": {f: cell(None, []) for f in K.COMPARISON_FIELDS},
}
cells["pmjjby"]["eligibility_status"] = cell("NEEDS_VERIFICATION", [])
comparison = c.ComparisonResponse(
    matrix=c.ComparisonMatrix(scheme_ids=["pmsby", "pmjjby"], fields=list(K.COMPARISON_FIELDS), cells=cells),
    insights=c.ComparisonInsights(insights=[cs(P1C0, "PMSBY is", "on account of an accident.")]),
    evidence=list(EV.values()))

profile = c.Profile(user_id="00000000-0000-4000-8000-000000000001", version=1, attributes=farmer, complete=True)
question = c.OnboardingNext(done=False, question=c.Question(
    question_id="q-sectors", field="sectors_of_interest", text=TAG + "Which areas do you want help with?",
    type="multi_choice", options=list(K.SECTOR_IDS), progress=0.5, option_labels=dict(K.SECTORS)))
e = EV[P1C1]   # same mapping as backend.app.knowledge.citations.to_target (checked in test_fixtures.py)
citation = c.CitationTarget(citation_id=e.citation_id, doc_id=e.doc_id, file_url=f"/api/documents/{e.doc_id}/file",
                            page=e.page, bbox=e.bbox, quote=e.text[:600], source_url=e.source_url,
                            doc_version=e.doc_version, precision="passage" if e.bbox else "page")


def write(name, model_or_obj, model_name):
    body = model_or_obj.model_dump(mode="json") if hasattr(model_or_obj, "model_dump") else model_or_obj
    out = {"_fixture": True, "_model": model_name, "_note": NOTE, **body}
    (FX / name).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    write("profile.json", profile, "Profile")
    write("question.json", question, "OnboardingNext")
    write("library.json", library, "LibraryResult")
    write("scheme_detail.json", detail, "SchemeDetail")
    write("comparison.json", comparison, "ComparisonResponse")
    write("citation.json", citation, "CitationTarget")
    (ROOT / "contracts/personas.json").write_text(json.dumps({
        "_fixture": True, "_note": "SYNTHETIC test people (section 6). Not real persons; no scheme facts here.",
        "personas": personas}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / "data/raw" / f"{DOC}.pdf", FX / "sample.pdf")
    print("fixtures written")


if __name__ == "__main__":
    main()
