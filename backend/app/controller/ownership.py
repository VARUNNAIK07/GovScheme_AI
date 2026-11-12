CONTROLLER_WRITES = {"schemes", "rules", "refresh"}
AGENT_WRITES = {"next_question", "eligibility", "scores", "library", "comparison", "summary"}


def can_controller_write(field: str) -> bool:
    return field in CONTROLLER_WRITES


def can_agent_write(field: str) -> bool:
    return field in AGENT_WRITES

