"""All PostgreSQL tables for GovScheme AI (initial schema, 2026-10-12).

Writers: A = ingestion/knowledge (reference, scheme, provenance, extraction tables),
         B = backend (users, profiles, workflow_runs, comparison_sessions).
PostgreSQL is the source of truth; Qdrant is a search index rebuilt from `chunks`.
Enumerations are TEXT + CHECK (cheaper to extend than PostgreSQL ENUM types).
Changing anything here needs a new Alembic migration (backend/migrations/versions).
"""
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Identity, Index, Integer,
    REAL, SmallInteger, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from contracts import constants


def _in(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


REVIEW_STATUSES = ("unreviewed", "verified", "flagged", "rejected")
NOW = func.now()


class Base(DeclarativeBase):
    pass


# ════════════════════════ Reference data (seeded by migration) ════════════════════════
class Sector(Base):
    __tablename__ = "sectors"
    sector_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger)


class Tag(Base):
    __tablename__ = "tags"
    tag_id: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    label: Mapped[str] = mapped_column(Text)
    profile_rule: Mapped[str | None] = mapped_column(Text)  # NULL = not derivable from a profile
    __table_args__ = (CheckConstraint(_in("kind", ("beneficiary", "benefit_type")), name="ck_tags_kind"),)


class State(Base):
    __tablename__ = "states"
    state_code: Mapped[str] = mapped_column(Text, primary_key=True)  # ISO 3166-2:IN or 'ALL'
    name: Mapped[str] = mapped_column(Text, unique=True)


# ════════════════════════ Schemes (A writes) ════════════════════════
class SchemeRow(Base):
    __tablename__ = "schemes"
    scheme_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    department: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(Text)
    primary_sector: Mapped[str] = mapped_column(ForeignKey("sectors.sector_id"), index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    max_benefit_inr: Mapped[int | None] = mapped_column(BigInteger)
    max_benefit_period: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str | None] = mapped_column(Text)
    application_url: Mapped[str | None] = mapped_column(Text)
    facts_status: Mapped[str] = mapped_column(Text, server_default="incomplete")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    last_checked: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    __table_args__ = (
        CheckConstraint(f"scheme_id ~ '{constants.SCHEME_ID_RE}'", name="ck_schemes_id_format"),
        CheckConstraint(_in("level", ("central", "state")), name="ck_schemes_level"),
        CheckConstraint(_in("facts_status", ("verified", "extracted", "incomplete")), name="ck_schemes_facts_status"),
        CheckConstraint("max_benefit_inr >= 0", name="ck_schemes_max_benefit"),
        CheckConstraint(_in("max_benefit_period", ("one_time", "per_year", "per_month")), name="ck_schemes_benefit_period"),
    )


class SchemeSecondarySector(Base):
    __tablename__ = "scheme_secondary_sectors"  # app rule: max 3 rows, never the primary sector
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_id", ondelete="CASCADE"), primary_key=True)
    sector_id: Mapped[str] = mapped_column(ForeignKey("sectors.sector_id"), primary_key=True)


class SchemeTag(Base):
    __tablename__ = "scheme_tags"
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(ForeignKey("tags.tag_id"), primary_key=True, index=True)


class SchemeState(Base):
    __tablename__ = "scheme_states"
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_id", ondelete="CASCADE"), primary_key=True)
    state_code: Mapped[str] = mapped_column(ForeignKey("states.state_code"), primary_key=True, index=True)


# ════════════════════════ Provenance (A writes) ════════════════════════
class Source(Base):
    __tablename__ = "sources"
    source_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_id"), index=True)  # no source without a scheme
    url: Mapped[str] = mapped_column(Text, unique=True)
    host: Mapped[str] = mapped_column(Text)
    approved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    robots: Mapped[str | None] = mapped_column(Text)
    last_status: Mapped[str | None] = mapped_column(Text)  # '206', '403', 'timeout', ...
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(_in("robots", ("allowed", "disallowed", "no-robots", "unknown")), name="ck_sources_robots"),
    )


