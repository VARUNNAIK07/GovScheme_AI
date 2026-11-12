"""Allow scheme_facts.kind 'max_benefit' and 'limitation' (contracts v1.2, FACT_KIND_BY_FIELD).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
Drafted in docs/proposals/migration_0002_scheme_fact_kinds.py; approved by the DB owner 2026-10-13.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

OLD = ("summary", "benefit", "document_required", "application_step")
NEW = OLD + ("max_benefit", "limitation")


def _check(values) -> str:
    return "kind IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # Widening a CHECK never invalidates existing rows. PostgreSQL validates on ADD; all rows pass.
    op.drop_constraint("ck_scheme_facts_kind", "scheme_facts", type_="check")
    op.create_check_constraint("ck_scheme_facts_kind", "scheme_facts", _check(NEW))


def downgrade() -> None:
    # Refuses (CHECK violation) if any 'max_benefit'/'limitation' rows exist: delete them first on purpose.
    op.drop_constraint("ck_scheme_facts_kind", "scheme_facts", type_="check")
    op.create_check_constraint("ck_scheme_facts_kind", "scheme_facts", _check(OLD))
