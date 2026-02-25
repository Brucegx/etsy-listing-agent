"""API Key management endpoints.

These endpoints are for the web UI (Google OAuth session auth) so users can
generate, list, and revoke their programmatic API keys.
"""

import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.config import settings
from app.database import get_db
from app.models.api_key import ApiKey
from app.models.user import User

router = APIRouter(prefix="/api/keys", tags=["api-keys"])

# --- Session auth helpers (copied from auth.py to avoid circular imports) ---


def _verify_session(cookie: str) -> str | None:
    """Verify HMAC-signed session cookie and return google_id."""
    if ":" not in cookie:
        return None
    google_id, sig = cookie.rsplit(":", 1)
    expected = hmac.new(
        settings.session_secret.encode(), google_id.encode(), hashlib.sha256
    ).hexdigest()
    return google_id if hmac.compare_digest(sig, expected) else None


def _get_current_user_from_session(request: Request) -> User:
    """FastAPI dependency: resolve session cookie → User model."""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    google_id = _verify_session(session)
    if not google_id:
        raise HTTPException(status_code=401, detail="Invalid session.")
    db = get_db()
    try:
        user = db.query(User).filter(User.google_id == google_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found.")
        db.expunge(user)
        return user
    finally:
        db.close()


# --- Pydantic schemas ---


class CreateApiKeyRequest(BaseModel):
    """Request body for generating a new API key."""

    name: str = Field(..., min_length=1, max_length=255, description="Human-readable label for this key")
    rate_limit_rpm: int = Field(
        default=60,
        ge=1,
        le=6000,
        description="Max requests per minute for this key (1–6000)",
    )


class ApiKeyCreatedResponse(BaseModel):
    """Response after creating a new API key.

    The raw key is returned ONCE and never stored. Save it securely.
    """

    id: int
    name: str
    raw_key: str = Field(description="Full API key — shown once, store securely.")
    rate_limit_rpm: int
    created_at: datetime


class ApiKeyListItem(BaseModel):
    """Summary of an API key (without the raw key)."""

    id: int
    name: str
    rate_limit_rpm: int
    revoked: bool
    created_at: datetime
    last_used_at: datetime | None


class ApiKeyListResponse(BaseModel):
    """List of API keys for the current user."""

    keys: list[ApiKeyListItem]


class RevokeApiKeyResponse(BaseModel):
    """Confirmation of key revocation."""

    id: int
    revoked: bool
    message: str


# --- Endpoints ---


@router.post("", response_model=ApiKeyCreatedResponse, status_code=201)
def create_api_key(
    body: CreateApiKeyRequest,
    current_user: Annotated[User, Depends(_get_current_user_from_session)],
) -> ApiKeyCreatedResponse:
    """Generate a new API key for the authenticated user.

    The raw key is returned exactly once. It is not stored — only its SHA-256
    hash is persisted. Store the key securely after creation.
    """
    raw_key = f"eta_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    db = get_db()
    try:
        api_key = ApiKey(
            user_id=current_user.id,
            name=body.name,
            key_hash=key_hash,
            rate_limit_rpm=body.rate_limit_rpm,
        )
        db.add(api_key)
        db.commit()
        db.refresh(api_key)

        return ApiKeyCreatedResponse(
            id=api_key.id,
            name=api_key.name,
            raw_key=raw_key,
            rate_limit_rpm=api_key.rate_limit_rpm,
            created_at=api_key.created_at,
        )
    finally:
        db.close()


@router.get("", response_model=ApiKeyListResponse)
def list_api_keys(
    current_user: Annotated[User, Depends(_get_current_user_from_session)],
) -> ApiKeyListResponse:
    """List all API keys for the current user (does not reveal raw keys)."""
    db = get_db()
    try:
        keys = (
            db.query(ApiKey)
            .filter(ApiKey.user_id == current_user.id)
            .order_by(ApiKey.created_at.desc())
            .all()
        )
        return ApiKeyListResponse(
            keys=[
                ApiKeyListItem(
                    id=k.id,
                    name=k.name,
                    rate_limit_rpm=k.rate_limit_rpm,
                    revoked=k.revoked,
                    created_at=k.created_at,
                    last_used_at=k.last_used_at,
                )
                for k in keys
            ]
        )
    finally:
        db.close()


@router.delete("/{key_id}", response_model=RevokeApiKeyResponse)
def revoke_api_key(
    key_id: int,
    current_user: Annotated[User, Depends(_get_current_user_from_session)],
) -> RevokeApiKeyResponse:
    """Revoke an API key.  Revoked keys are rejected immediately on next use."""
    db = get_db()
    try:
        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id)
            .first()
        )
        if api_key is None:
            raise HTTPException(status_code=404, detail="API key not found.")
        if api_key.revoked:
            raise HTTPException(status_code=409, detail="API key is already revoked.")

        api_key.revoked = True
        db.commit()

        return RevokeApiKeyResponse(
            id=api_key.id,
            revoked=True,
            message=f"API key '{api_key.name}' has been revoked.",
        )
    finally:
        db.close()
