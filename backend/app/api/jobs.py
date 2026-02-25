"""Jobs API — status polling and history for async generation jobs.

Implements:
  GET  /api/jobs/{job_id}   — poll a single job (DEC-003)
  GET  /api/jobs            — list all jobs for authenticated user (DEC-007)
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.database import get_db
from app.deps import get_current_user
from app.models.job import Job
from app.models.user import User
from app.services.job_service import JobService

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


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        job_id=job.job_id,
        product_id=job.product_id,
        category=job.category,
        status=job.status,
        progress=job.progress,
        stage_name=job.stage_name,
        image_urls=job.image_urls,
        result=job.result,
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
    if job.user_id is not None and job.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    return _job_to_response(job)


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
