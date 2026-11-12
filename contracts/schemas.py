"""GovScheme AI shared contracts (Pydantic v2).

Source: "3-Person 1-Day Build Plan", section 4. Frozen: after the freeze, changes are
append-only (new OPTIONAL fields with defaults). Every change is logged in CHANGELOG.md.
Mirror for the frontend: contracts/types.ts.

Conventions: JSON snake_case; money = integer INR; dates = ISO 'YYYY-MM-DD';
timestamps = ISO 8601 strings. ID formats and vocabularies live in contracts/constants.py.
Rule/score semantics (section 9) are written as code in contracts/semantics.py.
`backend/tests/test_contracts_ts_sync.py` fails if this file and types.ts drift apart.
"""
from typing import Any, Literal

from pydantic import BaseModel, Field

EligibilityStatus = Literal["ELIGIBLE", "PARTIALLY_ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_VERIFICATION"]


# ── Profile ──────────────────────────────────────────────────────────────────
class ProfileAttributes(BaseModel):
    # Defaults are None/[] so a partially answered profile is valid during onboarding.
    age: int | None = None
    gender: Literal["male", "female", "other"] | None = None
    state: str | None = None                        # constants.STATE_CODES, e.g. 'IN-UP'
    district: str | None = None
    area_type: Literal["rural", "urban"] | None = None
    social_category: Literal["general", "obc", "sc", "st", "ews"] | None = None
    annual_family_income_inr: int | None = None
    is_bpl: bool | None = None
    occupation: Literal["farmer", "student", "salaried", "self_employed", "unemployed",
                        "retired", "homemaker", "other"] | None = None
    education_level: str | None = None
    disability: bool | None = None
    disability_percent: int | None = None
    marital_status: Literal["single", "married", "widowed", "divorced"] | None = None
    land_holding_acres: float | None = None         # only asked if farmer
    sectors_of_interest: list[str] = []             # constants.SECTOR_IDS
    needs: list[str] = []                           # free-text tags, e.g. 'scholarship'


class Profile(BaseModel):
    user_id: str
    version: int
    attributes: ProfileAttributes
    complete: bool


# ── Knowledge records (PostgreSQL) ───────────────────────────────────────────
class Scheme(BaseModel):                            # tables: schemes (+ link tables, scheme_facts)
    scheme_id: str
    name: str
    sector: str                                     # PRIMARY sector, constants.SECTOR_IDS
    department: str
    level: Literal["central", "state"]
    states: list[str]                               # ['ALL'] for central
    beneficiary_tags: list[str]                     # constants.BENEFICIARY_TAGS
    summary: str | None
    benefits: list[str]
    max_benefit_inr: int | None
    documents_required: list[str]
    application_steps: list[str]
    official_url: str | None
    application_url: str | None
    doc_ids: list[str]
    facts_status: Literal["verified", "extracted", "incomplete"]
    last_checked: str
    # v1.1 (A, optional): taxonomy + benefit period
    secondary_sectors: list[str] = []               # max 3, never the primary sector
    benefit_types: list[str] = []                   # constants.BENEFIT_TYPES
    max_benefit_period: Literal["one_time", "per_year", "per_month"] | None = None
    # v1.2 (A, optional): provenance per fact field + limitations
    # fact_citations[field] = citation_ids (real chunk_ids from scheme_facts) backing that field;
    # keys are constants.FACT_KIND_BY_FIELD keys. A field with no key here has no stored evidence.
    fact_citations: dict[str, list[str]] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)   # scheme_facts kind 'limitation'


class EligibilityRule(BaseModel):                   # table: eligibility_rules
    rule_id: str
    scheme_id: str
    field: str                                      # ProfileAttributes field, or constants.UNMAPPED_FIELD
    operator: Literal["eq", "in", "not_in", "lte", "gte", "between", "is_true", "is_false", "manual"]
    value: Any                                      # e.g. 18, ['sc','st'], [18, 40]
    kind: Literal["required", "exclusion"]
    source_text: str                                # original wording from the PDF
    citation_id: str | None                         # the chunk it came from


class DocumentMeta(BaseModel):                      # view: document_meta_v
    doc_id: str
    scheme_id: str | None
    title: str
    source_url: str
    local_path: str
    sha256: str
    pages: int                                      # counted at download time
    version: int
    fetched_at: str
    last_checked: str
    ingestion_status: Literal["downloaded", "parsed", "indexed", "failed"]
    # v1.1 (A, optional): provenance + quality
    language: str = "en"
    text_layer: Literal["digital", "scanned", "mixed"] | None = None
    fetch_method: Literal["auto", "manual"] = "auto"
    error: str | None = None
    # v1.2 (A, optional): False = replaced by a newer version of the same source. Its chunks stay
    # resolvable for old citations but are excluded from retrieval. A replacement becomes current
    # only after it is indexed (see ingestion.common.current_versions).
    is_current: bool = True


