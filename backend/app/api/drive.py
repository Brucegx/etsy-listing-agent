import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.auth import _verify_session
from app.auth.google import refresh_access_token
from app.config import settings
from app.database import get_db
from app.drive.client import DriveClient
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drive", tags=["drive"])


async def _get_access_token(request: Request) -> tuple[str, bool]:
    """Get a valid access token, refreshing if needed.

    Returns (access_token, was_refreshed).
    Raises 401 if unable to authenticate.
    """
    session = request.cookies.get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    google_id = _verify_session(session)
    if not google_id:
        raise HTTPException(status_code=401, detail="Invalid session")

    # Try the cookie first
    access_token = request.cookies.get("access_token")
    if access_token:
        return access_token, False

    # Cookie expired — try refreshing from DB
    db = get_db()
    try:
        user = db.query(User).filter(User.google_id == google_id).first()
        if not user or not user.refresh_token:
            raise HTTPException(
                status_code=401,
                detail="Session expired. Please sign in again.",
            )

        tokens = await refresh_access_token(user.refresh_token)
        new_access_token = tokens["access_token"]

        # Update DB
        user.access_token = new_access_token
        db.commit()

        return new_access_token, True
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Token refresh failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please sign in again.",
        )
    finally:
        db.close()


def _set_token_cookie(response: JSONResponse, access_token: str) -> None:
    """Set the refreshed access_token cookie on the response."""
    is_prod = bool(settings.google_client_id)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=3600,
    )


@router.get("/folders")
async def list_folders(
    request: Request, parent_id: str | None = None
) -> JSONResponse:
    """List folders in Google Drive, optionally under a parent."""
    access_token, refreshed = await _get_access_token(request)
    client = DriveClient(access_token=access_token)
    folders = await client.list_folders(parent_id=parent_id)
    resp = JSONResponse(content={"folders": folders})
    if refreshed:
        _set_token_cookie(resp, access_token)
    return resp


@router.get("/files/{folder_id}")
async def list_files(request: Request, folder_id: str) -> JSONResponse:
    """List files in a specific Google Drive folder."""
    access_token, refreshed = await _get_access_token(request)
    client = DriveClient(access_token=access_token)
    files = await client.list_files(folder_id=folder_id)
    resp = JSONResponse(content={"files": files})
    if refreshed:
        _set_token_cookie(resp, access_token)
    return resp
