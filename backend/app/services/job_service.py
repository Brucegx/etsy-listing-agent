"""Job service — creates, updates and queries Job records.

Keeps DB operations isolated from the API layer so the logic is
easily testable and reusable.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.job import (
    Job,
    JOB_STATUS_QUEUED,
    JOB_STATUS_STRATEGY,
    JOB_STATUS_GENERATING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
)

logger = logging.getLogger(__name__)


class JobService:
    """CRUD operations and status helpers for Job records."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_job(
        self,
        db: Session,
        product_id: str,
        *,
        user_id: int | None = None,
        category: str = "",
        drive_folder_id: str = "",
    ) -> Job:
        """Create a new Job in QUEUED state and return it."""
        job = Job(
            job_id=uuid.uuid4().hex,
            product_id=product_id,
            user_id=user_id,
            category=category,
            drive_folder_id=drive_folder_id,
            status=JOB_STATUS_QUEUED,
            progress=0,
            stage_name="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info("Created job %s for product %s", job.job_id, product_id)
        return job

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update_status(
        self,
        db: Session,
        job_id: str,
        status: str,
        *,
        progress: int | None = None,
        stage_name: str | None = None,
        error_message: str | None = None,
    ) -> Job | None:
        """Update the status (and optional fields) of a job."""
        job = self.get_by_job_id(db, job_id)
        if not job:
            logger.warning("update_status: job %s not found", job_id)
            return None
        job.status = status
        if progress is not None:
            job.progress = progress
        if stage_name is not None:
            job.stage_name = stage_name
        if error_message is not None:
            job.error_message = error_message
        db.commit()
        db.refresh(job)
        return job

    def mark_strategy(self, db: Session, job_id: str) -> Job | None:
        """Transition job to STRATEGY stage."""
        return self.update_status(
            db,
            job_id,
            JOB_STATUS_STRATEGY,
            progress=10,
            stage_name="building strategy",
        )

    def mark_generating(self, db: Session, job_id: str) -> Job | None:
        """Transition job to GENERATING stage."""
        return self.update_status(
            db,
            job_id,
            JOB_STATUS_GENERATING,
            progress=50,
            stage_name="generating images",
        )

    def mark_completed(
        self,
        db: Session,
        job_id: str,
        *,
        result: dict[str, Any] | None = None,
        image_urls: list[str] | None = None,
    ) -> Job | None:
        """Transition job to COMPLETED and store results."""
        job = self.get_by_job_id(db, job_id)
        if not job:
            return None
        job.status = JOB_STATUS_COMPLETED
        job.progress = 100
        job.stage_name = "completed"
        if result is not None:
            job.result = result
        if image_urls is not None:
            job.image_urls = image_urls
        db.commit()
        db.refresh(job)
        logger.info("Job %s completed with %d images", job_id, len(image_urls or []))
        return job

    def mark_failed(
        self,
        db: Session,
        job_id: str,
        error_message: str,
    ) -> Job | None:
        """Transition job to FAILED and record the error."""
        return self.update_status(
            db,
            job_id,
            JOB_STATUS_FAILED,
            stage_name="failed",
            error_message=error_message,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_job_id(self, db: Session, job_id: str) -> Job | None:
        """Fetch a job by its public job_id UUID string."""
        return db.query(Job).filter(Job.job_id == job_id).first()

    def list_for_user(
        self,
        db: Session,
        user_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Job], int]:
        """Return a page of jobs for a user plus the total count.

        Jobs are ordered newest-first.
        """
        q = db.query(Job).filter(Job.user_id == user_id)
        total = q.count()
        offset = (page - 1) * page_size
        jobs = q.order_by(Job.created_at.desc()).offset(offset).limit(page_size).all()
        return jobs, total
