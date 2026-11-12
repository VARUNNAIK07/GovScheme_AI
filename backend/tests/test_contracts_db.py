"""Contracts <-> database consistency (static: inspects models, needs no running database).

Every field of a contract model stored in PostgreSQL must come from a real column (or a
documented derivation), and every Literal in the contracts must equal the DB CHECK values.
"""
import re
import typing

import pytest

from contracts import constants
from contracts import schemas as c
from backend.app.db import models as m

COL = lambda model, name: (model, name)  # noqa: E731

# contract field -> where it comes from in the database
MAPPING = {
    c.Scheme: {
        "scheme_id": COL(m.SchemeRow, "scheme_id"), "name": COL(m.SchemeRow, "name"),
        "sector": COL(m.SchemeRow, "primary_sector"), "department": COL(m.SchemeRow, "department"),
        "level": COL(m.SchemeRow, "level"), "states": COL(m.SchemeState, "state_code"),
        "beneficiary_tags": COL(m.SchemeTag, "tag_id"), "summary": COL(m.SchemeRow, "summary"),
        "benefits": COL(m.SchemeFact, "text"), "max_benefit_inr": COL(m.SchemeRow, "max_benefit_inr"),
        "documents_required": COL(m.SchemeFact, "text"), "application_steps": COL(m.SchemeFact, "text"),
        "official_url": COL(m.SchemeRow, "official_url"), "application_url": COL(m.SchemeRow, "application_url"),
        "doc_ids": COL(m.DocumentRow, "doc_id"), "facts_status": COL(m.SchemeRow, "facts_status"),
        "last_checked": COL(m.SchemeRow, "last_checked"),
        "secondary_sectors": COL(m.SchemeSecondarySector, "sector_id"), "benefit_types": COL(m.SchemeTag, "tag_id"),
        "max_benefit_period": COL(m.SchemeRow, "max_benefit_period"),
        "fact_citations": COL(m.SchemeFact, "citation_id"), "limitations": COL(m.SchemeFact, "text"),
    },
    c.EligibilityRule: {f: COL(m.EligibilityRuleRow, f) for f in c.EligibilityRule.model_fields},
    c.DocumentMeta: {
        **{f: COL(m.DocumentRow, f) for f in c.DocumentMeta.model_fields if f not in ("scheme_id", "source_url")},
        "scheme_id": COL(m.Source, "scheme_id"), "source_url": COL(m.Source, "url"),
    },
    c.Evidence: {
        "citation_id": COL(m.ChunkRow, "chunk_id"), "chunk_id": COL(m.ChunkRow, "chunk_id"),
        "doc_id": COL(m.ChunkRow, "doc_id"), "scheme_id": COL(m.Source, "scheme_id"),
        "section": COL(m.ChunkRow, "section"), "page": COL(m.ChunkRow, "page"), "text": COL(m.ChunkRow, "text"),
        "bbox": COL(m.ChunkRow, "bbox"), "source_url": COL(m.Source, "url"),
        "doc_version": COL(m.DocumentRow, "version"), "score": None,  # search-time only
    },
}


@pytest.mark.parametrize("contract", list(MAPPING), ids=lambda x: x.__name__)
def test_every_contract_field_has_a_db_source(contract):
    mapping = MAPPING[contract]
    assert set(mapping) == set(contract.model_fields), "contract fields and mapping differ"
    for field, target in mapping.items():
        if target is None:
            continue
        model, column = target
        assert column in model.__table__.columns, f"{contract.__name__}.{field} -> {model.__tablename__}.{column} missing"


def _check_values(model, column: str) -> set[str]:
    for con in model.__table__.constraints:
        sql = str(getattr(con, "sqltext", ""))
        if sql.startswith(f"{column} IN ("):
            return set(re.findall(r"'([^']*)'", sql))
    raise AssertionError(f"no CHECK ... IN (...) for {model.__tablename__}.{column}")


def _literal_values(contract, field) -> set[str]:
    ann = contract.model_fields[field].annotation
    args = typing.get_args(ann)
    lit = next((a for a in (args or (ann,)) if typing.get_origin(a) is typing.Literal), ann)
    return set(typing.get_args(lit))


@pytest.mark.parametrize("contract,field,model,column", [
    (c.Scheme, "level", m.SchemeRow, "level"),
    (c.Scheme, "facts_status", m.SchemeRow, "facts_status"),
    (c.Scheme, "max_benefit_period", m.SchemeRow, "max_benefit_period"),
    (c.EligibilityRule, "operator", m.EligibilityRuleRow, "operator"),
    (c.EligibilityRule, "kind", m.EligibilityRuleRow, "kind"),
    (c.DocumentMeta, "ingestion_status", m.DocumentRow, "ingestion_status"),
    (c.DocumentMeta, "text_layer", m.DocumentRow, "text_layer"),
    (c.DocumentMeta, "fetch_method", m.DocumentRow, "fetch_method"),
    (c.WorkflowState, "workflow", m.WorkflowRun, "workflow"),
])
def test_literals_match_db_checks(contract, field, model, column):
    assert _literal_values(contract, field) == _check_values(model, column)


def test_eligibility_statuses_constant_matches_contract():
    assert set(typing.get_args(c.EligibilityStatus)) == set(constants.ELIGIBILITY_STATUSES)


def test_id_regexes_used_in_db_checks():
    sql = " ".join(str(getattr(k, "sqltext", "")) for t in (m.SchemeRow, m.DocumentRow, m.ChunkRow)
                   for k in t.__table__.constraints)
    for regex in (constants.SCHEME_ID_RE, constants.DOC_ID_RE, constants.CHUNK_ID_RE):
        assert regex in sql


def test_fact_kinds_storable():
    """Every kind in constants.FACT_KIND_BY_FIELD must be allowed by the scheme_facts.kind CHECK (migration 0002)."""
    assert set(constants.FACT_KIND_BY_FIELD.values()) <= _check_values(m.SchemeFact, "kind")
