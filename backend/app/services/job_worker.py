"""Background job worker — runs the LangGraph workflow for a submitted job.

The worker is invoked via asyncio.create_task() in the generate endpoint.
It updates job status in the DB as it progresses, and copies generated
images into persistent storage (DEC-002 / DEC-003).
"""

import json
import logging
from pathlib import Path
from typing import Any

from app.database import get_db
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
) -> None:
    """Execute the LangGraph workflow for a job in the background.

    Updates job status at each lifecycle stage and persists results and
    images into the storage service.  Any exception marks the job failed.

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
    """
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
            generate_images=generate_images,
            max_retries=max_retries,
        )

        # ----- GENERATING stage (once workflow starts image gen) -----
        # We stream workflow events to track progress; progress updates are
        # approximate since LangGraph doesn't expose per-step percentages.
        node_order = ["preprocess", "strategy", "prompt_aggregator", "image_gen", "listing"]
        completed_nodes: set[str] = set()

        async for event in runner.run_with_events(state, run_id=job_id):
            event_name = event.get("event", "")
            data = event.get("data", {})

            # Update progress based on completed nodes
            node = data.get("node", "")
            if node and node not in completed_nodes:
                completed_nodes.add(node)
                progress = min(90, 10 + int(len(completed_nodes) / max(len(node_order), 1) * 80))
                _job_service.update_status(
                    db,
                    job_id,
                    status="generating" if "image" in node else "strategy",
                    progress=progress,
                    stage_name=node,
                )

            if event_name == "strategy_complete":
                _job_service.mark_generating(db, job_id)

            if event_name == "error":
                raise RuntimeError(data.get("message", "Workflow error"))

        # ----- Persist results -----
        storage = get_storage()
        result = _read_result_files(product_dir, product_id)

        # Copy all generated images to persistent storage
        image_paths = _collect_image_paths(product_dir)
        image_urls: list[str] = []
        for img_path in image_paths:
            # Preserve directory structure relative to product_dir
            try:
                rel = img_path.relative_to(product_dir)
            except ValueError:
                rel = Path(img_path.name)

            parts = rel.parts
            if len(parts) > 1:
                # Has subdirectory (e.g. generated_1k/image.png)
                url = storage.store_file(
                    job_id,
                    str(rel).replace("\\", "/"),
                    img_path.read_bytes(),
                )
            else:
                url = storage.copy_file(job_id, img_path)
            image_urls.append(url)

        _job_service.mark_completed(db, job_id, result=result, image_urls=image_urls)
        logger.info("Job %s finished — %d images stored", job_id, len(image_urls))

    except Exception as exc:
        logger.exception("Job %s failed", job_id)
        try:
            _job_service.mark_failed(db, job_id, error_message=str(exc))
        except Exception:
            logger.exception("Could not mark job %s as failed", job_id)
    finally:
        db.close()
        if temp is not None:
            # Keep input files briefly for debugging, then clean up
            temp.schedule_cleanup(ttl_seconds=3600)
