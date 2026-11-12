"""GovScheme AI API (build plan section 5). Run from the repo root:

    uvicorn backend.app.main:app --reload --port 8000        # interactive docs: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from contracts.schemas import (AnswerRequest, AnswerResponse, AuthResponse, CitationTarget, ComparisonRequest,
                               ComparisonResponse, HealthResponse, LibraryCard, LibraryResult, LoginRequest, Me,
                               OnboardingNext, Profile, ProfileUpdateRequest, ProfileUpdateResponse, Question, RefreshRequest,
                               RefreshResult, RegisterRequest, SchemeDetail)
from backend.app.api import admin, auth, citations, comparison, health, library, onboarding, profile, schemes
from backend.app.api.deps import get_current_user, get_repository
from backend.app.core.config import get_settings
from backend.app.core.errors import AppError, install_error_handlers
from backend.app.db.repositories import SqlRepository, UserRecord


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not get_settings().use_stubs:
        from backend.app.knowledge.embedder import get_model
        get_model()                       # load BGE once at startup, not on the first user's request
    yield
    if not get_settings().use_stubs:
        from backend.app.knowledge.qdrant_store import close_client
        close_client()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="GovScheme AI API", version="1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
                       allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
    install_error_handlers(app)
    User = Depends(get_current_user)
    Repo = Depends(get_repository)

    # ── auth ──
    @app.post("/api/auth/register", response_model=AuthResponse, tags=["auth"])
    def register(body: RegisterRequest, repo: SqlRepository = Repo):
        if len(body.password) < 8:
            raise AppError("validation_error", "Password must be at least 8 characters", 422)
        try:
            return auth.register(body, repo)
        except ValueError as e:
            raise AppError("email_taken", str(e), 409) from e

    @app.post("/api/auth/login", response_model=AuthResponse, tags=["auth"])
    def login(body: LoginRequest, repo: SqlRepository = Repo):
        try:
            return auth.login(body, repo)
        except ValueError as e:
            raise AppError("invalid_credentials", str(e), 401) from e

    @app.get("/api/me", response_model=Me, tags=["auth"])
    def me(user: UserRecord = User):
        return auth.me(user)

    # ── W1 onboarding ──
    @app.get("/api/onboarding/next", response_model=OnboardingNext, tags=["onboarding"])
    def onboarding_next(user: UserRecord = User):
        return onboarding.get_next(user)

    @app.post("/api/onboarding/answer", response_model=AnswerResponse, tags=["onboarding"])
    def onboarding_answer(body: AnswerRequest, user: UserRecord = User, repo: SqlRepository = Repo):
        return onboarding.answer(user, body, repo)

    # ── profile (W5) ──
    @app.get("/api/profile", response_model=Profile, tags=["profile"])
    def get_profile(user: UserRecord = User):
        return profile.get_profile(user)

    @app.put("/api/profile", response_model=ProfileUpdateResponse, tags=["profile"])
    def put_profile(body: ProfileUpdateRequest, user: UserRecord = User, repo: SqlRepository = Repo):
        return profile.update_profile(user, body, repo)

    @app.post("/api/profile/questions", response_model=list[Question], tags=["profile"])
    def profile_questions(body: ProfileUpdateRequest, user: UserRecord = User):
        return profile.questions_for(user, body)

    # ── W2 library, W3 scheme detail ──
    @app.get("/api/library", response_model=LibraryResult, tags=["library"])
    def get_library(user: UserRecord = User):
        return library.get_library(user)

    @app.get("/api/schemes/{scheme_id}", response_model=SchemeDetail, tags=["library"])
    def get_scheme(scheme_id: str, user: UserRecord = User):
        try:
            return schemes.get_scheme_detail(user, scheme_id)
        except KeyError as e:
            raise AppError("not_found", f"Scheme '{scheme_id}' not found", 404) from e

    # ── W4 comparison ──
    @app.get("/api/comparison/options", response_model=list[LibraryCard], tags=["comparison"])
    def comparison_options(user: UserRecord = User):
        return comparison.options(user)

    @app.post("/api/comparison", response_model=ComparisonResponse, tags=["comparison"])
    def compare(body: ComparisonRequest, user: UserRecord = User):
        try:
            return comparison.compare(user, body)
        except ValueError as e:
            raise AppError("invalid_comparison", str(e), 400) from e

    # ── citations + source PDFs ──
    @app.get("/api/citations/{citation_id}", response_model=CitationTarget, tags=["citations"])
    def get_citation(citation_id: str, user: UserRecord = User):
        try:
            return citations.resolve(citation_id)
        except KeyError as e:
            raise AppError("citation_not_found", f"Citation '{citation_id}' not found", 404) from e

    @app.get("/api/documents/{doc_id}/file", tags=["citations"], response_class=FileResponse)
    def get_document_file(doc_id: str, user: UserRecord = User):
        try:
            return FileResponse(citations.document_path(doc_id), media_type="application/pdf",
                                filename=f"{doc_id}.pdf", content_disposition_type="inline")
        except KeyError as e:
            raise AppError("not_found", f"Document '{doc_id}' not found", 404) from e

    # ── W6 admin refresh, health ──
    @app.post("/api/admin/refresh", response_model=RefreshResult, tags=["admin"])
    def refresh(body: RefreshRequest, user: UserRecord = User):
        return admin.refresh(body)

    @app.get("/api/health", response_model=HealthResponse, tags=["health"])
    def get_health():
        return health.health()

    return app


app = create_app()
