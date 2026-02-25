"""Image serving endpoint for generated product images.

Serves images from persistent storage (DEC-002) with a fallback to the
legacy TempManager directories for backwards compatibility.

Stable URL pattern: /api/images/{job_id}/{path}
  where job_id is the UUID string from the Job record.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.storage import get_storage
from app.services.temp_manager import TempManager

router = APIRouter(prefix="/api/images", tags=["images"])

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


@router.get("/{job_id}/{path:path}")
async def serve_image(job_id: str, path: str) -> FileResponse:
    """Serve a generated image.

    Looks up the file in persistent storage first (new jobs).  Falls back
    to the legacy TempManager directory for old SSE-stream runs.

    Path traversal is blocked by validating the resolved path stays within
    the expected directory.
    """
    storage = get_storage()

    # --- Persistent storage (new async jobs) ---
    storage_path = storage.url_to_path(f"/api/images/{job_id}/{path}")
    if storage_path and storage_path.exists() and storage_path.is_file():
        file_path = storage_path
    else:
        # --- Legacy TempManager fallback ---
        # Old SSE paths were: /api/images/{run_id}/{product_id}/{path}
        # We try to re-derive product_id from the first path component.
        parts = path.split("/", 1)
        if len(parts) == 2:
            product_id, sub_path = parts
        else:
            raise HTTPException(status_code=404, detail="Not found")

        TempManager.purge_expired()
        product_dir = TempManager.get_product_dir(job_id, product_id)
        resolved = (product_dir / sub_path).resolve()

        if not resolved.is_relative_to(product_dir.resolve()):
            raise HTTPException(status_code=404, detail="Not found")
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        file_path = resolved

    # Security: double-check final path is under a known safe root
    safe_roots = [storage._base, Path("/tmp")]
    is_safe = any(
        _is_relative_to_safe(file_path, root) for root in safe_roots
    )
    if not is_safe:
        raise HTTPException(status_code=404, detail="Not found")

    media_type = _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)


def _is_relative_to_safe(path: Path, root: Path) -> bool:
    """Check if path is relative to root without raising exceptions."""
    try:
        path.relative_to(root.resolve())
        return True
    except ValueError:
        return False
