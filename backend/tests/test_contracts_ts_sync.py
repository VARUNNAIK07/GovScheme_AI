"""contracts/schemas.py <-> contracts/types.ts must agree (static: parses the .ts file as text).

For every Pydantic model (except backend-only ones) there must be a TS interface with the same
fields, the same type, the same nullability, and '?' only where Python has a default.
If this fails after a contract change: update the other file and add a CHANGELOG line.
"""
import inspect
import re
import types
import typing
from pathlib import Path

import pytest
from pydantic import BaseModel

from contracts import schemas as c

TS_PATH = Path(__file__).resolve().parents[2] / "contracts" / "types.ts"
BACKEND_ONLY = {"TraceStep", "WorkflowState"}     # never sent to the frontend as-is
# Deliberate, documented differences: (model, field) -> accepted TS type
TS_OVERRIDES = {
    ("Evidence", "bbox"): "[number, number, number, number] | null",
    ("CitationTarget", "bbox"): "[number, number, number, number] | null",
    ("ProfileUpdateRequest", "attributes"): "Partial<ProfileAttributes>",
}
ALIASES = {"EligibilityStatus": c.EligibilityStatus}


def _models() -> dict[str, type[BaseModel]]:
    return {n: o for n, o in vars(c).items()
            if inspect.isclass(o) and issubclass(o, BaseModel) and o is not BaseModel and n not in BACKEND_ONLY}


def _parse_ts() -> dict[str, dict[str, tuple[bool, str]]]:
    """interface name -> {field: (optional, type)}"""
    text = TS_PATH.read_text(encoding="utf-8")
    out = {}
    for name, body in re.findall(r"export interface (\w+) \{(.*?)\n\}", text, flags=re.S):
        body = re.sub(r"//[^\n]*", "", body)
        fields = {}
        for decl in filter(None, (d.strip() for d in body.split(";"))):
            m = re.fullmatch(r"(\w+)(\?)?\s*:\s*(.+)", decl, flags=re.S)
            assert m, f"{name}: cannot parse {decl!r}"
            fields[m[1]] = (bool(m[2]), m[3])
        out[name] = fields
    return out


def _expected_ts(ann) -> str:
    for alias, target in ALIASES.items():
        if ann == target:
            return alias
    origin, args = typing.get_origin(ann), typing.get_args(ann)
    if ann is typing.Any:
        return "unknown"
    if origin in (typing.Union, types.UnionType):
        parts = [_expected_ts(a) for a in args if a is not type(None)]
        return " | ".join(parts + (["null"] if type(None) in args else []))
    if origin is typing.Literal:
        return " | ".join(f'"{a}"' for a in args)
    if origin is list:
        inner = _expected_ts(args[0])
        return f"({inner})[]" if "|" in inner else f"{inner}[]"
    if origin is dict:
        return f"Record<string, {_expected_ts(args[1])}>"
    if inspect.isclass(ann) and issubclass(ann, BaseModel):
        return ann.__name__
    return {str: "string", int: "number", float: "number", bool: "boolean"}[ann]


def _norm(ts_type: str) -> frozenset[str]:
    """Whitespace-free, order-free set of top-level union members."""
    flat = re.sub(r"\s+", "", ts_type)
    parts, depth, cur = [], 0, ""
    for ch in flat:
        depth += ch in "<([{"
        depth -= ch in ">)]}"
        if ch == "|" and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    return frozenset(p for p in parts + [cur] if p)


TS = _parse_ts()


def test_every_python_model_has_a_ts_interface():
    missing = sorted(set(_models()) - set(TS))
    assert not missing, f"add to types.ts: {missing}"


def test_no_orphan_ts_interfaces():
    orphans = sorted(set(TS) - set(_models()))
    assert not orphans, f"types.ts interfaces with no Python model: {orphans}"


@pytest.mark.parametrize("name", sorted(_models()))
def test_fields_types_and_optionality_match(name):
    model, ts_fields = _models()[name], TS.get(name, {})
    assert set(model.model_fields) == set(ts_fields), (
        f"{name}: only in Python {sorted(set(model.model_fields) - set(ts_fields))}, "
        f"only in TS {sorted(set(ts_fields) - set(model.model_fields))}")
    for field, info in model.model_fields.items():
        optional, ts_type = ts_fields[field]
        if optional:
            assert not info.is_required(), f"{name}.{field}: '?' in TS but required in Python"
        expected = TS_OVERRIDES.get((name, field)) or _expected_ts(info.annotation)
        assert _norm(ts_type) == _norm(expected), f"{name}.{field}: TS {ts_type!r} != expected {expected!r}"


def test_eligibility_status_alias_matches():
    m = re.search(r"export type EligibilityStatus =(.*?);", TS_PATH.read_text(encoding="utf-8"), flags=re.S)
    assert _norm(m[1].strip().lstrip("|")) == frozenset(f'"{v}"' for v in typing.get_args(c.EligibilityStatus))
