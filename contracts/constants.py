"""Frozen constants shared by all three modules. Vocabularies here are seeded into the
reference tables (sectors, tags, states) by the initial migration — change both together."""

# ── Embeddings / vector store ────────────────────────────────────────────────
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384
VECTOR_DISTANCE = "cosine"
QDRANT_COLLECTION = "scheme_chunks"
# BGE v1.5 recommends this prefix for short retrieval queries (not for documents).
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

# ── IDs ──────────────────────────────────────────────────────────────────────
SCHEME_ID_RE = r"^[a-z0-9]+(-[a-z0-9]+)*$"          # 'pm-kisan'
DOC_ID_RE = r"^[0-9a-f]{16}$"                       # first 16 hex of the PDF's SHA-256
CHUNK_ID_RE = r"^[0-9a-f]{16}-p[0-9]+-c[0-9]+$"     # '{doc_id}-p{page}-c{n}'; citation_id == chunk_id
BBOX_ORIGIN = "bottom-left"                         # Evidence.bbox = [x0,y0,x1,y1] in PDF points

# ── Eligibility / scoring ────────────────────────────────────────────────────
ELIGIBILITY_STATUSES = ("ELIGIBLE", "PARTIALLY_ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_VERIFICATION")
UNMAPPED_FIELD = "_unmapped"                        # rule condition with no ProfileAttributes field -> operator 'manual'
SCORE_COMPONENTS = ("profile", "eligibility", "need", "benefit")
# Section 9, formula v1 (FROZEN): match = round(100 * (0.35P + 0.30E + 0.20N + 0.15B))
SCORE_WEIGHTS = {"profile": 0.35, "eligibility": 0.30, "need": 0.20, "benefit": 0.15}
ELIGIBILITY_FIT = {"ELIGIBLE": 1.0, "PARTIALLY_ELIGIBLE": 0.6, "NEEDS_VERIFICATION": 0.5, "NOT_ELIGIBLE": 0.0}
SCORE_UI_LABEL = "relevance match"                  # never "chance of approval"
LIBRARY_TOP_N = 5
LIBRARY_MORE_N = 5

# Scheme field -> scheme_facts.kind holding its source wording + citation_id (Scheme.fact_citations keys).
# 'max_benefit' and 'limitation' need migration 0002 (B) before they can be stored.
FACT_KIND_BY_FIELD = {
    "summary": "summary",
    "benefits": "benefit",
    "documents_required": "document_required",
    "application_steps": "application_step",
    "max_benefit_inr": "max_benefit",
    "limitations": "limitation",
}
COMPARISON_FIELDS = ("target_group", "eligibility_status", "benefits", "max_benefit_inr",
                     "documents", "application_process", "limitations")

# ── Sector taxonomy (approved 2026-10-12) ────────────────────────────────────
SECTORS: dict[str, str] = {
    "agriculture_rural": "Agriculture, Farming & Rural Development",
    "education": "Education & Scholarships",
    "employment_skills": "Employment, Skills & Livelihoods",
    "business_msme": "Business, Entrepreneurship & MSMEs",
    "health": "Healthcare & Medical Assistance",
    "housing_utilities": "Housing, Sanitation & Basic Needs",
    "women_child": "Women, Children & Family Welfare",
    "social_welfare": "Social Welfare & Inclusion",
    "financial_inclusion": "Financial Inclusion, Insurance & Savings",
    "energy_environment": "Energy & Environment",
}
SECTOR_IDS = tuple(SECTORS)
MAX_SECONDARY_SECTORS = 3

# ── Beneficiary tags: value = how B derives it from ProfileAttributes (None = not derivable yet) ──
BENEFICIARY_TAGS: dict[str, str | None] = {
    "farmer": "occupation == 'farmer'",
    "student": "occupation == 'student'",
    "unemployed": "occupation == 'unemployed'",
    "woman": "gender == 'female'",
    "sc": "social_category == 'sc'",
    "st": "social_category == 'st'",
    "obc": "social_category == 'obc'",
    "ews": "social_category == 'ews'",
    "senior": "age >= 60",
    "youth": "18 <= age <= 35",
    "child": "age < 18",
    "widow": "marital_status == 'widowed'",
    "disabled": "disability is True",
    "rural": "area_type == 'rural'",
    "urban": "area_type == 'urban'",
    "bpl": "is_bpl is True",
    "girl_child": None, "pregnant_woman": None, "transgender": None, "dnt": None,
    "artisan": None, "street_vendor": None, "fisher": None, "entrepreneur": None,
    "unorganised_worker": None, "sanitation_worker": None, "homeowner": None,
    "shg": None, "fpo": None, "lig": None, "mig": None,
}

BENEFIT_TYPES = ("cash_transfer", "scholarship", "stipend", "loan", "interest_subsidy",
                 "credit_guarantee", "capital_subsidy", "grant", "insurance", "health_cover",
                 "pension", "savings", "bank_account", "housing", "in_kind", "training",
                 "employment", "service")

# ── States / UTs: ISO 3166-2:IN codes; 'ALL' = whole country (central schemes) ──
ALL_STATES = "ALL"
STATES: dict[str, str] = {
    "IN-AN": "Andaman and Nicobar Islands", "IN-AP": "Andhra Pradesh", "IN-AR": "Arunachal Pradesh",
    "IN-AS": "Assam", "IN-BR": "Bihar", "IN-CH": "Chandigarh", "IN-CG": "Chhattisgarh",
    "IN-DH": "Dadra and Nagar Haveli and Daman and Diu", "IN-DL": "Delhi", "IN-GA": "Goa",
    "IN-GJ": "Gujarat", "IN-HR": "Haryana", "IN-HP": "Himachal Pradesh", "IN-JK": "Jammu and Kashmir",
    "IN-JH": "Jharkhand", "IN-KA": "Karnataka", "IN-KL": "Kerala", "IN-LA": "Ladakh",
    "IN-LD": "Lakshadweep", "IN-MP": "Madhya Pradesh", "IN-MH": "Maharashtra", "IN-MN": "Manipur",
    "IN-ML": "Meghalaya", "IN-MZ": "Mizoram", "IN-NL": "Nagaland", "IN-OD": "Odisha",
    "IN-PY": "Puducherry", "IN-PB": "Punjab", "IN-RJ": "Rajasthan", "IN-SK": "Sikkim",
    "IN-TN": "Tamil Nadu", "IN-TS": "Telangana", "IN-TR": "Tripura", "IN-UP": "Uttar Pradesh",
    "IN-UK": "Uttarakhand", "IN-WB": "West Bengal",
}
