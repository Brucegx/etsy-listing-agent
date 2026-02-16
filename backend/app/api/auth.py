import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.auth.google import exchange_code, get_login_url, get_user_info
from app.config import settings
from app.database import get_db
from app.models.user import User


def _sign_session(google_id: str) -> str:
    """Create HMAC-signed session cookie value."""
    sig = hmac.new(
        settings.session_secret.encode(), google_id.encode(), hashlib.sha256
    ).hexdigest()
    return f"{google_id}:{sig}"


def _verify_session(cookie: str) -> str | None:
    """Verify HMAC signature and return google_id, or None if invalid."""
    if ":" not in cookie:
        return None
    google_id, sig = cookie.rsplit(":", 1)
    expected = hmac.new(
        settings.session_secret.encode(), google_id.encode(), hashlib.sha256
    ).hexdigest()
    if hmac.compare_digest(sig, expected):
        return google_id
    return None

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login() -> RedirectResponse:
    """Redirect to Google OAuth."""
    url = get_login_url()
    return RedirectResponse(url=url, status_code=307)


@router.get("/callback")
async def callback(request: Request, code: str | None = None) -> RedirectResponse:
    """Handle Google OAuth callback: exchange code, upsert user, set cookies."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    tokens = await exchange_code(code)
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")

    user_info = await get_user_info(access_token)

    # Upsert user in DB
    db = get_db()
    try:
        user = db.query(User).filter(User.google_id == user_info["id"]).first()
        if user:
            user.email = user_info.get("email", user.email)
            user.name = user_info.get("name", user.name)
            user.access_token = access_token
            if refresh_token:
                user.refresh_token = refresh_token
        else:
            user = User(
                google_id=user_info["id"],
                email=user_info.get("email", ""),
                name=user_info.get("name", ""),
                access_token=access_token,
                refresh_token=refresh_token,
            )
            db.add(user)
        db.commit()
    finally:
        db.close()

    is_prod = bool(settings.google_client_id)
    redirect = RedirectResponse(url=settings.frontend_url, status_code=302)
    redirect.set_cookie(
        key="session",
        value=_sign_session(user_info["id"]),
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=7 * 24 * 3600,
    )
    redirect.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=3600,  # 1 hour, matches Google token expiry
    )
    return redirect


@router.get("/me")
async def me(request: Request) -> dict:
    """Get current user info from session."""
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    google_id = _verify_session(session)
    if not google_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    db = get_db()
    try:
        user = db.query(User).filter(User.google_id == google_id).first()
    finally:
        db.close()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {"google_id": user.google_id, "email": user.email, "name": user.name}


@router.get("/dev-login")
async def dev_login() -> RedirectResponse:
    """Dev-only: skip Google OAuth, create a fake user and set cookies."""
    if settings.google_client_id:
        raise HTTPException(status_code=404, detail="Not available in production")

    db = get_db()
    try:
        user = db.query(User).filter(User.google_id == "dev_user").first()
        if not user:
            user = User(
                google_id="dev_user",
                email="dev@localhost",
                name="Dev User",
                access_token="dev_token",
            )
            db.add(user)
            db.commit()
    finally:
        db.close()

    redirect = RedirectResponse(url=settings.frontend_url, status_code=302)
    redirect.set_cookie(
        key="session", value=_sign_session("dev_user"), httponly=True, samesite="lax", max_age=7 * 24 * 3600,
    )
    redirect.set_cookie(
        key="access_token", value="dev_token", httponly=True, samesite="lax", max_age=3600,
    )
    return redirect


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Clear session and access_token cookies."""
    redirect = RedirectResponse(url=settings.frontend_url, status_code=302)
    redirect.delete_cookie("session")
    redirect.delete_cookie("access_token")
    return redirect
