// GovScheme AI shared contracts — mirror of contracts/schemas.py. Keep both in sync;
// log every change in contracts/CHANGELOG.md. backend/tests/test_contracts_ts_sync.py fails on drift.
//
// Optionality rules:
//   * `x: T | null`  -> the key is always present; its value may be null.
//   * `x?: T`        -> added in v1.2 with a backend default; an older backend may omit the key.
//                       Read it with a fallback, e.g. `scheme.limitations ?? []`.
//   * v1.0/v1.1 fields with defaults are always sent, so they stay required.

export type EligibilityStatus =
  | "ELIGIBLE"
  | "PARTIALLY_ELIGIBLE"
  | "NOT_ELIGIBLE"
  | "NEEDS_VERIFICATION";

export interface ProfileAttributes {
  age: number | null;
  gender: "male" | "female" | "other" | null;
  state: string | null; // ISO 3166-2:IN code, e.g. 'IN-UP'
  district: string | null;
  area_type: "rural" | "urban" | null;
  social_category: "general" | "obc" | "sc" | "st" | "ews" | null;
  annual_family_income_inr: number | null;
  is_bpl: boolean | null;
  occupation:
    | "farmer" | "student" | "salaried" | "self_employed"
    | "unemployed" | "retired" | "homemaker" | "other" | null;
  education_level: string | null;
  disability: boolean | null;
  disability_percent: number | null;
  marital_status: "single" | "married" | "widowed" | "divorced" | null;
  land_holding_acres: number | null;
  sectors_of_interest: string[]; // sector ids from constants.py
  needs: string[];
}

export interface Profile {
  user_id: string;
  version: number;
  attributes: ProfileAttributes;
  complete: boolean;
}

export interface Scheme {
  scheme_id: string;
  name: string;
  sector: string; // primary sector id
  department: string;
  level: "central" | "state";
  states: string[];
  beneficiary_tags: string[];
  summary: string | null;
  benefits: string[];
  max_benefit_inr: number | null;
  documents_required: string[];
  application_steps: string[];
  official_url: string | null;
  application_url: string | null;
  doc_ids: string[];
  facts_status: "verified" | "extracted" | "incomplete";
  last_checked: string;
  secondary_sectors: string[];
  benefit_types: string[];
  max_benefit_period: "one_time" | "per_year" | "per_month" | null;
  fact_citations?: Record<string, string[]>; // field name -> citation_ids backing it (v1.2)
  limitations?: string[]; // v1.2
}

export interface EligibilityRule {
  rule_id: string;
  scheme_id: string;
  field: string;
  operator: "eq" | "in" | "not_in" | "lte" | "gte" | "between" | "is_true" | "is_false" | "manual";
  value: unknown;
  kind: "required" | "exclusion";
  source_text: string;
  citation_id: string | null;
}

export interface DocumentMeta {
  doc_id: string;
  scheme_id: string | null;
  title: string;
  source_url: string;
  local_path: string;
  sha256: string;
  pages: number;
  version: number;
  fetched_at: string;
  last_checked: string;
  ingestion_status: "downloaded" | "parsed" | "indexed" | "failed";
  language: string;
  text_layer: "digital" | "scanned" | "mixed" | null;
  fetch_method: "auto" | "manual";
  error: string | null;
  is_current?: boolean; // false = replaced by a newer version; still citable, not retrieved (v1.2)
}

export interface Evidence {
  citation_id: string;
  chunk_id: string;
  doc_id: string;
  scheme_id: string;
  section: string | null;
  page: number; // 1-based
  text: string;
  bbox: [number, number, number, number] | null; // PDF points, origin bottom-left
  source_url: string;
  doc_version: number;
  score: number | null;
}

export interface CitedSentence {
  text: string;
  citation_ids: string[];
}

export interface Question {
  question_id: string;
  field: string;
  text: string;
  type: "number" | "single_choice" | "multi_choice" | "boolean" | "text";
  options: string[]; // machine codes; send these back as the answer value
  progress: number; // 0..1
  option_labels?: Record<string, string>; // code -> display text; fall back to the code (v1.2)
}

