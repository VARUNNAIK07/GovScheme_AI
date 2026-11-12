from contracts.schemas import LibraryResult

from backend.app.controller.workflow import WorkflowController


def get_library(user, controller: WorkflowController | None = None) -> LibraryResult:
    state = (controller or WorkflowController()).library(user.profile)
    return state.library

