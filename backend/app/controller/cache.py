from collections import OrderedDict
from threading import Lock

from contracts.schemas import WorkflowState
from backend.app.db.repositories import SqlRepository, get_repository

_MEMORY_LIMIT = 512


class _Memory:
    """Process-local LRU in front of the database cache (DB round trips are slow from far regions).
    The database stays the source of truth; invalidation always clears both."""

    def __init__(self):
        self._data: OrderedDict[tuple, WorkflowState] = OrderedDict()
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        return None

    def put(self, key, state: WorkflowState) -> None:
        with self._lock:
            self._data[key] = state
            self._data.move_to_end(key)
            while len(self._data) > _MEMORY_LIMIT:
                self._data.popitem(last=False)

    def drop(self, predicate) -> None:
        with self._lock:
            for key in [k for k, v in self._data.items() if predicate(k, v)]:
                del self._data[key]


_memory = _Memory()


class WorkflowCache:
    """Cached workflow results in PostgreSQL (workflow_runs), keyed by workflow + user + profile_version
    (+ exact scheme ids for W3). A new profile version therefore never reuses an old result."""

    def __init__(self, repo: SqlRepository | None = None):
        self.repo = repo or get_repository()

    @staticmethod
    def _key(workflow, user_id, profile_version, scheme_ids):
        return (workflow, user_id, profile_version, tuple(sorted(scheme_ids)) if scheme_ids is not None else None)

    def get(self, workflow: str, user_id: str | None, profile_version: int | None,
            scheme_ids: list[str] | None = None) -> WorkflowState | None:
        if not user_id or profile_version is None:
            return None
        key = self._key(workflow, user_id, profile_version, scheme_ids)
        if (hit := _memory.get(key)) is not None:
            return hit
        state = self.repo.find_run(workflow, user_id, profile_version, scheme_ids)
        if state is not None:
            _memory.put(key, state)
        return state

    def set(self, state: WorkflowState, scheme_ids: list[str] | None = None) -> None:
        if state.workflow == "W2":
            # full Scheme/rule records are reloadable; cache only the result (smaller, faster to read back)
            state = state.model_copy(update={"schemes": {}, "rules": {}})
        self.repo.save_run(state, scheme_ids or [])
        lookup_ids = None if state.workflow == "W2" else (scheme_ids or [])
        _memory.put(self._key(state.workflow, state.user_id, state.profile_version, lookup_ids), state)

    def invalidate_user(self, user_id: str) -> int:
        _memory.drop(lambda k, v: k[1] == user_id)
        return self.repo.invalidate_user_runs(user_id)

    def invalidate_schemes(self, scheme_ids: list[str]) -> list[str]:
        affected = set(scheme_ids)
        _memory.drop(lambda k, v: bool(affected & (set(v.schemes) | set(v.scheme_ids) | set(v.scores))))
        return self.repo.invalidate_scheme_runs(scheme_ids)
