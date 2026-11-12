from contracts.schemas import SchemeDetail

from backend.app.controller.workflow import WorkflowController


def get_scheme_detail(user, scheme_id: str, controller: WorkflowController | None = None) -> SchemeDetail:
    return (controller or WorkflowController()).scheme_detail(user.profile, scheme_id)

