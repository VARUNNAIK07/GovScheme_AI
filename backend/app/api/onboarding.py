from contracts.schemas import AnswerRequest, AnswerResponse, OnboardingNext

from backend.app.agents.profiling import apply_answer, next_question
from backend.app.db.repositories import SqlRepository


def get_next(user) -> OnboardingNext:
    question = next_question(user.profile)
    return OnboardingNext(done=question is None, question=question)


def answer(user, request: AnswerRequest, repo: SqlRepository) -> AnswerResponse:
    try:
        profile = repo.save_profile(apply_answer(user.profile, request.field, request.value))
    except ValueError as exc:
        return AnswerResponse(ok=False, errors=[str(exc)], done=False, question=next_question(user.profile))
    question = next_question(profile)
    return AnswerResponse(ok=True, errors=[], done=question is None, question=question)

