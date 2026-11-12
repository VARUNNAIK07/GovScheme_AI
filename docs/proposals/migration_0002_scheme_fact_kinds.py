"""PROPOSAL for B (not active: lives in docs/proposals, NOT in backend/migrations/versions).

Allow scheme_facts.kind 'max_benefit' and 'limitation', so Scheme.max_benefit_inr and Scheme.limitations
can carry real citations (contracts v1.2, constants.FACT_KIND_BY_FIELD). Nothing else changes:
no new tables, no data rewritten, all existing facts/citations kept.

To adopt (B):
  1. copy this file to backend/migrations/versions/0002_scheme_fact_kinds.py
  2. in backend/app/db/models.py, SchemeFact.__table_args__: add "max_benefit", "limitation" to the
     ck_scheme_facts_kind tuple
  3. alembic -c backend/alembic.ini upgrade head   (then `alembic check` must report no drift)
  4. remove the xfail marker on test_fact_kinds_storable in backend/tests/test_contracts_db.py

Revision ID: 0002
Revises: 0001
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
