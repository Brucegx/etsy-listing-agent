"""Job model — tracks async generation requests (DEC-003).

Status lifecycle:
    queued → strategy → batch_submitted → generating → completed
                                                      ↘ failed
"""

from datetime import datetime

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base

# Valid job status values — ordered by lifecycle stage
JOB_STATUS_QUEUED = "queued"
JOB_STATUS_STRATEGY = "strategy"
JOB_STATUS_BATCH_SUBMITTED = "batch_submitted"
JOB_STATUS_GENERATING = "generating"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

VALID_JOB_STATUSES: list[str] = [
    JOB_STATUS_QUEUED,
    JOB_STATUS_STRATEGY,
    JOB_STATUS_BATCH_SUBMITTED,
    JOB_STATUS_GENERATING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
]


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- Ownership ---
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )

    # --- Identity ---
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    product_id: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(50), default="")
    drive_folder_id: Mapped[str] = mapped_column(String(255), default="")

    # --- Status tracking ---
    status: Mapped[str] = mapped_column(
        String(30), default=JOB_STATUS_QUEUED, index=True
    )
    progress: Mapped[int] = mapped_column(Integer, default=0)
    # Human-readable name of the current processing stage
    stage_name: Mapped[str] = mapped_column(String(100), default="")

    # --- Results ---
    # Stable image URLs: list[str]
    image_urls: Mapped[list | None] = mapped_column(JSON, default=None)
    # Full workflow results (listing, prompts, strategy JSON)
    result: Mapped[dict | None] = mapped_column(JSON, default=None)
    # Error message when status == "failed"
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    # --- Cost / metadata ---
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
