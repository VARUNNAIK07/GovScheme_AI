import json
from pathlib import Path

from contracts.schemas import (
    Candidate,
    ComparisonInsights,
    ComparisonMatrix,
    EligibilityRule,
    Evidence,
    Profile,
    Scheme,
    SchemeSummary,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "contracts" / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fixture_profile() -> Profile:
    data = load_fixture("profile.json")
    return Profile(**{k: v for k, v in data.items() if not k.startswith("_")})


def fixture_scheme() -> Scheme:
    return Scheme(**load_fixture("scheme_detail.json")["scheme"])


def fixture_evidence() -> list[Evidence]:
    return [Evidence(**item) for item in load_fixture("scheme_detail.json")["evidence"]]


def sample_candidates() -> list[Candidate]:
    return [
        Candidate(
            scheme_id=fixture_scheme().scheme_id,
            retrieval_score=0.91,
            matched_sectors=["financial_inclusion"],
            need_similarity=0.72,
        )
    ]


def sample_rules() -> dict[str, list[EligibilityRule]]:
    return {
        "pmsby": [
            EligibilityRule(
                rule_id="pmsby-age",
                scheme_id="pmsby",
                field="age",
                operator="between",
                value=[18, 70],
                kind="required",
                source_text="Applicant age must be between 18 and 70 years.",
                citation_id="195a99298e85821b-p1-c1",
            ),
            EligibilityRule(
                rule_id="pmsby-bank",
                scheme_id="pmsby",
                field="_unmapped",
                operator="manual",
                value=True,
                kind="required",
                source_text="Applicant must hold a participating bank or Post office account.",
                citation_id="195a99298e85821b-p1-c1",
            ),
        ]
    }


def sample_schemes() -> dict[str, Scheme]:
    scheme = fixture_scheme()
    return {scheme.scheme_id: scheme}


def summarize_scheme(scheme: Scheme, eligibility, evidence, attrs) -> SchemeSummary:
    return SchemeSummary(**load_fixture("scheme_detail.json")["summary"])


def compare(*args, **kwargs) -> tuple[ComparisonMatrix, ComparisonInsights, list[Evidence]]:
    data = load_fixture("comparison.json")
    return (
        ComparisonMatrix(**data["matrix"]),
        ComparisonInsights(**data["insights"]),
        [Evidence(**item) for item in data["evidence"]],
    )