class Evidence(BaseModel):                          # Qdrant payload (+ vector); table: chunks
    citation_id: str                                # == chunk_id
    chunk_id: str                                   # '{doc_id}-p{page}-c{n}', page = start page
    doc_id: str
    scheme_id: str
    section: str | None
    page: int                                       # 1-based
    text: str
    bbox: list[float] | None                        # [x0,y0,x1,y1] PDF points, origin BOTTOM-LEFT
    source_url: str
    doc_version: int
    score: float | None = None


class CitedSentence(BaseModel):
    text: str
    citation_ids: list[str]                         # must be non-empty after citations.validate


# ── Agent result shapes ──────────────────────────────────────────────────────
class Question(BaseModel):
    question_id: str
    field: str
    text: str
    type: Literal["number", "single_choice", "multi_choice", "boolean", "text"]
    options: list[str] = []                         # stable machine codes (what the answer stores)
    progress: float                                 # 0..1
    # v1.2 (B, optional): display text per option code; UI falls back to the code if a label is missing
    option_labels: dict[str, str] = Field(default_factory=dict)


class Candidate(BaseModel):
    scheme_id: str
    retrieval_score: float
    matched_sectors: list[str]
    # v1.2 (A, optional): cosine(BGE(needs), BGE(scheme summary)) clipped to 0..1, computed by
    # Retrieval with the shared embedder. None = needs empty or no summary. Scoring uses it as N.
    need_similarity: float | None = None


class RuleCheck(BaseModel):
    # result is from the USER's point of view (semantics.RULE_RESULT_MEANING):
    #   pass = rule satisfied (required condition met / exclusion does NOT apply)
    #   fail = required condition not met, or an exclusion condition DOES apply
    #   unknown = a profile field the rule needs is missing (never 'fail')
    #   ambiguous = operator 'manual' or unclear wording -> needs an official check
    rule_id: str
    result: Literal["pass", "fail", "unknown", "ambiguous"]
    reason: str
    citation_id: str | None


class EligibilityResult(BaseModel):
    scheme_id: str
    status: EligibilityStatus
    checks: list[RuleCheck]
    reasons: list[str]
    missing_fields: list[str]


class ScoreResult(BaseModel):
    scheme_id: str
    match_percent: int
    components: dict[str, float]                    # constants.SCORE_COMPONENTS, each 0..1
    formula_version: str = "v1"


class LibraryCard(BaseModel):
    scheme_id: str
    name: str
    department: str
    sector: str
    eligibility_status: EligibilityStatus
    eligibility_reason: str
    match_percent: int | None                       # None in the 'more' section


class LibraryResult(BaseModel):
    profile_version: int
    top: list[LibraryCard]
    more: list[LibraryCard]


class ComparisonCell(BaseModel):
    value: str | None                               # None = 'Not stated in source'
    citation_ids: list[str]


class ComparisonMatrix(BaseModel):
    scheme_ids: list[str]
    fields: list[str]                               # constants.COMPARISON_FIELDS
    cells: dict[str, dict[str, ComparisonCell]]     # cells[scheme_id][field]


class SchemeSummary(BaseModel):
    overview: list[CitedSentence]
    relevance: list[CitedSentence]
    eligibility: list[CitedSentence]
    benefits: list[CitedSentence]
    documents: list[CitedSentence]
    application: list[CitedSentence]


class ComparisonInsights(BaseModel):
    insights: list[CitedSentence]


class CitationTarget(BaseModel):
    citation_id: str
    doc_id: str
    file_url: str
    page: int
    bbox: list[float] | None
    quote: str
    source_url: str
    doc_version: int
    precision: Literal["passage", "page", "document"]


class RefreshResult(BaseModel):
    # v1.2: W6 result and the body of POST /api/admin/refresh.
    # A's ingestion/refresh.py fills changed_docs + affected_schemes; B's controller adds invalidated_runs.
    changed_docs: list[str] = Field(default_factory=list)       # new doc_ids (new versions) indexed
    affected_schemes: list[str] = Field(default_factory=list)   # scheme_ids whose evidence changed
    invalidated_runs: list[str] = Field(default_factory=list)   # workflow_runs.run_id values


