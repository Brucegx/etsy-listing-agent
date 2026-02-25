"""FastAPI dependency functions shared across routers."""

import hashlib
import hmac
import time
from collections import defaultdict
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User

# --- Session-cookie auth (web UI) ---


def _verify_session(cookie: str) -> str | None:
    """Verify HMAC-signed session cookie and return google_id, or None."""
    if ":" not in cookie:
        return None
    google_id, sig = cookie.rsplit(":", 1)
    expected = hmac.new(
        settings.session_secret.encode(), google_id.encode(), hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(sig, expected):
        return google_id
    return None


def get_current_user(request: Request) -> User:
    """FastAPI dependency: return the authenticated User or raise 401.

    Reads the 'session' cookie, verifies the HMAC signature, and fetches
    the User from the database.  Raises HTTP 401 on any failure.

    Usage::

        @router.get("/protected")
        def endpoint(user: User = Depends(get_current_user)):
            ...
    """
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    google_id = _verify_session(session)
    if not google_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    db: Session = get_db()
    try:
        user = db.query(User).filter(User.google_id == google_id).first()
    finally:
        db.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


def get_optional_user(request: Request) -> User | None:
    """Like get_current_user but returns None instead of raising 401.

    Useful for endpoints that work both authenticated and unauthenticated.
    """
    try:
        return get_current_user(request)
    except HTTPException:
        return None


# --- API key auth (public API) ---

_bearer_scheme = HTTPBearer(auto_error=False)

# In-memory rate limiter: {key_id: [timestamp, ...]}
_rate_limit_store: dict[int, list[float]] = defaultdict(list)
_rate_limit_lock = Lock()

_DEFAULT_RPM = 60


def _hash_key(raw_key: str) -> str:
    """SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _check_rate_limit(key: ApiKey) -> None:
    """Sliding-window rate limiter. Raises 429 if over limit."""
    rpm = key.rate_limit_rpm if key.rate_limit_rpm > 0 else _DEFAULT_RPM
    now = time.monotonic()
    window_start = now - 60.0

    with _rate_limit_lock:
        timestamps = _rate_limit_store[key.id]
        # Prune old timestamps outside the window
        _rate_limit_store[key.id] = [t for t in timestamps if t >= window_start]
        if len(_rate_limit_store[key.id]) >= rpm:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {rpm} requests per minute.",
                headers={"Retry-After": "60"},
            )
        _rate_limit_store[key.id].append(now)


def get_api_key_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer_scheme)
    ] = None,
) -> tuple[ApiKey, User]:
    """Resolve Bearer token → ApiKey + User.

    Used as a FastAPI dependency for all /api/v1/* routes.
    Raises HTTP 401 for missing/invalid tokens and 403 for revoked keys.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header. Use: Bearer <api-key>",
        )

    raw_key = credentials.credentials
    key_hash = _hash_key(raw_key)

    db = get_db()
    try:
        api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
        if api_key is None:
            raise HTTPException(status_code=401, detail="Invalid API key.")
        if api_key.revoked:
            raise HTTPException(status_code=403, detail="API key has been revoked.")

        _check_rate_limit(api_key)

        # Update last_used_at without loading user eagerly
        from datetime import datetime, timezone

        api_key.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()

        user = db.query(User).filter(User.id == api_key.user_id).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found.")

        # Detach from session so we can return safely after db.close()
        db.expunge(api_key)
        db.expunge(user)
        return api_key, user
    finally:
        db.close()


# Convenience dependency that returns only the User
def get_api_user(
    ctx: Annotated[tuple[ApiKey, User], Depends(get_api_key_user)],
) -> User:
    """Return just the User from the API key context."""
    return ctx[1]
