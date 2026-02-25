"""Public API v1 — generation endpoint.

Authentication: Bearer token (API key).
All routes are under /api/v1/.
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.deps import get_api_key_user
from app.models.api_key import ApiKey
from app.models.user import User
from app.services.temp_manager import TempManager
from app.services.workflow_runner import WorkflowRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["public-api-v1"])

_workflow_runner: WorkflowRunner | None = None

# Upload constraints
_MAX_UPLOAD_FILES = 10
_MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB — supports 8 MB+ as required
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _get_workflow_runner() -> WorkflowRunner:
    """Lazy-init the workflow runner."""
    global _workflow_runner
    if _workflow_runner is None:
        _workflow_runner = WorkflowRunner()
    return _workflow_runner


def _read_result_files(product_dir: Path, product_id: str) -> dict:
    """Read JSON output files produced by the workflow."""
    result: dict = {}

    product_data_path = product_dir / "product_data.json"
    if product_data_path.exists():
        result["product_data"] = json.loads(product_data_path.read_text())

    listing_path = product_dir / f"{product_id}_Listing.json"
    if listing_path.exists():
        result["listing"] = json.loads(listing_path.read_text())

    prompts_path = product_dir / f"{product_id}_NanoBanana_Prompts.json"
    if prompts_path.exists():
        result["prompts"] = json.loads(prompts_path.read_text())

    strategy_path = product_dir / f"{product_id}_image_strategy.json"
    if strategy_path.exists():
        result["strategy"] = json.loads(strategy_path.read_text())

    return result


async def _fire_webhook(callback_url: str, payload: dict) -> None:
    """POST result JSON to the webhook callback URL.

    Attempts up to 3 times with exponential back-off. Errors are logged but
    never propagated — webhook delivery is best-effort.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, 4):
            try:
                resp = await client.post(callback_url, json=payload)
                if resp.is_success:
                    logger.info("Webhook delivered to %s (attempt %d)", callback_url, attempt)
                    return
                logger.warning(
                    "Webhook %s returned %d (attempt %d)",
                    callback_url,
                    resp.status_code,
                    attempt,
                )
            except Exception as exc:
                logger.warning("Webhook delivery failed (attempt %d): %s", attempt, exc)

            if attempt < 3:
                await asyncio.sleep(2**attempt)  # 2s, 4s


# --- Response & request schemas ---


class GenerateJobResponse(BaseModel):
    """Response from POST /api/v1/generate — returns a job_id for polling."""

    job_id: str = Field(description="Unique identifier for this generation job.")
    status: str = Field(default="started", description="Initial job status.")


class JobStatusResponse(BaseModel):
    """Response from GET /api/v1/jobs/{job_id}."""

    job_id: str
    status: str
    results: dict | None = None
    error: str | None = None


# In-process job store (persisted in memory per worker process).
# For production, replace with a DB-backed store.
_jobs: dict[str, dict] = {}


# --- Endpoints ---


@router.post(
    "/generate",
    response_model=GenerateJobResponse,
    status_code=202,
    summary="Submit a generation job",
    description=(
        "Upload product images (multipart/form-data) or provide image URLs, "
        "along with product metadata. Returns a `job_id` for polling. "
        "Optionally supply a `callback_url` to receive a POST when the job completes."
    ),
)
async def public_generate(
    ctx: Annotated[tuple[ApiKey, User], Depends(get_api_key_user)],
    images: list[UploadFile] = File(default=[], description="Product images (multipart upload). Max 10 files, 15 MB each."),
    image_urls: str = Form(default="", description="JSON array of image URLs (alternative to file upload)."),
    material: str = Form(..., description="Product material, e.g. '925 silver'"),
    size: str = Form(default="", description="Product size or dimensions."),
    category: str = Form(default="", description="Product category for the AI workflow."),
    generate_images: bool = Form(default=True, description="Whether to generate AI product images."),
    callback_url: str = Form(default="", description="Optional webhook URL. When job completes, POST result JSON here."),
) -> GenerateJobResponse:
    """Submit a product for listing generation.

    Accepts either file uploads (``images``) or a JSON array of image URLs
    (``image_urls``).  At least one image source is required.
    """
    _, user = ctx

    # Validate inputs
    if not images and not image_urls.strip():
        raise HTTPException(400, "Provide at least one image (file upload or image_urls).")
    if len(images) > _MAX_UPLOAD_FILES:
        raise HTTPException(400, f"Maximum {_MAX_UPLOAD_FILES} images allowed.")

    for img in images:
        if img.content_type and img.content_type not in _ALLOWED_CONTENT_TYPES:
            raise HTTPException(400, f"Unsupported file type: {img.content_type}. Use JPEG, PNG, or WebP.")
        # Read size without consuming the stream
        if img.size is not None and img.size > _MAX_FILE_SIZE:
            raise HTTPException(
                400,
                f"File '{img.filename}' is {img.size // 1024 // 1024:.1f} MB. "
                f"Maximum is {_MAX_FILE_SIZE // 1024 // 1024} MB.",
            )

    # Validate callback_url if provided
    if callback_url.strip():
        if not (callback_url.startswith("http://") or callback_url.startswith("https://")):
            raise HTTPException(400, "callback_url must be an http or https URL.")

    job_id = f"job_{uuid.uuid4().hex}"
    _jobs[job_id] = {"status": "started", "results": None, "error": None}

    asyncio.create_task(
        _run_generation_job(
            job_id=job_id,
            user=user,
            images=images,
            image_urls_json=image_urls,
            material=material,
            size=size,
            category=category,
            generate_images=generate_images,
            callback_url=callback_url.strip() or None,
        )
    )

    return GenerateJobResponse(job_id=job_id, status="started")


