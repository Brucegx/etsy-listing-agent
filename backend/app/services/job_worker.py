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

import io
import json
import logging
from pathlib import Path
from typing import Any

from app.database import get_db
from app.models.user import User
from app.services.email_service import get_email_service
from app.services.job_service import JobService
from app.services.storage import get_storage
from app.services.temp_manager import TempManager
from app.services.workflow_runner import WorkflowRunner

logger = logging.getLogger(__name__)

_job_service = JobService()
_workflow_runner: WorkflowRunner | None = None

# Claude API hard limit (5 MB). We target 4 MB to leave a safe margin.
_CLAUDE_IMAGE_SIZE_LIMIT = 5 * 1024 * 1024  # 5 MB
_CLAUDE_IMAGE_TARGET = 4 * 1024 * 1024      # 4 MB target after compression

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _compress_image_for_claude(image_path: Path) -> None:
    """Resize and/or compress an image file in-place so it fits within Claude's
    5 MB per-image limit.

    Strategy:
    1. Skip files already under the target size (no-op, fast path).
    2. Convert PNG/WebP → JPEG (lossless → lossy is acceptable for analysis).
    3. Iteratively reduce JPEG quality (85 → 75 → 60) until the file is small
       enough.  If quality reduction alone is insufficient, halve the dimensions
       and repeat.

    Only JPEG, PNG, and WebP images are processed.  Other file types are left
    untouched.

    Args:
        image_path: Path to the image file on disk.  Modified in place when
                    compression is applied.
    """
    from PIL import Image  # noqa: PLC0415 — imported here to keep module load light

    if image_path.suffix.lower() not in _IMAGE_EXTENSIONS:
        return

    size = image_path.stat().st_size
    if size <= _CLAUDE_IMAGE_TARGET:
        return  # Fast path — already small enough

    logger.info(
        "Compressing image %s: %.2f MB → target %.2f MB",
        image_path.name,
        size / 1024 / 1024,
        _CLAUDE_IMAGE_TARGET / 1024 / 1024,
    )

    img = Image.open(image_path)
    # Convert palette/transparency modes to RGB for JPEG compatibility
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Save as JPEG — try progressively lower quality levels first
    for quality in (85, 75, 60, 45):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= _CLAUDE_IMAGE_TARGET:
            # Write compressed bytes back to disk (rename to .jpg if needed)
            new_path = image_path.with_suffix(".jpg")
            new_path.write_bytes(buf.getvalue())
            if new_path != image_path:
                image_path.unlink()
            logger.info(
                "Compressed %s to %.2f MB (quality=%d)",
                image_path.name,
                buf.tell() / 1024 / 1024,
                quality,
            )
            return

    # Quality reduction alone wasn't enough — halve the dimensions and retry
    width, height = img.size
    scale = 0.5
    while scale >= 0.125:  # Stop at 12.5% of original size
        new_w = max(1, int(width * scale))
        new_h = max(1, int(height * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=75, optimize=True)
        if buf.tell() <= _CLAUDE_IMAGE_TARGET:
            new_path = image_path.with_suffix(".jpg")
            new_path.write_bytes(buf.getvalue())
            if new_path != image_path:
                image_path.unlink()
            logger.info(
                "Compressed %s to %.2f MB (scale=%.2f, quality=75)",
                image_path.name,
                buf.tell() / 1024 / 1024,
                scale,
            )
            return
        scale *= 0.5

    # Last-resort: overwrite at lowest quality / smallest size
    buf = io.BytesIO()
    img.resize((max(1, width // 8), max(1, height // 8)), Image.LANCZOS).save(
        buf, format="JPEG", quality=40, optimize=True
    )
    new_path = image_path.with_suffix(".jpg")
    new_path.write_bytes(buf.getvalue())
    if new_path != image_path:
        image_path.unlink()
    logger.warning(
        "Could not reach target size for %s; last-resort compressed to %.2f MB",
        image_path.name,
        buf.tell() / 1024 / 1024,
    )


def _compress_product_images(
    product_dir: Path, image_files: list[str]
) -> list[str]:
    """Compress all product images in product_dir to fit within Claude's 5 MB limit.

    Returns an updated list of image filenames, reflecting any .jpg renames
    that happened when PNG/WebP files were converted.

    Args:
        product_dir: Directory where the image files live.
        image_files: List of image filenames (relative to product_dir).

    Returns:
        Updated list of filenames (same order, possibly different extensions).
    """
    updated: list[str] = []
    for fname in image_files:
        original_path = product_dir / fname
        if not original_path.exists():
            updated.append(fname)
            continue

        _compress_image_for_claude(original_path)

        # If the extension changed (e.g. .png → .jpg), update the filename
        new_path = original_path.with_suffix(".jpg")
        if not original_path.exists() and new_path.exists():
            updated.append(new_path.name)
        else:
            updated.append(fname)
    return updated


def _friendly_error_message(exc: Exception) -> str:
    """Convert a raw exception into a user-friendly error message.

    Raw API error dicts (e.g. ``{'type': 'error', 'error': {...}}``) are never
    shown to users.  The raw message is logged at ERROR level so developers can
    investigate.

    Args:
        exc: The exception raised during job processing.

    Returns:
        A short, human-readable error string suitable for storing in the DB and
        displaying in the UI.
    """
    raw = str(exc)
    logger.error("Raw job error: %s", raw)

    # Claude API image-size rejection
    if "image exceeds" in raw and "maximum" in raw:
        return "Image too large — please use images under 5 MB and try again."
    if "invalid_request_error" in raw and ("image" in raw.lower() or "size" in raw.lower()):
        return "Image too large — please use images under 5 MB and try again."

    # Anthropic / API rate-limit or overload
    if "overloaded" in raw.lower() or "rate_limit" in raw.lower() or "529" in raw:
        return "Generation service is temporarily busy — please try again in a moment."

    # Auth / key issues
    if "authentication_error" in raw or "invalid_api_key" in raw.lower():
        return "Configuration error — please contact support."

    # Generic transient / timeout
    if "timeout" in raw.lower() or "timed out" in raw.lower():
        return "Generation timed out — please try again."

    # Workflow-specific messages we already control
    if "Workflow error" in raw:
        return "Generation failed — please try again."

    # Fallback: don't leak the raw dict, but give enough context
    return "Generation failed — please try again."


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
    """Generate images sequentially using the Gemini API.

    The Gemini image generation model does not support batchGenerateContent,
    so we generate one image at a time using the synchronous API in a thread
    pool to avoid blocking the event loop.

    Images are written directly to persistent storage.

    Args:
        job_id: The job UUID string (used as the storage namespace).
        product_dir: Directory containing the NanoBanana prompts JSON and
                     reference images.
        product_id: Product identifier (e.g. "R001").
        resolution: Image resolution — "1k", "2k", or "4k".
        api_key: Gemini API key.
        poll_interval: Unused (kept for API compatibility).

    Returns:
        List of stable image URL paths (e.g. ``["/api/images/{job_id}/..."``]).
    """
    import asyncio
    import functools

    from etsy_listing_agent.image_generator import (
        generate_image_gemini,
        parse_nanobanana_json,
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
    storage = get_storage()
    storage_job_dir = storage.job_dir(job_id)
    output_dir = storage_job_dir / f"generated_{resolution}"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Update job status to generating
    db = get_db()
    try:
        _job_service.update_status(
            db, job_id, status="generating", progress=60,
            stage_name="generating_images",
        )
    finally:
        db.close()

    # Generate images sequentially (in thread pool to avoid blocking)
    loop = asyncio.get_event_loop()
    image_urls: list[str] = []
    generated = 0
    failed = 0

    for i, entry in enumerate(entries):
        # Build reference image paths
        ref_paths = [
            str(product_dir / ref_name)
            for ref_name in entry.reference_images
            if (product_dir / ref_name).exists()
        ]

        try:
            logger.info(
                "Generating image %d/%d for job %s: %s",
                i + 1, len(entries), job_id, entry.type_en,
            )

            image_bytes = await loop.run_in_executor(
                None,
                functools.partial(
                    generate_image_gemini,
                    prompt=entry.prompt,
                    reference_image_paths=ref_paths,
                    resolution=resolution,
                    api_key=api_key,
                ),
            )

            # Save image to persistent storage
            safe_type = entry.type_en.replace("/", "_").replace(" ", "_")
            filename = f"{product_id}_{safe_type}_{i+1}.png"
            image_path = output_dir / filename
            image_path.write_bytes(image_bytes)

            # Build stable URL
            rel = image_path.relative_to(storage_job_dir)
            url = f"/api/images/{job_id}/{str(rel).replace(chr(92), '/')}"
            image_urls.append(url)
            generated += 1

            # Update progress (60-95 range for image generation)
            progress = 60 + int((i + 1) / len(entries) * 35)
            db = get_db()
            try:
                _job_service.update_status(
                    db, job_id, status="generating", progress=progress,
                    stage_name=f"image_{i+1}_of_{len(entries)}",
                )
            finally:
                db.close()

        except Exception as exc:
            logger.warning(
                "Failed to generate image %d/%d for job %s (%s): %s",
                i + 1, len(entries), job_id, entry.type_en, exc,
            )
            failed += 1

    logger.info(
        "Image generation complete for job %s — %d generated, %d failed",
        job_id, generated, failed,
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

        # Compress images BEFORE passing them to the workflow so Claude never
        # sees files larger than its 5 MB per-image limit (DEC-012 / BUG-1).
        image_files = _compress_product_images(product_dir, image_files)

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
        # Convert raw API errors to user-friendly messages (DEC-012 / BUG-2).
        # _friendly_error_message logs the raw error at ERROR level for devs.
        friendly_msg = _friendly_error_message(exc)
        try:
            _job_service.mark_failed(db, job_id, error_message=friendly_msg)
        except Exception:
            logger.exception("Could not mark job %s as failed", job_id)
        # --- Send failure email (best-effort) ---
        try:
            await _notify_job_failed(db, job_id, product_id, error_message=friendly_msg)
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
