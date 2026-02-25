"""Background job worker — runs the LangGraph workflow for a submitted job.

The worker is invoked via asyncio.create_task() in the generate endpoint.
It updates job status in the DB as it progresses, and writes generated images
directly into persistent storage (DEC-002 / DEC-003 / DEC-006).

Image generation flow (DEC-006):
    1. LangGraph runs strategy → prompts nodes.
    2. Worker picks up the NanoBanana prompts JSON from the product directory.
    3. ``submit_image_batch`` submits all 10 prompts to Gemini Batch API.
    4. Job status advances to ``batch_submitted`` with the batch job name stored.
    5. Worker polls Gemini until the batch completes (async, non-blocking loop).
    6. ``collect_batch_images`` saves images directly to persistent storage.
    7. Job status advances to ``completed`` with stable image URLs.
"""

import json
import logging
from pathlib import Path
from typing import Any

from app.database import get_db
from app.models.job import JOB_STATUS_BATCH_SUBMITTED
from app.models.user import User
from app.services.email_service import get_email_service
from app.services.job_service import JobService
from app.services.storage import get_storage
from app.services.temp_manager import TempManager
from app.services.workflow_runner import WorkflowRunner

logger = logging.getLogger(__name__)

_job_service = JobService()
_workflow_runner: WorkflowRunner | None = None


def _get_workflow_runner() -> WorkflowRunner:
    """Lazy-init the workflow runner (avoids import-time LangGraph compilation)."""
    global _workflow_runner
    if _workflow_runner is None:
        _workflow_runner = WorkflowRunner()
    return _workflow_runner


def _read_result_files(product_dir: Path, product_id: str) -> dict[str, Any]:
    """Read the output JSON files produced by the workflow."""
    result: dict[str, Any] = {}

    for filename, key in [
        ("product_data.json", "product_data"),
        (f"{product_id}_Listing.json", "listing"),
        (f"{product_id}_NanoBanana_Prompts.json", "prompts"),
        (f"{product_id}_image_strategy.json", "strategy"),
    ]:
        path = product_dir / filename
        if path.exists():
            try:
                result[key] = json.loads(path.read_text())
            except Exception:
                logger.warning("Could not parse result file %s", path)
    return result


def _collect_image_paths(product_dir: Path) -> list[Path]:
    """Collect generated image files from the product dir tree."""
    image_extensions = {".png", ".jpg", ".jpeg", ".webp"}
    images: list[Path] = []
    for f in product_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in image_extensions:
            images.append(f)
    return images