async def _run_generation_job(
    job_id: str,
    user: User,
    images: list[UploadFile],
    image_urls_json: str,
    material: str,
    size: str,
    category: str,
    generate_images: bool,
    callback_url: str | None,
) -> None:
    """Background coroutine that runs the LangGraph workflow and updates _jobs."""
    _jobs[job_id]["status"] = "running"
    product_id = f"api_{uuid.uuid4().hex[:8]}"
    temp = TempManager()

    try:
        product_dir = temp.setup(product_id)
        image_files: list[str] = []

        # Save uploaded files
        for img in images:
            content = await img.read()
            # Guard against large files at read time (double-check)
            if len(content) > _MAX_FILE_SIZE:
                raise ValueError(
                    f"File '{img.filename}' exceeds {_MAX_FILE_SIZE // 1024 // 1024} MB limit."
                )
            filename = img.filename or f"image_{len(image_files)}.jpg"
            (product_dir / filename).write_bytes(content)
            image_files.append(filename)

        # Fetch image URLs if provided
        if image_urls_json.strip():
            try:
                urls: list[str] = json.loads(image_urls_json)
            except json.JSONDecodeError:
                raise ValueError("image_urls must be a valid JSON array of strings.")

            async with httpx.AsyncClient(timeout=30.0) as client:
                for i, url in enumerate(urls):
                    resp = await client.get(url, follow_redirects=True)
                    resp.raise_for_status()
                    if len(resp.content) > _MAX_FILE_SIZE:
                        raise ValueError(
                            f"Image at {url} exceeds {_MAX_FILE_SIZE // 1024 // 1024} MB limit."
                        )
                    ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
                    if ext not in ("jpg", "jpeg", "png", "webp"):
                        ext = "jpg"
                    filename = f"url_image_{i}.{ext}"
                    (product_dir / filename).write_bytes(resp.content)
                    image_files.append(filename)

        if not image_files:
            raise ValueError("No images were successfully processed.")

        excel_row = {
            "款号": product_id,
            "材质": material,
            "尺寸": size,
        }

        runner = _get_workflow_runner()
        state = runner.build_state(
            product_id=product_id,
            product_path=str(product_dir),
            category=category,
            excel_row=excel_row,
            image_files=image_files,
            generate_images=generate_images,
            max_retries=5,
        )

        async for _ in runner.run_with_events(state, run_id=temp.run_id):
            pass  # Consume events — results are read from files

        results = _read_result_files(product_dir, product_id)
        _jobs[job_id] = {"status": "completed", "results": results, "error": None}

        if callback_url:
            await _fire_webhook(
                callback_url,
                {"job_id": job_id, "status": "completed", "results": results},
            )

    except Exception as exc:
        logger.exception("Generation job %s failed", job_id)
        error_msg = str(exc)
        _jobs[job_id] = {"status": "failed", "results": None, "error": error_msg}

        if callback_url:
            await _fire_webhook(
                callback_url,
                {"job_id": job_id, "status": "failed", "error": error_msg},
            )
    finally:
        temp.schedule_cleanup(ttl_seconds=3600)


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll job status",
    description="Poll the status of a generation job. Returns results when status is 'completed'.",
)
def get_job_status(
    job_id: str,
    ctx: Annotated[tuple[ApiKey, User], Depends(get_api_key_user)],
) -> JobStatusResponse:
    """Get the current status and results for a generation job."""
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        results=job.get("results"),
        error=job.get("error"),
    )
