from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import _sign_session
from app.main import app
from app.models import Base
from app.models.user import User

client = TestClient(app)


def _make_test_db():
    """Create a shared in-memory DB and return a session factory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_google_login_redirects():
    """GET /api/auth/login should redirect to Google OAuth."""
    response = client.get("/api/auth/login", follow_redirects=False)
    assert response.status_code == 307
    assert "accounts.google.com" in response.headers["location"]


def test_auth_callback_without_code():
    """GET /api/auth/callback without code should return 400."""
    response = client.get("/api/auth/callback")
    assert response.status_code == 400


def test_auth_me_without_session():
    """GET /api/auth/me without session should return 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401


@patch("app.api.auth.get_user_info", new_callable=AsyncMock)
@patch("app.api.auth.exchange_code", new_callable=AsyncMock)
@patch("app.api.auth.get_db")
def test_auth_callback_sets_cookies_and_upserts_user(mock_get_db, mock_exchange, mock_userinfo):
    """Callback should set session + access_token cookies and upsert user in DB."""
    SessionLocal = _make_test_db()
    mock_get_db.return_value = SessionLocal()

    mock_exchange.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
    }
    mock_userinfo.return_value = {
        "id": "google_123",
        "email": "test@example.com",
        "name": "Test User",
    }

    response = client.get("/api/auth/callback?code=test_code", follow_redirects=False)

    assert response.status_code == 302
    cookies = {c.name: c.value for c in response.cookies.jar}
    assert "session" in cookies
    assert cookies["session"].startswith("google_123:")
    assert "access_token" in cookies
    assert cookies["access_token"] == "test_access_token"

    # Verify user was created in DB (same shared connection via StaticPool)
    verify = SessionLocal()
    user = verify.query(User).filter(User.google_id == "google_123").first()
    assert user is not None
    assert user.email == "test@example.com"
    assert user.name == "Test User"
    assert user.access_token == "test_access_token"
    assert user.refresh_token == "test_refresh_token"
    verify.close()


@patch("app.api.auth.get_user_info", new_callable=AsyncMock)
@patch("app.api.auth.exchange_code", new_callable=AsyncMock)
@patch("app.api.auth.get_db")
def test_auth_callback_updates_existing_user(mock_get_db, mock_exchange, mock_userinfo):
    """Callback should update existing user's tokens on re-login."""
    SessionLocal = _make_test_db()

    # Pre-create user
    setup = SessionLocal()
    setup.add(User(
        google_id="google_123",
        email="old@example.com",
        name="Old Name",
        access_token="old_token",
    ))
    setup.commit()
    setup.close()

    mock_get_db.return_value = SessionLocal()
    mock_exchange.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
    }
    mock_userinfo.return_value = {
        "id": "google_123",
        "email": "new@example.com",
        "name": "New Name",
    }

    response = client.get("/api/auth/callback?code=test_code", follow_redirects=False)
    assert response.status_code == 302

    verify = SessionLocal()
    user = verify.query(User).filter(User.google_id == "google_123").first()
    assert user.email == "new@example.com"
    assert user.name == "New Name"
    assert user.access_token == "new_access_token"
    assert user.refresh_token == "new_refresh_token"
    verify.close()


@patch("app.api.auth.get_db")
def test_auth_me_returns_user_info(mock_get_db):
    """GET /api/auth/me with valid session should return user info."""
    SessionLocal = _make_test_db()

    setup = SessionLocal()
    setup.add(User(
        google_id="google_123",
        email="test@example.com",
        name="Test User",
        access_token="token",
    ))
    setup.commit()
    setup.close()

    mock_get_db.return_value = SessionLocal()

    response = client.get("/api/auth/me", cookies={"session": _sign_session("google_123")})
    assert response.status_code == 200
    data = response.json()
    assert data["google_id"] == "google_123"
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"


def test_logout_clears_cookies():
    """POST /api/auth/logout should clear both cookies."""
    response = client.post(
        "/api/auth/logout",
        cookies={"session": "google_123", "access_token": "test_token"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    set_cookies = response.headers.get_list("set-cookie")
    cookie_names = [c.split("=")[0] for c in set_cookies]
    assert "session" in cookie_names
    assert "access_token" in cookie_names