async def _run_batch_image_generation(
    job_id: str,
    product_dir: Path,
    product_id: str,
    resolution: str = "1k",
    api_key: str | None = None,
    poll_interval: float = 30.0,
) -> list[str]:
    """Submit all prompts to Gemini Batch API, poll, and store images.

    Images are written directly to persistent storage (no intermediate /tmp
    directory — satisfies DEC-002: no ephemeral /tmp usage).

    Args:
        job_id: The job UUID string (used as the storage namespace).
        product_dir: Directory containing the NanoBanana prompts JSON and
                     reference images.
        product_id: Product identifier (e.g. "R001").
        resolution: Image resolution — "1k", "2k", or "4k".
        api_key: Gemini API key.
        poll_interval: Seconds between batch status polls.

    Returns:
        List of stable image URL paths (e.g. ``["/api/images/{job_id}/..."``]).
    """
    import asyncio
    import functools

    from etsy_listing_agent.image_generator import (
        parse_nanobanana_json,
        submit_image_batch,
        poll_batch_until_done,
        collect_batch_images,
    )

    prompts_file = product_dir / f"{product_id}_NanoBanana_Prompts.json"
    if not prompts_file.exists():
        logger.warning("Prompts file not found: %s — skipping image generation", prompts_file)
        return []

    entries = parse_nanobanana_json(prompts_file)
    if not entries:
        logger.warning("No prompt entries found for %s", product_id)
        return []

    # Determine the output dir — write directly to persistent storage job dir
    # so we never touch /tmp after the workflow stage.
    storage = get_storage()
    storage_job_dir = storage.job_dir(job_id)
    output_dir = storage_job_dir / f"generated_{resolution}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- Submit batch ---
    logger.info("Submitting batch for job %s (%d images)", job_id, len(entries))
    batch_name = submit_image_batch(
        entries=entries,
        product_dir=product_dir,
        resolution=resolution,
        api_key=api_key,
        display_name=f"etsy-agent-{product_id}-{job_id[:8]}",
    )

    # Transition job to batch_submitted — store batch_name in stage_name
    db = get_db()
    try:
        _job_service.update_status(
            db,
            job_id,
            status=JOB_STATUS_BATCH_SUBMITTED,
            progress=60,
            stage_name=f"batch_submitted:{batch_name}",
        )
    finally:
        db.close()

    # --- Poll in thread pool (non-blocking) ---
    loop = asyncio.get_event_loop()
    batch_job = await loop.run_in_executor(
        None,
        functools.partial(
            poll_batch_until_done,
            batch_name,
            api_key=api_key,
            poll_interval=poll_interval,
        ),
    )

    # --- Collect and save images directly to persistent storage ---
    collect_results = collect_batch_images(
        batch_job=batch_job,
        entries=entries,
        output_dir=output_dir,
        product_id=product_id,
        resolution=resolution,
    )

    # Build stable URL paths from the files we wrote
    image_urls: list[str] = []
    for item in collect_results.get("generated", []):
        img_path = Path(item["path"])
        try:
            rel = img_path.relative_to(storage_job_dir)
        except ValueError:
            rel = Path(img_path.name)
        url = f"/api/images/{job_id}/{str(rel).replace(chr(92), '/')}"
        image_urls.append(url)

    logger.info(
        "Batch complete for job %s — %d generated, %d failed",
        job_id,
        len(collect_results.get("generated", [])),
        len(collect_results.get("failed", [])),
    )
    return image_urls


