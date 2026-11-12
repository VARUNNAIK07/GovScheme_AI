// frontend/src/types/contracts.ts
// Frozen contracts mirrored directly from contracts/types.ts

export type Gender = 'male' | 'female' | 'other';
export type AreaType = 'rural' | 'urban';
export type SocialCategory = 'general' | 'obc' | 'sc' | 'st' | 'ews';
export type Occupation =
  | 'farmer'
  | 'student'
  | 'salaried'
  | 'self_employed'
  | 'unemployed'
  | 'retired'
  | 'homemaker'
  | 'other';
export type MaritalStatus = 'single' | 'married' | 'widowed' | 'divorced';

export interface ProfileAttributes {
  age: number | null;
  gender: Gender | null;
  state: string | null;
  district: string | null;
  area_type: AreaType | null;
  social_category: SocialCategory | null;
  annual_family_income_inr: number | null;
  is_bpl: boolean | null;
  occupation: Occupation | null;
  education_level: string | null;
  disability: boolean | null;
  disability_percent: number | null;
  marital_status: MaritalStatus | null;
  land_holding_acres: number | null;
  sectors_of_interest: string[];
  needs: string[];
}

export interface Profile {
  user_id: string;
  version: number;
  attributes: ProfileAttributes;
  complete: boolean;
}

export type SchemeLevel = 'central' | 'state';
export type FactsStatus = 'verified' | 'extracted' | 'incomplete';

export interface Scheme {
  scheme_id: string;
  name: string;
  sector: string;
  department: string;
  level: SchemeLevel;
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
  facts_status: FactsStatus;
  last_checked: string;
  secondary_sectors: string[];
  benefit_types: string[];
  max_benefit_period: 'one_time' | 'per_year' | 'per_month' | null;
  fact_citations?: Record<string, string[]>;
  limitations?: string[];
}

export type RuleOperator =
  | 'eq'
  | 'in'
  | 'not_in'
  | 'lte'
  | 'gte'
  | 'between'
  | 'is_true'
  | 'is_false'
  | 'manual';

export type RuleKind = 'required' | 'exclusion';

export interface EligibilityRule {
  rule_id: string;
  scheme_id: string;
  field: string;
  operator: RuleOperator;
  value: any;
  kind: RuleKind;
  source_text: string;
  citation_id: string | null;
}

export type IngestionStatus = 'downloaded' | 'parsed' | 'indexed' | 'failed';

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
  ingestion_status: IngestionStatus;
}

export interface Evidence {
  citation_id: string;
  chunk_id: string;
  doc_id: string;
  scheme_id: string;
  section: string | null;
  page: number;
  text: string;
  bbox: [number, number, number, number] | null;
  source_url: string;
  doc_version: number;
  score: number | null;
}

export interface CitedSentence {
  text: string;
  citation_ids: string[];
}

export type QuestionType =
  | 'number'
  | 'single_choice'
  | 'multi_choice'
  | 'boolean'
  | 'text';

export interface Question {
  question_id: string;
  field: string;
  text: string;
  type: QuestionType;
  options: string[]; // machine codes; send these back as the answer value
  progress: number;
  option_labels?: Record<string, string>; // code -> display text
}

export interface Candidate {
  scheme_id: string;
  retrieval_score: number;
  matched_sectors: string[];
  need_similarity?: number | null;
}

export type RuleCheckResult = 'pass' | 'fail' | 'unknown' | 'ambiguous';

export interface RuleCheck {
  rule_id: string;
  result: RuleCheckResult;
  reason: string;
  citation_id: string | null;
}

export type EligibilityStatus =
  | 'ELIGIBLE'
  | 'PARTIALLY_ELIGIBLE'
  | 'NOT_ELIGIBLE'
  | 'NEEDS_VERIFICATION';

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
  components: Record<string, number>;
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
  value: string | null;
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

export type CitationPrecision = 'passage' | 'page' | 'document';

export interface CitationTarget {
  citation_id: string;
  doc_id: string;
  file_url: string;
  page: number;
  bbox: [number, number, number, number] | null;
  quote: string;
  source_url: string;
  doc_version: number;
  precision: CitationPrecision;
}

export interface User {
  user_id: string;
  email: string;
  name: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface MeResponse {
  user: User;
  profile_complete: boolean;
  profile_version: number;
}

export interface OnboardingNextResponse {
  done: boolean;
  question: Question | null;
}

export interface OnboardingAnswerRequest {
  field: string;
  value: any;
}

export interface OnboardingAnswerResponse {
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

export interface SchemeDetailResponse {
  scheme: Scheme;
  eligibility: EligibilityResult;
  summary: SchemeSummary;
  evidence: Evidence[];
}

export interface ComparisonRequest {
  scheme_ids: string[];
}

export interface ComparisonResponse {
  matrix: ComparisonMatrix;
  insights: ComparisonInsights;
  evidence: Evidence[];
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
  };
}

export interface HealthResponse {
  postgres: 'ok' | 'down';
  qdrant: 'ok' | 'down';
  llm: 'ok' | 'down';
}

// Sector ids (contracts/constants.py SECTORS) -> display names
export const SECTOR_LABELS: Record<string, string> = {
  agriculture_rural: 'Agriculture, Farming & Rural Development',
  education: 'Education & Scholarships',
  employment_skills: 'Employment, Skills & Livelihoods',
  business_msme: 'Business, Entrepreneurship & MSMEs',
  health: 'Healthcare & Medical Assistance',
  housing_utilities: 'Housing, Sanitation & Basic Needs',
  women_child: 'Women, Children & Family Welfare',
  social_welfare: 'Social Welfare & Inclusion',
  financial_inclusion: 'Financial Inclusion, Insurance & Savings',
  energy_environment: 'Energy & Environment',
};

export const sectorLabel = (id: string): string => SECTOR_LABELS[id] ?? id.replace(/_/g, ' ');

export const SCORE_UI_LABEL = 'relevance match'; // never "chance of approval"
