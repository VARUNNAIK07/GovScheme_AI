from contracts.schemas import Profile, ProfileAttributes, ProfileUpdateRequest, ProfileUpdateResponse, Question

from backend.app.agents.profiling import next_question, prune_hidden, validate_answer, visible_questions
from backend.app.controller.workflow import WorkflowController
from backend.app.core.errors import AppError
from backend.app.db.repositories import SqlRepository

FREE_FIELDS = {"district"}            # profile fields with no question in the bank (not validated against options)


def get_profile(user) -> Profile:
    return user.profile


def _merged(user, request: ProfileUpdateRequest) -> ProfileAttributes:
    data = user.profile.attributes.model_dump()
    data.update(request.attributes.model_dump(exclude_unset=True))
    return ProfileAttributes(**data)


def questions_for(user, request: ProfileUpdateRequest) -> list[Question]:
    """Questions that apply to a draft of the profile (nothing is saved). The profile page calls this
    as the user edits, so follow-up questions appear/disappear and options adapt."""
    return visible_questions(_merged(user, request))


def update_profile(
    user,
    request: ProfileUpdateRequest,
    repo: SqlRepository,
    controller: WorkflowController | None = None,
) -> ProfileUpdateResponse:
    updates = request.attributes.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if field in FREE_FIELDS or value is None or value == []:
            continue
        errors = validate_answer(field, value)
        if errors:
            raise AppError("validation_error", f"{field}: {errors[0]}", 422)
    attrs = prune_hidden(_merged(user, request))
    draft = Profile(user_id=user.user_id, version=user.profile.version + 1, attributes=attrs, complete=False)
    profile = draft.model_copy(update={"complete": next_question(draft) is None})
    repo.save_profile(profile)
    library = (controller or WorkflowController()).after_profile_change(profile).library   # W5 -> W2
    return ProfileUpdateResponse(profile=profile, library=library)
