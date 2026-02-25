"""FastAPI dependency functions shared across routers.

Rate-limiting strategy
----------------------
Three distinct limiters, all using a sliding-window algorithm (in-memory):

* API-key limiter   — keyed by ``api_key.id`` (int)
* User limiter      — keyed by ``user.id`` (int), for web-UI sessions
* Anonymous limiter — keyed by client IP, for unauthenticated requests

Limits are configurable via environment variables:

    RATE_LIMIT_API_KEY_RPM=60   (default 60 req/min per API key)
    RATE_LIMIT_USER_RPM=30      (default 30 req/min per logged-in user)
    RATE_LIMIT_ANON_RPM=10      (default 10 req/min per IP)

Every rate-limited response gets two extra headers:

    X-RateLimit-Remaining   Requests left in the current 60-second window
    X-RateLimit-Reset       Unix timestamp when the window resets (UTC)
"""

import hashlib
import hmac
import logging
import math
import os
import time
from collections import defaultdict
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User

logger = logging.getLogger(__name__)

# ── Configurable limits ───────────────────────────────────────────────────────

_DEFAULT_API_KEY_RPM: int = int(os.environ.get("RATE_LIMIT_API_KEY_RPM", "60"))
_DEFAULT_USER_RPM: int = int(os.environ.get("RATE_LIMIT_USER_RPM", "30"))
_DEFAULT_ANON_RPM: int = int(os.environ.get("RATE_LIMIT_ANON_RPM", "10"))

# ── Sliding-window store ──────────────────────────────────────────────────────
# Separate stores for each limiter type to avoid key collisions.
_api_key_store: dict[int, list[float]] = defaultdict(list)
_user_store: dict[int, list[float]] = defaultdict(list)
_anon_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = Lock()

# Backward-compatible alias used by existing tests that import _rate_limit_store
# directly to clear state between test runs.
_rate_limit_store = _api_key_store

_WINDOW_SECONDS = 60.0


# ── Internal sliding-window helper ───────────────────────────────────────────


def _sliding_window_check(
    store: dict,
    key: int | str,
    rpm: int,
    response: Response | None = None,
) -> None:
    """Sliding-window rate limiter (thread-safe via ``_rate_limit_lock``).

    Raises HTTP 429 if the caller has exceeded ``rpm`` requests in the last
    60 seconds.  Attaches ``X-RateLimit-Remaining`` and ``X-RateLimit-Reset``
    headers to ``response`` when provided.

    Args:
        store:    The shared timestamp store (dict keyed by identity).
        key:      Identity for this caller (API key ID, user ID, or IP string).
        rpm:      Maximum requests per 60-second window.
        response: FastAPI ``Response`` object to attach rate-limit headers to.
    """
    now = time.time()
    window_start = now - _WINDOW_SECONDS

    with _rate_limit_lock:
        timestamps = store[key]
        # Prune timestamps that have fallen outside the window
        store[key] = [t for t in timestamps if t >= window_start]
        current_count = len(store[key])

        remaining = max(0, rpm - current_count - 1)  # -1 for this request
        reset_at = math.ceil(now + _WINDOW_SECONDS)  # conservative: full window

        if response is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(reset_at)

        if current_count >= rpm:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "identity": str(key),
                    "rpm_limit": rpm,
                    "current_count": current_count,
                },
            )
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded: {rpm} requests per minute.",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )

        store[key].append(now)


# ── Session-cookie auth (web UI) ──────────────────────────────────────────────


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


# ── Per-user rate limiting (web UI) ───────────────────────────────────────────


def rate_limit_user(
    request: Request,
    response: Response,
    user: User | None = Depends(get_optional_user),
) -> None:
    """FastAPI dependency: apply per-user or per-IP rate limiting.

    Authenticated users are limited by ``RATE_LIMIT_USER_RPM`` (default 30).
    Anonymous requests are limited by ``RATE_LIMIT_ANON_RPM`` (default 10)
    keyed by client IP.

    Attach ``X-RateLimit-Remaining`` / ``X-RateLimit-Reset`` to the response.

    Usage::

        @router.post("/api/generate/upload")
        def endpoint(_: None = Depends(rate_limit_user)):
            ...
    """
    if user is not None:
        _sliding_window_check(_user_store, user.id, _DEFAULT_USER_RPM, response)
        logger.debug(
            "User rate limit checked",
            extra={"user_id": user.id, "rpm_limit": _DEFAULT_USER_RPM},
        )
    else:
        # Fall back to IP-based limiting for anonymous callers
        client_ip = request.client.host if request.client else "unknown"
        _sliding_window_check(_anon_store, client_ip, _DEFAULT_ANON_RPM, response)
        logger.debug(
            "Anonymous rate limit checked",
            extra={"client_ip": client_ip, "rpm_limit": _DEFAULT_ANON_RPM},
        )


# ── API key auth (public API) ─────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


def _hash_key(raw_key: str) -> str:
    """SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def get_api_key_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Security(_bearer_scheme)
    ] = None,
    response: Response = None,  # type: ignore[assignment]
) -> tuple[ApiKey, User]:
    """Resolve Bearer token → ApiKey + User.

    Used as a FastAPI dependency for all /api/v1/* routes.
    Raises HTTP 401 for missing/invalid tokens and 403 for revoked keys.
    Attaches ``X-RateLimit-Remaining`` / ``X-RateLimit-Reset`` headers.
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
            logger.warning("Invalid API key presented", extra={"key_prefix": raw_key[:8]})
            raise HTTPException(status_code=401, detail="Invalid API key.")
        if api_key.revoked:
            logger.warning(
                "Revoked API key used",
                extra={"api_key_id": api_key.id, "user_id": api_key.user_id},
            )
            raise HTTPException(status_code=403, detail="API key has been revoked.")

        # Per-key rate limit with configurable RPM
        rpm = api_key.rate_limit_rpm if api_key.rate_limit_rpm > 0 else _DEFAULT_API_KEY_RPM
        _sliding_window_check(_api_key_store, api_key.id, rpm, response)

        logger.debug(
            "API key authenticated",
            extra={"api_key_id": api_key.id, "user_id": api_key.user_id},
        )

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
