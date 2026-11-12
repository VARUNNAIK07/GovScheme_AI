from contracts.schemas import ComparisonRequest, ComparisonResponse, LibraryCard

from backend.app.controller.workflow import WorkflowController


def options(user, controller: WorkflowController | None = None) -> list[LibraryCard]:
    return (controller or WorkflowController()).comparison_options(user.profile)


def compare(user, request: ComparisonRequest, controller: WorkflowController | None = None) -> ComparisonResponse:
    return (controller or WorkflowController()).compare(user.profile, request.scheme_ids)