export interface Candidate {
  scheme_id: string;
  retrieval_score: number;
  matched_sectors: string[];
  need_similarity?: number | null; // 0..1, computed by Retrieval (v1.2)
}

// result is from the user's point of view: for an exclusion rule, "fail" = the exclusion applies.
export interface RuleCheck {
  rule_id: string;
  result: "pass" | "fail" | "unknown" | "ambiguous";
  reason: string;
  citation_id: string | null;
}

export interface EligibilityResult {
  scheme_id: string;
  status: EligibilityStatus;
  checks: RuleCheck[];
  reasons: string[];
  missing_fields: string[];
}

export interface ScoreResult {
  scheme_id: string;
  match_percent: number;
  components: Record<string, number>; // profile, eligibility, need, benefit
  formula_version: string;
}

export interface LibraryCard {
  scheme_id: string;
  name: string;
  department: string;
  sector: string;
  eligibility_status: EligibilityStatus;
  eligibility_reason: string;
  match_percent: number | null;
}

export interface LibraryResult {
  profile_version: number;
  top: LibraryCard[];
  more: LibraryCard[];
}

export interface ComparisonCell {
  value: string | null; // null = 'Not stated in source'
  citation_ids: string[];
}

export interface ComparisonMatrix {
  scheme_ids: string[];
  fields: string[];
  cells: Record<string, Record<string, ComparisonCell>>;
}

export interface SchemeSummary {
  overview: CitedSentence[];
  relevance: CitedSentence[];
  eligibility: CitedSentence[];
  benefits: CitedSentence[];
  documents: CitedSentence[];
  application: CitedSentence[];
}

export interface ComparisonInsights {
  insights: CitedSentence[];
}

export interface CitationTarget {
  citation_id: string;
  doc_id: string;
  file_url: string;
  page: number;
  bbox: [number, number, number, number] | null;
  quote: string;
  source_url: string;
  doc_version: number;
  precision: "passage" | "page" | "document";
}

// W6 result; also the body of POST /api/admin/refresh (v1.2)
export interface RefreshResult {
  changed_docs: string[];
  affected_schemes: string[];
  invalidated_runs: string[];
}

// ── API request / response bodies (section 5, v1.2) ──
// Already-defined responses: GET /api/profile -> Profile, GET /api/library -> LibraryResult,
// GET /api/citations/{id} -> CitationTarget, POST /api/admin/refresh -> RefreshResult.
export type ComparisonOptions = LibraryCard[]; // GET /api/comparison/options

export interface ErrorBody {
  code: string;
  message: string;
}

export interface ErrorResponse {
  error: ErrorBody; // every non-2xx response
}

export interface PublicUser {
  user_id: string;
  email: string;
  name: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  token: string;
  user: PublicUser;
}

export interface Me {
  user: PublicUser;
  profile_complete: boolean;
  profile_version: number;
}

export interface OnboardingNext {
  done: boolean;
  question: Question | null;
}

export interface AnswerRequest {
  field: string;
  value: unknown; // an option code for choice questions, never a label
}

export interface AnswerResponse {
  ok: boolean;
  errors: string[];
  done: boolean;
  question: Question | null;
}

export interface ProfileUpdateRequest {
  attributes: Partial<ProfileAttributes>; // only the keys sent are changed
}

export interface ProfileUpdateResponse {
  profile: Profile;
  library: LibraryResult;
}

export interface SchemeDetail {
  scheme: Scheme;
  eligibility: EligibilityResult;
  summary: SchemeSummary;
  evidence: Evidence[];
}

export interface ComparisonRequest {
  scheme_ids: string[]; // 2 to 5 ids from /api/comparison/options
}

export interface ComparisonResponse {
  matrix: ComparisonMatrix;
  insights: ComparisonInsights;
  evidence: Evidence[];
}

export interface RefreshRequest {
  doc_id?: string | null;
}

export interface HealthResponse {
  postgres: "ok" | "down";
  qdrant: "ok" | "down";
  llm: "ok" | "down";
}

export const SCORE_UI_LABEL = "relevance match"; // never "chance of approval"
