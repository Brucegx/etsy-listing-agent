"""Integration tests for API key management endpoints.

Tests: POST /api/keys, GET /api/keys, DELETE /api/keys/{key_id}
Auth: Google OAuth session cookie (web UI flow).
"""

import hashlib
import hmac
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base
from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SESSION_SECRET = "test-secret-for-keys"


def _sign_session(google_id: str, secret: str = _SESSION_SECRET) -> str:
    sig = hmac.new(secret.encode(), google_id.encode(), hashlib.sha256).hexdigest()
    return f"{google_id}:{sig}"


def _make_test_session() -> sessionmaker:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _create_user(session_factory: sessionmaker, google_id: str = "test_user_1") -> User:
    """Insert a test user and return it (with id populated)."""
    db = session_factory()
    try:
        user = User(
            google_id=google_id,
            email=f"{google_id}@test.com",
            name="Test User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        # Build a plain dict so we can use after db.close()
        return user
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_user():
    """Return (TestClient, session_factory, user) with patched DB and settings."""
    session_factory = _make_test_session()
    user = _create_user(session_factory)

    with (
        patch("app.api.keys.get_db", side_effect=session_factory),
        patch("app.api.keys.settings") as mock_settings,
    ):
        mock_settings.session_secret = _SESSION_SECRET
        tc = TestClient(app, raise_server_exceptions=True)
        yield tc, session_factory, user


# ---------------------------------------------------------------------------
# POST /api/keys — create
# ---------------------------------------------------------------------------


class TestCreateApiKey:
    def test_create_returns_raw_key(self, client_with_user):
        client, session_factory, user = client_with_user
        session_cookie = _sign_session(user.google_id)

        client.cookies.set("session", session_cookie)
        resp = client.post(
            "/api/keys",
            json={"name": "My Key", "rate_limit_rpm": 30},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["name"] == "My Key"
        assert data["rate_limit_rpm"] == 30
        assert data["raw_key"].startswith("eta_")
        assert "id" in data
        assert "created_at" in data

    def test_create_requires_auth(self):
        """No session cookie → 401."""
        tc = TestClient(app)
        resp = tc.post("/api/keys", json={"name": "Key"})
        assert resp.status_code == 401

    def test_create_missing_name_is_rejected(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))
        resp = client.post("/api/keys", json={"name": "", "rate_limit_rpm": 10})
        assert resp.status_code == 422  # Pydantic min_length validation

    def test_create_rate_limit_bounds(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))
        # rpm = 0 is below minimum
        resp = client.post("/api/keys", json={"name": "Low", "rate_limit_rpm": 0})
        assert resp.status_code == 422
        # rpm = 7000 is above maximum
        resp = client.post("/api/keys", json={"name": "High", "rate_limit_rpm": 7000})
        assert resp.status_code == 422

    def test_raw_key_not_stored_in_db(self, client_with_user):
        """Only the hash is stored — not the raw key."""
        client, session_factory, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))
        resp = client.post("/api/keys", json={"name": "Hashed"})
        assert resp.status_code == 201
        raw_key = resp.json()["raw_key"]

        db = session_factory()
        try:
            from app.models.api_key import ApiKey

            stored = db.query(ApiKey).first()
            assert stored is not None
            assert stored.key_hash != raw_key  # hash, not raw
            expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            assert stored.key_hash == expected_hash
        finally:
            db.close()


# ---------------------------------------------------------------------------
# GET /api/keys — list
# ---------------------------------------------------------------------------


class TestListApiKeys:
    def test_list_empty(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))
        resp = client.get("/api/keys")
        assert resp.status_code == 200
        assert resp.json()["keys"] == []

    def test_list_shows_created_keys(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))

        client.post("/api/keys", json={"name": "Key A"})
        client.post("/api/keys", json={"name": "Key B"})

        resp = client.get("/api/keys")
        assert resp.status_code == 200
        keys = resp.json()["keys"]
        assert len(keys) == 2
        names = {k["name"] for k in keys}
        assert names == {"Key A", "Key B"}

    def test_list_does_not_expose_raw_key(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))
        client.post("/api/keys", json={"name": "Secret"})

        resp = client.get("/api/keys")
        keys = resp.json()["keys"]
        assert len(keys) == 1
        assert "raw_key" not in keys[0]
        assert "key_hash" not in keys[0]

    def test_list_requires_auth(self):
        tc = TestClient(app)
        resp = tc.get("/api/keys")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /api/keys/{key_id} — revoke
# ---------------------------------------------------------------------------


class TestRevokeApiKey:
    def test_revoke_key(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))

        create_resp = client.post("/api/keys", json={"name": "ToRevoke"})
        key_id = create_resp.json()["id"]

        del_resp = client.delete(f"/api/keys/{key_id}")
        assert del_resp.status_code == 200
        data = del_resp.json()
        assert data["revoked"] is True
        assert data["id"] == key_id

    def test_revoke_marks_key_revoked_in_list(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))

        create_resp = client.post("/api/keys", json={"name": "WillRevoke"})
        key_id = create_resp.json()["id"]
        client.delete(f"/api/keys/{key_id}")

        list_resp = client.get("/api/keys")
        keys = list_resp.json()["keys"]
        assert len(keys) == 1
        assert keys[0]["revoked"] is True

    def test_revoke_nonexistent_key_returns_404(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))
        resp = client.delete("/api/keys/99999")
        assert resp.status_code == 404

    def test_revoke_another_users_key_returns_404(self, client_with_user):
        """A user cannot revoke another user's key."""
        client, session_factory, user = client_with_user
        # Create a second user and their key
        second_session = _make_test_session()
        second_user = _create_user(session_factory, google_id="other_user")

        client.cookies.set("session", _sign_session(second_user.google_id))
        create_resp = client.post("/api/keys", json={"name": "OtherKey"})
        key_id = create_resp.json()["id"]

        # Switch to first user and try to revoke
        client.cookies.set("session", _sign_session(user.google_id))
        resp = client.delete(f"/api/keys/{key_id}")
        assert resp.status_code == 404

    def test_double_revoke_returns_409(self, client_with_user):
        client, _, user = client_with_user
        client.cookies.set("session", _sign_session(user.google_id))

        create_resp = client.post("/api/keys", json={"name": "DoubleRevoke"})
        key_id = create_resp.json()["id"]
        client.delete(f"/api/keys/{key_id}")

        resp = client.delete(f"/api/keys/{key_id}")
        assert resp.status_code == 409

    def test_revoke_requires_auth(self):
        tc = TestClient(app)
        resp = tc.delete("/api/keys/1")
        assert resp.status_code == 401