class DocumentRow(Base):
    __tablename__ = "documents"
    doc_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.source_id"))
    version: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    title: Mapped[str] = mapped_column(Text)
    local_path: Mapped[str] = mapped_column(Text)
    pages: Mapped[int] = mapped_column(Integer)
    language: Mapped[str] = mapped_column(Text, server_default="en")
    text_layer: Mapped[str | None] = mapped_column(Text)
    fetch_method: Mapped[str] = mapped_column(Text, server_default="auto")
    ingestion_status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_checked: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("source_id", "version", name="uq_documents_source_version"),
        CheckConstraint(f"doc_id ~ '{constants.DOC_ID_RE}'", name="ck_documents_id_format"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_documents_sha256"),
        CheckConstraint("left(sha256, 16) = doc_id", name="ck_documents_id_from_sha"),
        CheckConstraint("version >= 1", name="ck_documents_version"),
        CheckConstraint("pages > 0", name="ck_documents_pages"),
        CheckConstraint(_in("text_layer", ("digital", "scanned", "mixed")), name="ck_documents_text_layer"),
        CheckConstraint(_in("fetch_method", ("auto", "manual")), name="ck_documents_fetch_method"),
        CheckConstraint(_in("ingestion_status", ("downloaded", "parsed", "indexed", "failed")), name="ck_documents_status"),
        Index("ux_documents_one_current", "source_id", unique=True, postgresql_where=text("is_current")),
    )


class ChunkRow(Base):
    __tablename__ = "chunks"
    chunk_id: Mapped[str] = mapped_column(Text, primary_key=True)  # == citation_id
    doc_id: Mapped[str] = mapped_column(ForeignKey("documents.doc_id", ondelete="CASCADE"))
    page: Mapped[int] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    bbox: Mapped[list[float] | None] = mapped_column(ARRAY(Float))
    token_count: Mapped[int] = mapped_column(Integer)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NULL = not in Qdrant yet
    __table_args__ = (
        CheckConstraint(f"chunk_id ~ '{constants.CHUNK_ID_RE}'", name="ck_chunks_id_format"),
        CheckConstraint("left(chunk_id, 16) = doc_id", name="ck_chunks_id_matches_doc"),
        CheckConstraint("page >= 1", name="ck_chunks_page"),
        CheckConstraint("bbox IS NULL OR cardinality(bbox) = 4", name="ck_chunks_bbox"),
        CheckConstraint("token_count > 0", name="ck_chunks_tokens"),
        Index("ix_chunks_doc_page", "doc_id", "page"),
    )


class IngestionEvent(Base):
    __tablename__ = "ingestion_events"
    event_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.source_id"))
    doc_id: Mapped[str | None] = mapped_column(ForeignKey("documents.doc_id", ondelete="CASCADE"))
    stage: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    __table_args__ = (
        CheckConstraint(_in("stage", ("audit", "download", "parse", "ocr", "chunk", "embed", "extract", "refresh")), name="ck_events_stage"),
        CheckConstraint(_in("status", ("started", "ok", "skipped", "failed")), name="ck_events_status"),
        Index("ix_events_doc_time", "doc_id", "created_at"),
    )


# ════════════════════════ Extracted knowledge (A writes; every row cites a chunk) ════════════════════════
class ExtractionRun(Base):
    __tablename__ = "extraction_runs"
    run_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(Text)
    input_chunk_ids: Mapped[list[str]] = mapped_column(ARRAY(Text))
    raw_output_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)  # never contains secrets
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(_in("status", ("ok", "partial", "invalid_json", "failed")), name="ck_extraction_runs_status"),
        Index("ix_extraction_runs_scheme_time", "scheme_id", "started_at"),
    )


class SchemeFact(Base):
    __tablename__ = "scheme_facts"
    fact_id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(SmallInteger)
    text: Mapped[str] = mapped_column(Text)
    citation_id: Mapped[str] = mapped_column(ForeignKey("chunks.chunk_id"))  # no chunk, no fact
    review_status: Mapped[str] = mapped_column(Text, server_default="unreviewed")
    run_id: Mapped[int | None] = mapped_column(ForeignKey("extraction_runs.run_id", ondelete="SET NULL"))
    __table_args__ = (
        UniqueConstraint("scheme_id", "kind", "position", name="uq_scheme_facts_position"),
        CheckConstraint(_in("kind", ("summary", "benefit", "document_required", "application_step",
                                     "max_benefit", "limitation")), name="ck_scheme_facts_kind"),
        CheckConstraint("position >= 0", name="ck_scheme_facts_position"),
        CheckConstraint(_in("review_status", REVIEW_STATUSES), name="ck_scheme_facts_review"),
    )


