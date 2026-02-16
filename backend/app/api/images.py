"""Image serving endpoint for generated product images."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.temp_manager import TempManager

router = APIRouter(prefix="/api/images", tags=["images"])

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@router.get("/{run_id}/{product_id}/{path:path}")
async def serve_image(run_id: str, product_id: str, path: str) -> FileResponse:
    """Serve a generated image file from the temp directory.

    The run_id is a short UUID assigned per generation run.
    Path traversal is blocked by validating the resolved path stays
    within the expected temp directory.
    """
    # Purge any expired temp dirs on each request (lazy cleanup)
    TempManager.purge_expired()

    product_dir = TempManager.get_product_dir(run_id, product_id)
    file_path = (product_dir / path).resolve()

    # Security: ensure resolved path is inside the temp dir
    if not file_path.is_relative_to(product_dir.resolve()):
        raise HTTPException(status_code=404, detail="Not found")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Not found")

    media_type = _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)
