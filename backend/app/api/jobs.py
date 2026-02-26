"""Jobs API — status polling and history for async generation jobs.

Implements:
  GET    /api/jobs/{job_id}   — poll a single job (DEC-003)
  GET    /api/jobs            — list all jobs for authenticated user (DEC-007)
  DELETE /api/jobs/{job_id}   — delete a completed/failed job and its files
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.database import get_db
from app.deps import get_current_user
from app.models.job import Job
from app.models.user import User
from app.services.job_service import JobService
from app.services.storage import get_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
_job_service = JobService()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class JobResponse(BaseModel):
    """Public representation of a Job record."""

    job_id: str
    product_id: str
    category: str
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