async def run_job(
    job_id: str,
    product_id: str,
    product_dir: Path,
    excel_row: dict[str, Any],
    image_files: list[str],
    category: str = "",
    generate_images: bool = True,
    max_retries: int = 3,
    temp: TempManager | None = None,
    resolution: str = "1k",
    batch_poll_interval: float = 30.0,
) -> None:
    """Execute the LangGraph workflow for a job in the background.

    Updates job status at each lifecycle stage and persists results and
    images into the storage service.  Any exception marks the job failed.

    Image generation (when ``generate_images=True``) uses the Gemini Batch
    API (DEC-006).  Images are written directly to persistent storage; the
    workflow's /tmp product_dir is only used for the strategy/prompts stage.

    Args:
        job_id: The public UUID string for the job.
        product_id: Product identifier string.
        product_dir: Temp directory where input/output files live.
        excel_row: Parsed Excel row dict for the product.
        image_files: List of input image filenames (relative to product_dir).
        category: Product category (may be empty for AI inference).
        generate_images: Whether to run the image generation step.
        max_retries: Max workflow retries.
        temp: TempManager owning product_dir (for cleanup scheduling).
        resolution: Image resolution ("1k", "2k", "4k").
        batch_poll_interval: Seconds between Gemini batch status polls.
    """
    import os

    api_key = os.environ.get("GEMINI_API_KEY") or None

    db = get_db()
    try:
        # ----- STRATEGY stage -----
        _job_service.mark_strategy(db, job_id)

        runner = _get_workflow_runner()
        state = runner.build_state(
            product_id=product_id,
            product_path=str(product_dir),
            category=category,
            excel_row=excel_row,
            image_files=image_files,
            # Always False here — we run image gen separately via Batch API
            generate_images=False,
            max_retries=max_retries,
        )

        # ----- Run LangGraph (strategy + prompts only) -----
        node_order = ["preprocess", "strategy", "prompt_aggregator", "listing"]
        completed_nodes: set[str] = set()

        async for event in runner.run_with_events(state, run_id=job_id):
            event_name = event.get("event", "")
            data = event.get("data", {})

            node = data.get("node", "")
            if node and node not in completed_nodes:
                completed_nodes.add(node)
                progress = min(55, 10 + int(len(completed_nodes) / max(len(node_order), 1) * 45))
                _job_service.update_status(
                    db,
                    job_id,
                    status="strategy",
                    progress=progress,
                    stage_name=node,
                )

            if event_name == "strategy_complete":
                _job_service.mark_generating(db, job_id)

            if event_name == "error":
                raise RuntimeError(data.get("message", "Workflow error"))

        # ----- Store non-image results (listing, strategy JSON, etc.) -----
        storage = get_storage()
        result = _read_result_files(product_dir, product_id)

        # Copy any input product images (reference photos) to persistent storage
        input_image_urls: list[str] = []
        for fname in image_files:
            src = product_dir / fname
            if src.exists():
                url = storage.copy_file(job_id, src)
                input_image_urls.append(url)

        # ----- IMAGE GENERATION via Gemini Batch API -----
        image_urls: list[str] = []
        if generate_images:
            image_urls = await _run_batch_image_generation(
                job_id=job_id,
                product_dir=product_dir,
                product_id=product_id,
                resolution=resolution,
                api_key=api_key,
                poll_interval=batch_poll_interval,
            )

        _job_service.mark_completed(db, job_id, result=result, image_urls=image_urls)
        logger.info("Job %s finished — %d images stored", job_id, len(image_urls))

        # --- Send completion email (DEC-007) ---
        await _notify_job_completed(db, job_id, product_id, image_count=len(image_urls))

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        try:
            _job_service.mark_failed(db, job_id, error_message=str(exc))
        except Exception:
            logger.exception("Could not mark job %s as failed", job_id)
        # --- Send failure email (best-effort) ---
        try:
            await _notify_job_failed(db, job_id, product_id, error_message=str(exc))
        except Exception:
            logger.exception("Could not send failure email for job %s", job_id)
    finally:
        db.close()
        if temp is not None:
            # Keep input files briefly for debugging, then clean up
            temp.schedule_cleanup(ttl_seconds=3600)


# ---------------------------------------------------------------------------
# Email notification helpers (DEC-007)
# ---------------------------------------------------------------------------


async def _get_job_user(db: Any, job_id: str) -> User | None:
    """Fetch the User record owning a job, or None if not found."""
    job = _job_service.get_by_job_id(db, job_id)
    if job is None or job.user_id is None:
        return None
    return db.query(User).filter(User.id == job.user_id).first()


async def _notify_job_completed(
    db: Any,
    job_id: str,
    product_id: str,
    image_count: int,
) -> None:
    """Send a job-completed email to the job owner (best-effort, never raises)."""
    try:
        user = await _get_job_user(db, job_id)
        if user is None:
            logger.debug("No user for job %s — skipping completion email", job_id)
            return

        email_svc = get_email_service()
        await email_svc.send_job_completed(
            to_email=user.email,
            user_name=user.name,
            job_id=job_id,
            product_id=product_id,
            image_count=image_count,
        )
    except Exception:
        logger.exception("Error sending completion email for job %s", job_id)


async def _notify_job_failed(
    db: Any,
    job_id: str,
    product_id: str,
    error_message: str,
) -> None:
    """Send a job-failed email to the job owner (best-effort, never raises)."""
    try:
        user = await _get_job_user(db, job_id)
        if user is None:
            logger.debug("No user for job %s — skipping failure email", job_id)
            return

        email_svc = get_email_service()
        await email_svc.send_job_failed(
            to_email=user.email,
            user_name=user.name,
            job_id=job_id,
            product_id=product_id,
            error_message=error_message,
        )
    except Exception:
        logger.exception("Error sending failure email for job %s", job_id)
