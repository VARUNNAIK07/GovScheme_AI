from contracts.schemas import RefreshRequest, RefreshResult

from backend.app.controller.workflow import WorkflowController


def refresh(request: RefreshRequest, controller: WorkflowController | None = None) -> RefreshResult:
    """W6. Slow (re-downloads official PDFs); intended for admins, not the citizen UI."""
    return (controller or WorkflowController()).refresh(request.doc_id)
