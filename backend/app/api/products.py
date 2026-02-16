from fastapi import APIRouter, HTTPException, Request

from app.drive.client import DriveClient
from app.services.product_service import ProductService

router = APIRouter(prefix="/api/products", tags=["products"])

EXCEL_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.spreadsheet",
}

_product_service = ProductService()


def _get_drive_client(request: Request) -> DriveClient:
    """Extract access_token from cookies and return a DriveClient."""
    session = request.cookies.get("session")
    access_token = request.cookies.get("access_token")
    if not session or not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return DriveClient(access_token=access_token)


@router.get("")
async def list_products(
    request: Request,
    folder_id: str,
    excel_file_id: str,
) -> dict:
    """List product IDs from an Excel file in a Drive folder.

    Also detects category from the folder name.
    """
    client = _get_drive_client(request)

    # Download Excel file
    try:
        # Check if it's a Google Sheet (needs export) or native Excel
        files = await client.list_files(folder_id)
        excel_file = next((f for f in files if f["id"] == excel_file_id), None)

        if excel_file and excel_file.get("mimeType") == "application/vnd.google-apps.spreadsheet":
            excel_bytes = await client.download_google_sheet_as_xlsx(excel_file_id)
        else:
            excel_bytes = await client.download_file(excel_file_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to download Excel: {e}")

    # Parse product IDs
    try:
        products = _product_service.list_products_from_bytes(excel_bytes)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse Excel: {e}")

    # Detect category from folder name (last segment, lowercased)
    # e.g. "Products/Rings" → "rings"
    category = ""
    try:
        folders = await client.list_folders()
        folder = next((f for f in folders if f["id"] == folder_id), None)
        if folder:
            category = folder["name"].lower().strip()
    except Exception:
        pass  # Category detection is best-effort

    return {"products": products, "category": category}
