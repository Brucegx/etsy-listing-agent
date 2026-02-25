"""FastAPI dependency helpers shared across routers."""

import hashlib
import hmac

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User


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
