# contracts/schemas.py
from typing import Any, Literal
from pydantic import BaseModel, Field

class ProfileAttributes(BaseModel):
    age: int | None = None
    gender: Literal['male', 'female', 'other'] | None = None
    state: str | None = None
    district: str | None = None
    area_type: Literal['rural', 'urban'] | None = None
    social_category: Literal['general', 'obc', 'sc', 'st', 'ews'] | None = None
    annual_family_income_inr: int | None = None
    is_bpl: bool | None = None
    occupation: Literal[
        'farmer', 'student', 'salaried', 'self_employed',
        'unemployed', 'retired', 'homemaker', 'other'
    ] | None = None
    education_level: str | None = None
    disability: bool | None = None
    disability_percent: int | None = None
    marital_status: Literal['single', 'married', 'widowed', 'divorced'] | None = None
    land_holding_acres: float | None = None  # only asked if farmer
    sectors_of_interest: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)

class Profile(BaseModel):
    user_id: str
    version: int
    attributes: ProfileAttributes
    complete: bool

class Scheme(BaseModel):
    scheme_id: str
    name: str
    sector: str
    department: str
    level: Literal['central', 'state']
    states: list[str]
    beneficiary_tags: list[str]
    summary: str | None = None
    benefits: list[str] = Field(default_factory=list)
    max_benefit_inr: int | None = None
    documents_required: list[str] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)
    official_url: str | None = None
    application_url: str | None = None
    doc_ids: list[str] = Field(default_factory=list)
    facts_status: Literal['verified', 'extracted', 'incomplete']
    last_checked: str

class EligibilityRule(BaseModel):
    rule_id: str
    scheme_id: str
    field: str
    operator: Literal['eq', 'in', 'not_in', 'lte', 'gte', 'between', 'is_true', 'is_false', 'manual']
    value: Any
    kind: Literal['required', 'exclusion']
    source_text: str
    citation_id: str | None = None

class DocumentMeta(BaseModel):
    doc_id: str
    scheme_id: str | None = None
    title: str
    source_url: str
    local_path: str
    sha256: str
    pages: int
    version: int
    fetched_at: str
    last_checked: str
    ingestion_status: Literal['downloaded', 'parsed', 'indexed', 'failed']

class Evidence(BaseModel):
    citation_id: str
    chunk_id: str
    doc_id: str
    scheme_id: str
    section: str | None = None
    page: int
    text: str
    bbox: list[float] | None = None  # [x0, y0, x1, y1] in PDF points
    source_url: str
    doc_version: int
    score: float | None = None

class CitedSentence(BaseModel):
    text: str
    citation_ids: list[str]

class Question(BaseModel):
    question_id: str
    field: str
    text: str
    type: Literal['number', 'single_choice', 'multi_choice', 'boolean', 'text']
    options: list[str] = Field(default_factory=list)
    progress: float  # 0..1

class Candidate(BaseModel):
    scheme_id: str
    retrieval_score: float
    matched_sectors: list[str]

class RuleCheck(BaseModel):
    rule_id: str
    result: Literal['pass', 'fail', 'unknown', 'ambiguous']
    reason: str
    citation_id: str | None = None

class EligibilityResult(BaseModel):
    scheme_id: str
    status: Literal['ELIGIBLE', 'PARTIALLY_ELIGIBLE', 'NOT_ELIGIBLE', 'NEEDS_VERIFICATION']
    checks: list[RuleCheck] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)

class ScoreResult(BaseModel):
    scheme_id: str
    match_percent: int
    components: dict[str, float]
    formula_version: str = 'v1'

class LibraryCard(BaseModel):
    scheme_id: str
    name: str
    department: str
    sector: str
    eligibility_status: Literal['ELIGIBLE', 'PARTIALLY_ELIGIBLE', 'NOT_ELIGIBLE', 'NEEDS_VERIFICATION']
    eligibility_reason: str
    match_percent: int | None = None

class LibraryResult(BaseModel):
    profile_version: int
    top: list[LibraryCard] = Field(default_factory=list)
    more: list[LibraryCard] = Field(default_factory=list)

class ComparisonCell(BaseModel):
    value: str | None = None
    citation_ids: list[str] = Field(default_factory=list)

class ComparisonMatrix(BaseModel):
    scheme_ids: list[str]
    fields: list[str]
    cells: dict[str, dict[str, ComparisonCell]]

class SchemeSummary(BaseModel):
    overview: list[CitedSentence] = Field(default_factory=list)
    relevance: list[CitedSentence] = Field(default_factory=list)
    eligibility: list[CitedSentence] = Field(default_factory=list)
    benefits: list[CitedSentence] = Field(default_factory=list)
    documents: list[CitedSentence] = Field(default_factory=list)
    application: list[CitedSentence] = Field(default_factory=list)

class ComparisonInsights(BaseModel):
    insights: list[CitedSentence] = Field(default_factory=list)

class CitationTarget(BaseModel):
    citation_id: str
    doc_id: str
    file_url: str
    page: int
    bbox: list[float] | None = None
    quote: str
    source_url: str
    doc_version: int
    precision: Literal['passage', 'page', 'document']
