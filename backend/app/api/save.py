import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.drive.client import DriveClient

router = APIRouter(prefix="/api/save", tags=["save"])


class SaveRequest(BaseModel):
    """Request to save generated results back to Google Drive."""

    drive_folder_id: str
    product_id: str
    listing: dict | None = None
    prompts: dict | None = None
    product_data: dict | None = None


def _get_drive_client(request: Request) -> DriveClient:
    """Extract access_token from cookies and return a DriveClient."""
    session = request.cookies.get("session")
    access_token = request.cookies.get("access_token")
    if not session or not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return DriveClient(access_token=access_token)


@router.post("")
async def save_results(request: Request, body: SaveRequest) -> dict:
    """Save generated listing/prompts/product_data to Drive folder."""
    client = _get_drive_client(request)

    uploaded: list[dict] = []

    if body.listing:
        result = await client.upload_file(
            name=f"{body.product_id}_Listing.json",
            content=json.dumps(body.listing, indent=2, ensure_ascii=False).encode(),
            folder_id=body.drive_folder_id,
        )
        uploaded.append({"type": "listing", **result})

    if body.prompts:
        result = await client.upload_file(
            name=f"{body.product_id}_NanoBanana_Prompts.json",
            content=json.dumps(body.prompts, indent=2, ensure_ascii=False).encode(),
            folder_id=body.drive_folder_id,
        )
        uploaded.append({"type": "prompts", **result})

    if body.product_data:
        result = await client.upload_file(
            name="product_data.json",
            content=json.dumps(body.product_data, indent=2, ensure_ascii=False).encode(),
            folder_id=body.drive_folder_id,
        )
        uploaded.append({"type": "product_data", **result})

    return {"status": "ok", "uploaded": uploaded}