# ── Shared workflow state (owned by B's controller) ──────────────────────────
class TraceStep(BaseModel):
    # Referenced by WorkflowState in the build plan but never defined there (proposed by A; B to confirm).
    agent: str
    status: Literal["ok", "skipped", "error"]
    started_at: str
    duration_ms: int
    message: str | None = None


class WorkflowState(BaseModel):
    run_id: str
    workflow: Literal["W1", "W2", "W3", "W4", "W5", "W6"]
    user_id: str | None
    profile: Profile | None = None
    profile_version: int | None = None
    next_question: Question | None = None
    scheme_ids: list[str] = []                      # input for W3 / W4
    candidates: list[Candidate] = []                # Retrieval
    evidence: dict[str, list[Evidence]] = {}        # Retrieval, keyed by scheme_id
    eligibility: dict[str, EligibilityResult] = {}  # Eligibility
    scores: dict[str, ScoreResult] = {}             # Scoring
    library: LibraryResult | None = None            # Scoring
    comparison: ComparisonMatrix | None = None      # Comparison
    summary: SchemeSummary | ComparisonInsights | None = None  # Summary
    skipped: list[str] = []
    errors: list[str] = []
    trace: list[TraceStep] = []
    # v1.2 (controller-written, read-only for agents): DB records for the schemes this run needs,
    # keyed by scheme_id, loaded BEFORE agents run so no agent queries the DB for them.
    schemes: dict[str, Scheme] = Field(default_factory=dict)              # Scoring, Comparison, Summary, library cards
    rules: dict[str, list[EligibilityRule]] = Field(default_factory=dict)  # Eligibility; [] = no rules extracted
    refresh: RefreshResult | None = None                                   # W6 only


# ── API request / response bodies (section 5) ────────────────────────────────
# Responses that are already a model above are not repeated: GET /api/profile -> Profile,
# GET /api/library -> LibraryResult, GET /api/comparison/options -> list[LibraryCard],
# GET /api/citations/{id} -> CitationTarget, POST /api/admin/refresh -> RefreshResult,
# GET /api/documents/{doc_id}/file -> PDF bytes (no JSON).
class ErrorBody(BaseModel):
    code: str                                       # stable machine code, e.g. 'not_found', 'validation_error'
    message: str                                    # human-readable, never contains secrets or stack traces


class ErrorResponse(BaseModel):                     # every non-2xx response
    error: ErrorBody


class PublicUser(BaseModel):                        # users row minus password_hash / is_active / timestamps
    user_id: str                                    # UUID as string
    email: str
    name: str


class RegisterRequest(BaseModel):                   # POST /api/auth/register
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):                      # POST /api/auth/login
    email: str
    password: str


class AuthResponse(BaseModel):                      # register + login
    token: str                                      # JWT, sent back as 'Authorization: Bearer <token>'
    user: PublicUser


class Me(BaseModel):                                # GET /api/me
    user: PublicUser
    profile_complete: bool
    profile_version: int


class OnboardingNext(BaseModel):                    # GET /api/onboarding/next  (W1)
    done: bool
    question: Question | None


class AnswerRequest(BaseModel):                     # POST /api/onboarding/answer  (W1)
    field: str                                      # a ProfileAttributes field name (== Question.field)
    value: Any                                      # an option code for choice questions, never a label


class AnswerResponse(BaseModel):
    ok: bool
    errors: list[str]                               # from validate_answer; non-empty => ok is False
    done: bool
    question: Question | None                       # same question again if not ok, else the next one


class ProfileUpdateRequest(BaseModel):              # PUT /api/profile  (W5)
    # Partial update: only the keys the client sends change (B reads it with model_dump(exclude_unset=True)).
    attributes: ProfileAttributes


class ProfileUpdateResponse(BaseModel):             # PUT /api/profile -> then W2
    profile: Profile
    library: LibraryResult


class SchemeDetail(BaseModel):                      # GET /api/schemes/{scheme_id}  (W3)
    scheme: Scheme
    eligibility: EligibilityResult
    summary: SchemeSummary
    evidence: list[Evidence]                        # every citation_id used in summary is in here


class ComparisonRequest(BaseModel):                 # POST /api/comparison  (W4)
    scheme_ids: list[str] = Field(min_length=2, max_length=5)   # must be in the user's library top 5


class ComparisonResponse(BaseModel):
    matrix: ComparisonMatrix
    insights: ComparisonInsights
    evidence: list[Evidence]


class RefreshRequest(BaseModel):                    # POST /api/admin/refresh  (W6)
    doc_id: str | None = None                       # None = re-check every source


class HealthResponse(BaseModel):                    # GET /api/health
    postgres: Literal["ok", "down"]
    qdrant: Literal["ok", "down"]
    llm: Literal["ok", "down"]
