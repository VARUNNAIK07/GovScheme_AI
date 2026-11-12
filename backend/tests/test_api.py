"""HTTP API contract tests: FastAPI TestClient + in-memory repository + stub knowledge layer.
No database, no Qdrant, no LLM. The live end-to-end run is done separately against Supabase."""
import uuid

import pytest
from fastapi.testclient import TestClient

from contracts.schemas import Profile, ProfileAttributes
from backend.app.core.security import hash_password
from backend.app.db.repositories import UserRecord


class FakeRepo:
    def __init__(self):
        self.users: dict[str, UserRecord] = {}

    def create_user(self, email, password, name):
        if any(u.email.lower() == email.lower() for u in self.users.values()):
            raise ValueError("Email already registered")
        uid = str(uuid.uuid4())
        u = UserRecord(uid, email, name, hash_password(password),
                       Profile(user_id=uid, version=1, attributes=ProfileAttributes(), complete=False))
        self.users[uid] = u
        return u

    def get_user_by_email(self, email):
        return next((u for u in self.users.values() if u.email.lower() == email.lower()), None)

    def get_user(self, user_id):
        return self.users.get(user_id)

    def save_profile(self, profile):
        self.users[profile.user_id].profile = profile
        return profile


@pytest.fixture
def client(monkeypatch):
    from backend.app.core.config import get_settings
    monkeypatch.setenv("USE_STUBS", "true")
    monkeypatch.setenv("JWT_SECRET", "test-secret-" + "x" * 40)
    get_settings.cache_clear()
    from backend.app.main import create_app
    from backend.app.api.deps import get_repository
    app = create_app()
    repo = FakeRepo()
    app.dependency_overrides[get_repository] = lambda: repo
    yield TestClient(app)
    get_settings.cache_clear()


def _auth(client, email="asha@example.org"):
    r = client.post("/api/auth/register", json={"email": email, "password": "secret-pass-1", "name": "Asha"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_register_login_me(client):
    h = _auth(client)
    assert client.get("/api/me", headers=h).json()["profile_version"] == 1
    dup = client.post("/api/auth/register", json={"email": "ASHA@example.org", "password": "secret-pass-1", "name": "x"})
    assert dup.status_code == 409 and dup.json() == {"error": {"code": "email_taken", "message": "Email already registered"}}
    bad = client.post("/api/auth/login", json={"email": "asha@example.org", "password": "wrong-password"})
    assert bad.status_code == 401 and bad.json()["error"]["code"] == "invalid_credentials"
    assert client.post("/api/auth/login", json={"email": "asha@example.org", "password": "secret-pass-1"}).status_code == 200


def test_auth_required_and_error_shape(client):
    r = client.get("/api/library")
    assert r.status_code == 401 and set(r.json()["error"]) == {"code", "message"}
    r = client.get("/api/library", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_onboarding_validates_and_advances(client):
    h = _auth(client)
    q = client.get("/api/onboarding/next", headers=h).json()
    assert q["done"] is False and q["question"]["field"] == "age"
    bad = client.post("/api/onboarding/answer", headers=h, json={"field": "age", "value": 400}).json()
    assert bad["ok"] is False and bad["errors"]
    ok = client.post("/api/onboarding/answer", headers=h, json={"field": "age", "value": 34}).json()
    assert ok["ok"] is True and ok["question"]["field"] == "gender"
    st = client.post("/api/onboarding/answer", headers=h, json={"field": "state", "value": "Odisha"}).json()
    assert st["ok"] is False                                       # names are not accepted, codes are


def test_library_detail_and_comparison_shapes(client):
    h = _auth(client)
    lib = client.get("/api/library", headers=h)
    assert lib.status_code == 200 and set(lib.json()) == {"profile_version", "top", "more"}
    assert client.get("/api/schemes/pmsby", headers=h).status_code == 200
    assert client.get("/api/schemes/no-such-scheme", headers=h).json()["error"]["code"] == "not_found"
    one = client.post("/api/comparison", headers=h, json={"scheme_ids": ["pmsby"]})
    assert one.status_code == 422 and one.json()["error"]["code"] == "validation_error"


def test_profile_update_bumps_version_and_returns_library(client):
    h = _auth(client)
    r = client.put("/api/profile", headers=h, json={"attributes": {"age": 40, "occupation": "farmer"}}).json()
    assert r["profile"]["version"] == 2 and r["profile"]["attributes"]["occupation"] == "farmer"
    assert "top" in r["library"]


def test_profile_questions_follow_the_draft_and_save_nothing(client):
    h = _auth(client)
    qs = client.post("/api/profile/questions", headers=h, json={"attributes": {"occupation": "farmer"}}).json()
    assert "land_holding_acres" in [q["field"] for q in qs]
    qs = client.post("/api/profile/questions", headers=h, json={"attributes": {"occupation": "student"}}).json()
    assert "land_holding_acres" not in [q["field"] for q in qs]
    assert client.get("/api/me", headers=h).json()["profile_version"] == 1


def test_profile_update_validates_and_prunes(client):
    h = _auth(client)
    bad = client.put("/api/profile", headers=h, json={"attributes": {"state": "Uttar Pradesh"}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    client.put("/api/profile", headers=h, json={"attributes": {"occupation": "farmer", "land_holding_acres": 3}})
    r = client.put("/api/profile", headers=h, json={"attributes": {"occupation": "salaried"}}).json()
    assert r["profile"]["attributes"]["land_holding_acres"] is None


def test_openapi_lists_every_section5_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]
    for p in ["/api/auth/register", "/api/auth/login", "/api/me", "/api/onboarding/next", "/api/onboarding/answer",
              "/api/profile", "/api/library", "/api/schemes/{scheme_id}", "/api/comparison/options", "/api/comparison",
              "/api/citations/{citation_id}", "/api/documents/{doc_id}/file", "/api/admin/refresh", "/api/health"]:
        assert p in paths, p
