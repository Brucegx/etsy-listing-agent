from fastapi import APIRouter, HTTPException, Request

from app.drive.client import DriveClient

router = APIRouter(prefix="/api/drive", tags=["drive"])


def _get_drive_client(request: Request) -> DriveClient:
    """Extract access_token from cookies and return a DriveClient.

    Raises 401 if user is not authenticated (missing session or access_token).
    """
    session = request.cookies.get("session")
    access_token = request.cookies.get("access_token")
    if not session or not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return DriveClient(access_token=access_token)


@router.get("/folders")
async def list_folders(
    request: Request, parent_id: str | None = None
) -> dict:
    """List folders in Google Drive, optionally under a parent."""
    client = _get_drive_client(request)
    folders = await client.list_folders(parent_id=parent_id)
    return {"folders": folders}


@router.get("/files/{folder_id}")
async def list_files(request: Request, folder_id: str) -> dict:
    """List files in a specific Google Drive folder."""
    client = _get_drive_client(request)
    files = await client.list_files(folder_id=folder_id)
    return {"files": files}
