"""Initial schema: all 18 tables (A + B), contract view, reference data, row-level security.

Revision ID: 0001
Revises:
Create Date: 2026-10-12

Tables are written out explicitly (not derived from models at run time) so this migration
never changes after it has been applied. `alembic check` verifies models.py still matches.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from contracts import constants

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TZ = sa.DateTime(timezone=True)
NOW = sa.text("now()")
REVIEW = "review_status IN ('unreviewed', 'verified', 'flagged', 'rejected')"

TABLES_IN_ORDER = [
    "sectors", "tags", "states", "schemes", "scheme_secondary_sectors", "scheme_tags", "scheme_states",
    "sources", "documents", "chunks", "ingestion_events", "extraction_runs", "scheme_facts",
    "eligibility_rules", "users", "profiles", "workflow_runs", "comparison_sessions",
]


def upgrade() -> None:
    # ── reference data ──
    op.create_table("sectors",
        sa.Column("sector_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("sort_order", sa.SmallInteger, nullable=False))
    op.create_table("tags",
        sa.Column("tag_id", sa.Text, primary_key=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("profile_rule", sa.Text),
        sa.CheckConstraint("kind IN ('beneficiary', 'benefit_type')", name="ck_tags_kind"))
    op.create_table("states",
        sa.Column("state_code", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True))

    # ── schemes ──
    op.create_table("schemes",
        sa.Column("scheme_id", sa.Text, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("department", sa.Text, nullable=False),
        sa.Column("level", sa.Text, nullable=False),
        sa.Column("primary_sector", sa.Text, sa.ForeignKey("sectors.sector_id"), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("max_benefit_inr", sa.BigInteger),
        sa.Column("max_benefit_period", sa.Text),
        sa.Column("official_url", sa.Text),
        sa.Column("application_url", sa.Text),
        sa.Column("facts_status", sa.Text, nullable=False, server_default="incomplete"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("last_checked", sa.Date, nullable=False),
        sa.Column("created_at", TZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TZ, nullable=False, server_default=NOW),
        sa.CheckConstraint(f"scheme_id ~ '{constants.SCHEME_ID_RE}'", name="ck_schemes_id_format"),
        sa.CheckConstraint("level IN ('central', 'state')", name="ck_schemes_level"),
        sa.CheckConstraint("facts_status IN ('verified', 'extracted', 'incomplete')", name="ck_schemes_facts_status"),
        sa.CheckConstraint("max_benefit_inr >= 0", name="ck_schemes_max_benefit"),
        sa.CheckConstraint("max_benefit_period IN ('one_time', 'per_year', 'per_month')", name="ck_schemes_benefit_period"))
    op.create_index("ix_schemes_primary_sector", "schemes", ["primary_sector"])
    op.create_table("scheme_secondary_sectors",
        sa.Column("scheme_id", sa.Text, sa.ForeignKey("schemes.scheme_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sector_id", sa.Text, sa.ForeignKey("sectors.sector_id"), primary_key=True))
    op.create_table("scheme_tags",
        sa.Column("scheme_id", sa.Text, sa.ForeignKey("schemes.scheme_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Text, sa.ForeignKey("tags.tag_id"), primary_key=True))
    op.create_index("ix_scheme_tags_tag_id", "scheme_tags", ["tag_id"])
    op.create_table("scheme_states",
        sa.Column("scheme_id", sa.Text, sa.ForeignKey("schemes.scheme_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("state_code", sa.Text, sa.ForeignKey("states.state_code"), primary_key=True))
    op.create_index("ix_scheme_states_state_code", "scheme_states", ["state_code"])

    # ── provenance ──
    op.create_table("sources",
        sa.Column("source_id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("scheme_id", sa.Text, sa.ForeignKey("schemes.scheme_id"), nullable=False),
        sa.Column("url", sa.Text, nullable=False, unique=True),
        sa.Column("host", sa.Text, nullable=False),
        sa.Column("approved", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("robots", sa.Text),
        sa.Column("last_status", sa.Text),
        sa.Column("last_checked", TZ),
        sa.CheckConstraint("robots IN ('allowed', 'disallowed', 'no-robots', 'unknown')", name="ck_sources_robots"))
    op.create_index("ix_sources_scheme_id", "sources", ["scheme_id"])
    op.create_table("documents",
        sa.Column("doc_id", sa.String(16), primary_key=True),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("source_id", sa.BigInteger, sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("local_path", sa.Text, nullable=False),
        sa.Column("pages", sa.Integer, nullable=False),
        sa.Column("language", sa.Text, nullable=False, server_default="en"),
        sa.Column("text_layer", sa.Text),
        sa.Column("fetch_method", sa.Text, nullable=False, server_default="auto"),
        sa.Column("ingestion_status", sa.Text, nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("fetched_at", TZ, nullable=False),
        sa.Column("last_checked", TZ, nullable=False),
        sa.UniqueConstraint("source_id", "version", name="uq_documents_source_version"),
        sa.CheckConstraint(f"doc_id ~ '{constants.DOC_ID_RE}'", name="ck_documents_id_format"),
        sa.CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_documents_sha256"),
        sa.CheckConstraint("left(sha256, 16) = doc_id", name="ck_documents_id_from_sha"),
        sa.CheckConstraint("version >= 1", name="ck_documents_version"),
        sa.CheckConstraint("pages > 0", name="ck_documents_pages"),
        sa.CheckConstraint("text_layer IN ('digital', 'scanned', 'mixed')", name="ck_documents_text_layer"),
        sa.CheckConstraint("fetch_method IN ('auto', 'manual')", name="ck_documents_fetch_method"),
        sa.CheckConstraint("ingestion_status IN ('downloaded', 'parsed', 'indexed', 'failed')", name="ck_documents_status"))
    op.create_index("ux_documents_one_current", "documents", ["source_id"], unique=True,
                    postgresql_where=sa.text("is_current"))
    op.create_table("chunks",
        sa.Column("chunk_id", sa.Text, primary_key=True),
        sa.Column("doc_id", sa.String(16), sa.ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("section", sa.Text),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("bbox", pg.ARRAY(sa.Float)),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("embedded_at", TZ),
        sa.CheckConstraint(f"chunk_id ~ '{constants.CHUNK_ID_RE}'", name="ck_chunks_id_format"),
        sa.CheckConstraint("left(chunk_id, 16) = doc_id", name="ck_chunks_id_matches_doc"),
        sa.CheckConstraint("page >= 1", name="ck_chunks_page"),
        sa.CheckConstraint("bbox IS NULL OR cardinality(bbox) = 4", name="ck_chunks_bbox"),
        sa.CheckConstraint("token_count > 0", name="ck_chunks_tokens"))
    op.create_index("ix_chunks_doc_page", "chunks", ["doc_id", "page"])
    op.create_table("ingestion_events",
        sa.Column("event_id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("source_id", sa.BigInteger, sa.ForeignKey("sources.source_id")),
        sa.Column("doc_id", sa.String(16), sa.ForeignKey("documents.doc_id", ondelete="CASCADE")),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("created_at", TZ, nullable=False, server_default=NOW),
        sa.CheckConstraint("stage IN ('audit', 'download', 'parse', 'ocr', 'chunk', 'embed', 'extract', 'refresh')", name="ck_events_stage"),
        sa.CheckConstraint("status IN ('started', 'ok', 'skipped', 'failed')", name="ck_events_status"))
    op.create_index("ix_events_doc_time", "ingestion_events", ["doc_id", "created_at"])

    # ── extracted knowledge ──
    op.create_table("extraction_runs",
        sa.Column("run_id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("scheme_id", sa.Text, sa.ForeignKey("schemes.scheme_id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.Text, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("prompt_version", sa.Text, nullable=False),
        sa.Column("input_chunk_ids", pg.ARRAY(sa.Text), nullable=False),
        sa.Column("raw_output_path", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("started_at", TZ, nullable=False),
        sa.Column("finished_at", TZ),
        sa.CheckConstraint("status IN ('ok', 'partial', 'invalid_json', 'failed')", name="ck_extraction_runs_status"))
    op.create_index("ix_extraction_runs_scheme_time", "extraction_runs", ["scheme_id", "started_at"])
    op.create_table("scheme_facts",
        sa.Column("fact_id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("scheme_id", sa.Text, sa.ForeignKey("schemes.scheme_id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("citation_id", sa.Text, sa.ForeignKey("chunks.chunk_id"), nullable=False),
        sa.Column("review_status", sa.Text, nullable=False, server_default="unreviewed"),
        sa.Column("run_id", sa.BigInteger, sa.ForeignKey("extraction_runs.run_id", ondelete="SET NULL")),
        sa.UniqueConstraint("scheme_id", "kind", "position", name="uq_scheme_facts_position"),
        sa.CheckConstraint("kind IN ('summary', 'benefit', 'document_required', 'application_step')", name="ck_scheme_facts_kind"),
        sa.CheckConstraint("position >= 0", name="ck_scheme_facts_position"),
        sa.CheckConstraint(REVIEW, name="ck_scheme_facts_review"))
    op.create_table("eligibility_rules",
        sa.Column("rule_id", sa.Text, primary_key=True),
        sa.Column("scheme_id", sa.Text, sa.ForeignKey("schemes.scheme_id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.Text, nullable=False),
        sa.Column("operator", sa.Text, nullable=False),
        sa.Column("value", pg.JSONB),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("source_text", sa.Text, nullable=False),
        sa.Column("citation_id", sa.Text, sa.ForeignKey("chunks.chunk_id"), nullable=False),
        sa.Column("confidence", sa.REAL),
        sa.Column("review_status", sa.Text, nullable=False, server_default="unreviewed"),
        sa.Column("run_id", sa.BigInteger, sa.ForeignKey("extraction_runs.run_id", ondelete="SET NULL")),
        sa.CheckConstraint("operator IN ('eq', 'in', 'not_in', 'lte', 'gte', 'between', 'is_true', 'is_false', 'manual')", name="ck_rules_operator"),
        sa.CheckConstraint("kind IN ('required', 'exclusion')", name="ck_rules_kind"),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_rules_confidence"),
        sa.CheckConstraint(REVIEW, name="ck_rules_review"),
        sa.CheckConstraint(f"field <> '{constants.UNMAPPED_FIELD}' OR operator = 'manual'", name="ck_rules_unmapped_is_manual"))
    op.create_index("ix_eligibility_rules_scheme_id", "eligibility_rules", ["scheme_id"])

    # ── users & workflow (B) ──
    op.create_table("users",
        sa.Column("user_id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TZ, nullable=False, server_default=NOW))
    op.create_index("ux_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
    op.create_table("profiles",
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("version", sa.Integer, primary_key=True),
        sa.Column("attributes", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("complete", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TZ, nullable=False, server_default=NOW),
        sa.CheckConstraint("version >= 1", name="ck_profiles_version"))
    op.create_index("ux_profiles_one_current", "profiles", ["user_id"], unique=True, postgresql_where=sa.text("is_current"))
    op.create_table("workflow_runs",
        sa.Column("run_id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("workflow", sa.Text, nullable=False),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE")),
        sa.Column("profile_version", sa.Integer),
        sa.Column("scheme_ids", pg.ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("params", pg.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("state", pg.JSONB),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("started_at", TZ, nullable=False, server_default=NOW),
        sa.Column("finished_at", TZ),
        sa.Column("invalidated_at", TZ),
        sa.CheckConstraint("workflow IN ('W1', 'W2', 'W3', 'W4', 'W5', 'W6')", name="ck_runs_workflow"),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed', 'invalidated')", name="ck_runs_status"))
    op.create_index("ix_runs_cache_lookup", "workflow_runs", ["user_id", "workflow", "profile_version"],
                    postgresql_where=sa.text("status = 'completed'"))
    op.create_index("ix_runs_scheme_ids", "workflow_runs", ["scheme_ids"], postgresql_using="gin")
    op.create_table("comparison_sessions",
        sa.Column("session_id", pg.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", pg.UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheme_ids", pg.ARRAY(sa.Text), nullable=False),
        sa.Column("run_id", pg.UUID(as_uuid=True), sa.ForeignKey("workflow_runs.run_id", ondelete="SET NULL")),
        sa.Column("created_at", TZ, nullable=False, server_default=NOW),
        sa.CheckConstraint("cardinality(scheme_ids) BETWEEN 2 AND 5", name="ck_comparison_size"))
    op.create_index("ix_comparison_sessions_user_id", "comparison_sessions", ["user_id"])

    # ── contract view ──
    op.execute("""
        CREATE VIEW document_meta_v WITH (security_invoker = true) AS
        SELECT d.doc_id, s.scheme_id, d.title, s.url AS source_url, d.local_path, d.sha256, d.pages,
               d.version, d.fetched_at, d.last_checked, d.ingestion_status, d.language, d.text_layer,
               d.fetch_method, d.error, d.is_current
        FROM documents d JOIN sources s ON s.source_id = d.source_id""")

    # ── reference data (vocabularies approved 2026-10-12) ──
    op.bulk_insert(sa.table("sectors", sa.column("sector_id"), sa.column("name"), sa.column("sort_order")),
                   [{"sector_id": k, "name": v, "sort_order": i} for i, (k, v) in enumerate(constants.SECTORS.items(), 1)])
    tags = sa.table("tags", sa.column("tag_id"), sa.column("kind"), sa.column("label"), sa.column("profile_rule"))
    op.bulk_insert(tags, [{"tag_id": k, "kind": "beneficiary", "label": k.replace("_", " "), "profile_rule": rule}
                          for k, rule in constants.BENEFICIARY_TAGS.items()])
    op.bulk_insert(tags, [{"tag_id": k, "kind": "benefit_type", "label": k.replace("_", " "), "profile_rule": None}
                          for k in constants.BENEFIT_TYPES])
    op.bulk_insert(sa.table("states", sa.column("state_code"), sa.column("name")),
                   [{"state_code": constants.ALL_STATES, "name": "All India"}]
                   + [{"state_code": k, "name": v} for k, v in constants.STATES.items()])

    # ── Supabase: deny the auto-generated public REST API; the backend's own role owns the tables ──
    for table in TABLES_IN_ORDER:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS document_meta_v")
    for table in reversed(TABLES_IN_ORDER):
        op.drop_table(table)
