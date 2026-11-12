from typing import Any

from contracts import constants
from contracts.schemas import EligibilityResult, EligibilityRule, ProfileAttributes, RuleCheck
from contracts.semantics import eligibility_status, rule_result


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return actual == expected
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    if operator == "lte":
        return actual <= expected
    if operator == "gte":
        return actual >= expected
    if operator == "between":
        lower, upper = expected
        return lower <= actual <= upper
    if operator == "is_true":
        return actual is True
    if operator == "is_false":
        return actual is False
    raise ValueError(f"Unsupported operator: {operator}")


def evaluate_condition(attrs: ProfileAttributes, rule: EligibilityRule) -> bool | None:
    if rule.operator == "manual" or rule.field == constants.UNMAPPED_FIELD:
        return None
    if not hasattr(attrs, rule.field):
        raise ValueError(f"Rule {rule.rule_id} references unknown field {rule.field}")
    actual = getattr(attrs, rule.field)
    if actual is None:
        return None
    return _compare(actual, rule.operator, rule.value)


def _reason(rule: EligibilityRule, result: str) -> str:
    prefix = {
        "pass": "Requirement satisfied",
        "fail": "Requirement not met" if rule.kind == "required" else "Exclusion applies",
        "unknown": "More profile information needed",
        "ambiguous": "Needs manual verification",
    }[result]
    return f"{prefix}: {rule.source_text}"


def evaluate(attrs: ProfileAttributes, scheme_id: str, rules: list[EligibilityRule]) -> EligibilityResult:
    checks: list[RuleCheck] = []
    missing_fields: list[str] = []

    for rule in rules:
        condition = evaluate_condition(attrs, rule)
        result = rule_result(rule.kind, rule.operator, condition)
        if result == "unknown" and rule.field != constants.UNMAPPED_FIELD:
            missing_fields.append(rule.field)
        checks.append(RuleCheck(
            rule_id=rule.rule_id,
            result=result,
            reason=_reason(rule, result),
            citation_id=rule.citation_id,
        ))

    status = eligibility_status([check.result for check in checks])
    if not checks:
        reasons = ["Eligibility criteria not extracted yet."]
    else:
        reasons = [check.reason for check in checks if check.result != "pass"] or ["All extracted eligibility checks passed."]

    return EligibilityResult(
        scheme_id=scheme_id,
        status=status,
        checks=checks,
        reasons=reasons,
        missing_fields=sorted(set(missing_fields)),
    )

