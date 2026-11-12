from fastapi import Depends, Header

from backend.app.core.config import get_settings
from backend.app.core.errors import AppError
from backend.app.core.security import verify_token
from backend.app.db.repositories import SqlRepository, UserRecord, get_repository

__all__ = ["get_repository", "get_current_user"]


def get_current_user(authorization: str | None = Header(default=None),
                     repo: SqlRepository = Depends(get_repository)) -> UserRecord:
    """Resolve 'Authorization: Bearer <JWT>' to the user (with current profile). 401 on any problem."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError("unauthorized", "Missing bearer token", 401)
    settings = get_settings()
    try:
        payload = verify_token(authorization.split(" ", 1)[1].strip(), settings.require("jwt_secret"),
                               settings.jwt_issuer)
    except (ValueError, KeyError) as e:
        raise AppError("unauthorized", str(e) or "Invalid token", 401) from e
    user = repo.get_user(payload.get("sub", ""))
    if user is None:
        raise AppError("unauthorized", "User not found", 401)
    return user
