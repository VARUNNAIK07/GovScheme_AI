"""PostgreSQL repository for Person B's data: users, versioned profiles, workflow-run cache.

Same method names as B's former InMemoryRepository (create_user, get_user_by_email, get_user,
save_profile), so agents/controller/api code is unchanged. Uses the shared engine/models only.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, update

from contracts.schemas import Profile, ProfileAttributes, WorkflowState
from backend.app.core.security import hash_password
from backend.app.db import models as m
from backend.app.db.session import session_scope


@dataclass
class UserRecord:
    user_id: str
    email: str
    name: str
    password_hash: str
    profile: Profile


def _profile(row: m.ProfileRow) -> Profile:
    return Profile(user_id=str(row.user_id), version=row.version,
                   attributes=ProfileAttributes(**(row.attributes or {})), complete=row.complete)


class SqlRepository:
    # ── users + profiles ──
    def create_user(self, email: str, password: str, name: str) -> UserRecord:
        email = email.strip()
        with session_scope() as s:
            if s.scalar(select(m.User.user_id).where(func.lower(m.User.email) == email.lower())):
                raise ValueError("Email already registered")
            user = m.User(user_id=uuid.uuid4(), email=email, name=name.strip(), password_hash=hash_password(password))
            s.add(user)
            s.flush()
            prof = m.ProfileRow(user_id=user.user_id, version=1, attributes={}, complete=False, is_current=True)
            s.add(prof)
            s.flush()
            return UserRecord(str(user.user_id), user.email, user.name, user.password_hash, _profile(prof))

    def _find(self, condition) -> UserRecord | None:
        """User + current profile in ONE round trip (every authenticated request does this)."""
        with session_scope() as s:
            row = s.execute(select(m.User, m.ProfileRow).join(
                m.ProfileRow, (m.ProfileRow.user_id == m.User.user_id) & m.ProfileRow.is_current)
                .where(condition, m.User.is_active)).first()
            if row is None:
                return None
            user, prof = row
            return UserRecord(str(user.user_id), user.email, user.name, user.password_hash, _profile(prof))

    def get_user_by_email(self, email: str) -> UserRecord | None:
        return self._find(func.lower(m.User.email) == email.strip().lower())

    def get_user(self, user_id: str) -> UserRecord | None:
        try:
            uid = uuid.UUID(str(user_id))
        except ValueError:
            return None
        return self._find(m.User.user_id == uid)

    def save_profile(self, profile: Profile) -> Profile:
        """Store a NEW profile version and make it current (older versions are kept for history)."""
        uid = uuid.UUID(profile.user_id)
        with session_scope() as s:
            s.execute(update(m.ProfileRow).where(m.ProfileRow.user_id == uid, m.ProfileRow.is_current)
                      .values(is_current=False))
            s.add(m.ProfileRow(user_id=uid, version=profile.version, complete=profile.complete, is_current=True,
                               attributes=profile.attributes.model_dump(exclude_defaults=True)))
        return profile

    # ── workflow-run cache (W2/W3 keyed by user + profile_version + scheme_ids) ──
    def find_run(self, workflow: str, user_id: str, profile_version: int,
                 scheme_ids: list[str] | None = None) -> WorkflowState | None:
        """scheme_ids=None matches any run of that workflow/version (W2); a list must match exactly (W3)."""
        with session_scope() as s:
            q = select(m.WorkflowRun).where(
                m.WorkflowRun.workflow == workflow, m.WorkflowRun.user_id == uuid.UUID(user_id),
                m.WorkflowRun.profile_version == profile_version, m.WorkflowRun.status == "completed")
            if scheme_ids is not None:
                q = q.where(m.WorkflowRun.scheme_ids == sorted(scheme_ids))
            row = s.scalars(q.order_by(m.WorkflowRun.started_at.desc()).limit(1)).first()
            return WorkflowState.model_validate(row.state) if row and row.state else None

    def save_run(self, state: WorkflowState, scheme_ids: list[str]) -> None:
        with session_scope() as s:
            s.add(m.WorkflowRun(run_id=uuid.UUID(state.run_id), workflow=state.workflow,
                                user_id=uuid.UUID(state.user_id) if state.user_id else None,
                                profile_version=state.profile_version, scheme_ids=sorted(scheme_ids),
                                state=state.model_dump(mode="json"), status="completed",
                                finished_at=datetime.now(timezone.utc)))

    def invalidate_user_runs(self, user_id: str) -> int:
        with session_scope() as s:
            res = s.execute(update(m.WorkflowRun).where(m.WorkflowRun.user_id == uuid.UUID(user_id),
                                                        m.WorkflowRun.status == "completed")
                            .values(status="invalidated", invalidated_at=datetime.now(timezone.utc)))
            return res.rowcount or 0

    def invalidate_scheme_runs(self, scheme_ids: list[str]) -> list[str]:
        """W6: invalidate cached runs that used any of these schemes; returns their run_ids."""
        if not scheme_ids:
            return []
        with session_scope() as s:
            ids = list(s.scalars(update(m.WorkflowRun).where(m.WorkflowRun.status == "completed",
                                                             m.WorkflowRun.scheme_ids.overlap(scheme_ids))
                                 .values(status="invalidated", invalidated_at=datetime.now(timezone.utc))
                                 .returning(m.WorkflowRun.run_id)))
            return [str(i) for i in ids]

    def save_comparison(self, user_id: str, scheme_ids: list[str], run_id: str | None) -> None:
        with session_scope() as s:
            s.add(m.ComparisonSession(user_id=uuid.UUID(user_id), scheme_ids=scheme_ids,
                                      run_id=uuid.UUID(run_id) if run_id else None))


# Kept for B's name: the API layer asks for "the repository".
_repository = SqlRepository()


def get_repository() -> SqlRepository:
    return _repository
