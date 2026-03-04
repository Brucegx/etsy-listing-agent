"""Jobs API — status polling and history for async generation jobs.

Implements:
  GET    /api/jobs/{job_id}      — poll a single job (DEC-003)
  GET    /api/jobs               — list all jobs for authenticated user (DEC-007)
  DELETE /api/jobs/{job_id}      — delete a completed/failed job and its files
  POST   /api/jobs/image-studio  — submit an image_only job (Phase 6A)
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.deps import get_current_user, get_optional_user, rate_limit_user
from app.models.job import Job, JOB_TYPE_IMAGE_ONLY
from app.models.user import User
from app.services.job_service import JobService
from app.services.storage import get_storage
from app.services.temp_manager import TempManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
_job_service = JobService()

# --- Image Studio upload limits ---
_STUDIO_MAX_FILES = 10
_STUDIO_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_STUDIO_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class JobResponse(BaseModel):
    """Public representation of a Job record."""

    job_id: str
    product_id: str
    category: str
    job_type: str = "full_listing"
    status: str
    progress: int
    stage_name: str
    image_urls: list[str] | None
    result: dict | None
    error_message: str | None
    cost_usd: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ImageStudioSubmitResponse(BaseModel):
    """Returned immediately when an Image Studio job is accepted."""

    job_id: str
    status: str = "queued"
    message: str = "Image Studio job queued. Poll GET /api/jobs/{job_id} for status."


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_LISTING_ALLOWED_KEYS = {
    "$schema", "product_id", "generated_at",
    "title", "title_variations", "tags", "long_tail_keywords",
    "description", "attributes",
}


def _safe_result(raw: dict | None) -> dict | None:
    """Strip proprietary prompt/strategy data — only expose listing info."""
    if not raw:
        return raw
    listing = raw.get("listing")
    if not isinstance(listing, dict):
        return None
    return {"listing": {k: v for k, v in listing.items() if k in _LISTING_ALLOWED_KEYS}}


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        product_id=job.product_id,
        category=job.category,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        stage_name=job.stage_name,
        image_urls=job.image_urls,
        result=_safe_result(job.result),
        error_message=job.error_message,
        cost_usd=job.cost_usd,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


# NOTE: /image-studio MUST be defined before /{job_id} so FastAPI does not
# match "image-studio" as a job_id path parameter (→ 405 Method Not Allowed).
@router.post("/image-studio", response_model=ImageStudioSubmitResponse)
async def submit_image_studio(
    images: list[UploadFile] = File(..., description="Product reference images"),
    category: str = Form(
        ...,
        description="Shot category: white_bg | scene | model | detail",
    ),
    count: int = Form(
        default=4,
        ge=1,
        le=8,
        description="Number of image variations to generate (1-8)",
    ),
    aspect_ratio: str = Form(
        default="",
        description="Output aspect ratio: 1:1 | 3:4 | 4:3 (empty = no crop)",
    ),
    additional_prompt: str = Form(
        default="",
        description="Optional extra instructions for the image generator",
    ),
    product_info: str = Form(
        default="",
        description="Free-text product description (optional, supplements image analysis)",
    ),
    current_user: User | None = Depends(get_optional_user),
    _rate_limit: None = Depends(rate_limit_user),
) -> ImageStudioSubmitResponse:
    """Submit an Image Studio job — generates product images without a full listing.

    Accepts uploaded product images, a shot category, and generation config.
    Returns a ``job_id`` immediately.  Poll ``GET /api/jobs/{job_id}`` for status.

    **Category values:**
    - ``white_bg`` — hero shot on white background
    - ``scene`` — lifestyle scene
    - ``model`` — model wearing the product
    - ``detail`` — macro detail close-up
    """
    from app.services.job_worker import run_image_only_job

    # --- Input validation ---
    valid_categories = {"white_bg", "scene", "model", "detail"}
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {', '.join(sorted(valid_categories))}",
        )

    valid_ratios = {"1:1", "3:4", "4:3", ""}
    ar = aspect_ratio.strip()
    if ar not in valid_ratios:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid aspect_ratio '{ar}'. Must be one of: 1:1, 3:4, 4:3 (or empty)",
        )

    if not images:
        raise HTTPException(status_code=400, detail="At least one image is required")
    if len(images) > _STUDIO_MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Maximum {_STUDIO_MAX_FILES} images allowed")
    for img in images:
        if img.content_type and img.content_type not in _STUDIO_ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {img.content_type}")

    image_config = {
        "category": category,
        "count": count,
        "aspect_ratio": ar or None,
        "additional_prompt": additional_prompt.strip(),
    }

    product_id = f"studio_{uuid.uuid4().hex[:8]}"

    # 1. Create DB job record
    db = get_db()
    try:
        job = _job_service.create_job(
            db,
            product_id=product_id,
            user_id=current_user.id if current_user else None,
            job_type=JOB_TYPE_IMAGE_ONLY,
            image_config=image_config,
            product_info=product_info.strip() or None,
        )
        job_id = job.job_id
    finally:
        db.close()

    # 2. Save uploaded images to temp dir
    temp = TempManager()
    product_dir = temp.setup(product_id)
    saved_files: list[str] = []
    try:
        for img in images:
            content = await img.read()
            if len(content) > _STUDIO_MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large: {img.filename} (max 10 MB)",
                )
            filename = (
                os.path.basename(img.filename or f"image_{len(saved_files)}.png")
                or f"image_{len(saved_files)}.png"
            )
            (product_dir / filename).write_bytes(content)
            saved_files.append(filename)
    except HTTPException:
        raise
    except Exception as exc:
        db = get_db()
        try:
            _job_service.mark_failed(db, job_id, error_message="Failed to save uploaded images")
        finally:
            db.close()
        raise HTTPException(status_code=500, detail=f"Failed to save images: {exc}") from exc

    # 3. Queue the image_only job in the background
    asyncio.create_task(
        run_image_only_job(
            job_id=job_id,
            product_id=product_id,
            product_dir=product_dir,
            image_files=saved_files,
            product_info=product_info.strip(),
            image_config=image_config,
            temp=temp,
        )
    )

    return ImageStudioSubmitResponse(job_id=job_id)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> JobResponse:
    """Return the current status of a single job.

    The job must belong to the authenticated user.
    """
    db = get_db()
    try:
        job = _job_service.get_by_job_id(db, job_id)
    finally:
        db.close()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only allow the owning user to see the job
    if job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return _job_to_response(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a completed or failed job",
    description=(
        "Permanently deletes a job record and its stored files. "
        "Only jobs in **completed** or **failed** status may be deleted. "
        "Active jobs are rejected to avoid orphaning in-flight workers."
    ),
)
def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    """Delete a job that belongs to the authenticated user.

    Returns 204 on success.
    Returns 404 if the job does not exist.
    Returns 403 if the job belongs to another user.
    Returns 409 if the job is still in an active (non-terminal) status.
    """
    db = get_db()
    try:
        # Fetch first so we can distinguish 404 vs 403 vs 409.
        job = _job_service.get_by_job_id(db, job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")

        deleted = _job_service.delete_job(db, job_id, current_user.id)
    finally:
        db.close()

    if not deleted:
        # The only remaining reason delete_job returns False at this point is a
        # non-terminal status (ownership and existence were already checked above).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be deleted while it is still running",
        )

    # Best-effort file cleanup — log but do not fail the request if storage is
    # unavailable, since the DB record has already been removed.
    try:
        storage = get_storage()
        storage.delete_job(job_id)
    except Exception:
        logger.exception("Failed to delete storage files for job %s", job_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("", response_model=JobListResponse)
def list_jobs(
    current_user: User = Depends(get_current_user),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> JobListResponse:
    """List all jobs for the authenticated user, newest first.

    Supports pagination via ``page`` and ``page_size`` query parameters.
    """
    db = get_db()
    try:
        jobs, total = _job_service.list_for_user(
            db, current_user.id, page=page, page_size=page_size
        )
    finally:
        db.close()

    total_pages = max(1, (total + page_size - 1) // page_size)
    return JobListResponse(
        jobs=[_job_to_response(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


