from contracts.schemas import AuthResponse, LoginRequest, Me, PublicUser, RegisterRequest

from backend.app.core.config import get_settings
from backend.app.core.security import create_token, verify_password
from backend.app.db.repositories import SqlRepository


def _public_user(user) -> PublicUser:
    return PublicUser(user_id=user.user_id, email=user.email, name=user.name)


def _token(user_id: str) -> str:
    settings = get_settings()
    return create_token(user_id, settings.require("jwt_secret"), settings.jwt_issuer, settings.jwt_ttl_s)


def register(request: RegisterRequest, repo: SqlRepository) -> AuthResponse:
    user = repo.create_user(request.email, request.password, request.name)
    return AuthResponse(user=_public_user(user), token=_token(user.user_id))


def login(request: LoginRequest, repo: SqlRepository) -> AuthResponse:
    user = repo.get_user_by_email(request.email)
    if user is None or not verify_password(request.password, user.password_hash):
        raise ValueError("Invalid email or password")
    return AuthResponse(user=_public_user(user), token=_token(user.user_id))


def me(user) -> Me:
    return Me(
        user=_public_user(user),
        profile_complete=user.profile.complete,
        profile_version=user.profile.version,
    )