class EligibilityRuleRow(Base):
    __tablename__ = "eligibility_rules"
    rule_id: Mapped[str] = mapped_column(Text, primary_key=True)  # '{scheme_id}-r{n}'
    scheme_id: Mapped[str] = mapped_column(ForeignKey("schemes.scheme_id", ondelete="CASCADE"), index=True)
    field: Mapped[str] = mapped_column(Text)
    operator: Mapped[str] = mapped_column(Text)
    value: Mapped[Any | None] = mapped_column(JSONB)
    kind: Mapped[str] = mapped_column(Text)
    source_text: Mapped[str] = mapped_column(Text)
    citation_id: Mapped[str] = mapped_column(ForeignKey("chunks.chunk_id"))  # stricter than the contract on purpose
    confidence: Mapped[float | None] = mapped_column(REAL)
    review_status: Mapped[str] = mapped_column(Text, server_default="unreviewed")
    run_id: Mapped[int | None] = mapped_column(ForeignKey("extraction_runs.run_id", ondelete="SET NULL"))
    __table_args__ = (
        CheckConstraint(_in("operator", ("eq", "in", "not_in", "lte", "gte", "between", "is_true", "is_false", "manual")), name="ck_rules_operator"),
        CheckConstraint(_in("kind", ("required", "exclusion")), name="ck_rules_kind"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_rules_confidence"),
        CheckConstraint(_in("review_status", REVIEW_STATUSES), name="ck_rules_review"),
        CheckConstraint(f"field <> '{constants.UNMAPPED_FIELD}' OR operator = 'manual'", name="ck_rules_unmapped_is_manual"),
    )


# ════════════════════════ Users & workflow (B writes) ════════════════════════
class User(Base):
    __tablename__ = "users"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    __table_args__ = (Index("ux_users_email_lower", func.lower(text("email")), unique=True),)


class ProfileRow(Base):
    __tablename__ = "profiles"  # one row per version; exactly one current row per user
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    attributes: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # ProfileAttributes
    complete: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    is_current: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_profiles_version"),
        Index("ux_profiles_one_current", "user_id", unique=True, postgresql_where=text("is_current")),
    )


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    workflow: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"))  # NULL for W6
    profile_version: Mapped[int | None] = mapped_column(Integer)
    scheme_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))  # for W6 invalidation
    params: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    state: Mapped[dict | None] = mapped_column(JSONB)  # WorkflowState
    status: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(_in("workflow", ("W1", "W2", "W3", "W4", "W5", "W6")), name="ck_runs_workflow"),
        CheckConstraint(_in("status", ("running", "completed", "failed", "invalidated")), name="ck_runs_status"),
        Index("ix_runs_cache_lookup", "user_id", "workflow", "profile_version", postgresql_where=text("status = 'completed'")),
        Index("ix_runs_scheme_ids", "scheme_ids", postgresql_using="gin"),
    )


class ComparisonSession(Base):
    __tablename__ = "comparison_sessions"
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    scheme_ids: Mapped[list[str]] = mapped_column(ARRAY(Text))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workflow_runs.run_id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=NOW)
    __table_args__ = (CheckConstraint("cardinality(scheme_ids) BETWEEN 2 AND 5", name="ck_comparison_size"),)


# Contract view DocumentMeta (scheme_id and source_url come from the source row).
# security_invoker: on Supabase a plain view would run as its owner and bypass row-level security.
DOCUMENT_META_VIEW_SQL = """
CREATE VIEW document_meta_v WITH (security_invoker = true) AS
SELECT d.doc_id, s.scheme_id, d.title, s.url AS source_url, d.local_path, d.sha256, d.pages,
       d.version, d.fetched_at, d.last_checked, d.ingestion_status, d.language, d.text_layer,
       d.fetch_method, d.error, d.is_current
FROM documents d JOIN sources s ON s.source_id = d.source_id
"""
