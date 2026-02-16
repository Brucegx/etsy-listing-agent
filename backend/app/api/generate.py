import json
import logging
import uuid
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.drive.client import DriveClient
from app.services.product_service import ProductService
from app.services.temp_manager import TempManager
from app.services.workflow_runner import WorkflowRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["generate"])

_product_service = ProductService()
_workflow_runner: WorkflowRunner | None = None


def _get_workflow_runner() -> WorkflowRunner:
    """Lazy-init the workflow runner (avoids import-time LangGraph compilation)."""
    global _workflow_runner
    if _workflow_runner is None:
        _workflow_runner = WorkflowRunner()
    return _workflow_runner


class SingleGenerateRequest(BaseModel):
    """Request to generate listing content for a single product."""

    drive_folder_id: str
    product_id: str
    category: str
    excel_file_id: str
    generate_images: bool = True
    image_model: str = "flash"


def _sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _get_drive_client(request: Request) -> DriveClient:
    """Extract access_token from cookies and return a DriveClient."""
    session = request.cookies.get("session")
    access_token = request.cookies.get("access_token")
    if not session or not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return DriveClient(access_token=access_token)


def _read_result_files(product_dir: Path, product_id: str) -> dict:
    """Read the output JSON files produced by the workflow."""
    result = {}

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


@router.post("/single")
async def generate_single(
    request: Request, body: SingleGenerateRequest
) -> StreamingResponse:
    """Generate listing + prompts for a single product. Returns SSE stream."""
    client = _get_drive_client(request)

    async def event_stream() -> AsyncGenerator[str, None]:
        temp = TempManager()
        try:
            yield _sse_event(
                "start", {"product_id": body.product_id, "status": "starting"}
            )

            # Step 1: Download files from Drive
            yield _sse_event(
                "progress",
                {"stage": "downloading", "message": "Downloading files from Drive..."},
            )
            product_dir = temp.setup(body.product_id)
            excel_path, image_files = await temp.download_files(
                client, body.drive_folder_id, body.excel_file_id, body.product_id
            )

            # Step 2: Parse Excel row
            yield _sse_event(
                "progress",
                {"stage": "parsing", "message": "Parsing product data..."},
            )
            excel_bytes = excel_path.read_bytes()
            excel_row = _product_service.get_row_from_bytes(
                excel_bytes, body.product_id
            )

            # Step 3: Build state and run LangGraph workflow
            runner = _get_workflow_runner()
            state = runner.build_state(
                product_id=body.product_id,
                product_path=str(product_dir),
                category=body.category,
                excel_row=excel_row,
                image_files=image_files,
                generate_images=body.generate_images,
            )

            async for event in runner.run_with_events(state, run_id=temp.run_id):
                yield _sse_event(event["event"], event["data"])

            # Step 4: Read result files and send complete event
            results = _read_result_files(product_dir, body.product_id)
            yield _sse_event(
                "complete",
                {
                    "product_id": body.product_id,
                    "status": "completed",
                    "results": results,
                    "run_id": temp.run_id,
                },
            )

        except Exception as e:
            logger.exception("Generation failed")
            yield _sse_event("error", {"message": "Generation failed. Please try again."})
        finally:
            temp.schedule_cleanup(ttl_seconds=3600)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


_MAX_UPLOAD_FILES = 10
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/upload")
async def generate_upload(
    images: list[UploadFile] = File(...),
    material: str = Form(...),
    size: str = Form(...),
) -> StreamingResponse:
    """Generate listing + images from uploaded files. No auth required.

    Accepts multipart/form-data with product images, material, and size.
    Returns SSE stream with progress events and results.
    """
    if len(images) > _MAX_UPLOAD_FILES:
        raise HTTPException(400, f"Maximum {_MAX_UPLOAD_FILES} images allowed")
    if not images:
        raise HTTPException(400, "At least one image is required")
    for img in images:
        if img.content_type and img.content_type not in _ALLOWED_CONTENT_TYPES:
            raise HTTPException(400, f"Unsupported file type: {img.content_type}")
        if img.size and img.size > _MAX_FILE_SIZE:
            raise HTTPException(400, f"File too large: {img.filename} (max 10MB)")

    product_id = f"upload_{uuid.uuid4().hex[:6]}"

    async def event_stream() -> AsyncGenerator[str, None]:
        temp = TempManager()
        try:
            yield _sse_event(
                "start", {"product_id": product_id, "status": "starting"}
            )

            # Step 1: Save uploaded images to temp dir
            yield _sse_event(
                "progress",
                {"stage": "uploading", "message": "Saving uploaded images..."},
            )
            product_dir = temp.setup(product_id)
            image_files: list[str] = []
            for img in images:
                content = await img.read()
                filename = img.filename or f"image_{len(image_files)}.png"
                (product_dir / filename).write_bytes(content)
                image_files.append(filename)

            # Step 2: Build excel_row from form fields
            excel_row = {
                "款号": product_id,
                "材质": material,
                "尺寸": size,
            }

            # Step 3: Run LangGraph workflow (category="" for AI inference)
            yield _sse_event(
                "progress",
                {"stage": "generating", "message": "Running AI workflow..."},
            )
            runner = _get_workflow_runner()
            state = runner.build_state(
                product_id=product_id,
                product_path=str(product_dir),
                category="",
                excel_row=excel_row,
                image_files=image_files,
                generate_images=True,
                max_retries=5,
            )

            async for event in runner.run_with_events(state, run_id=temp.run_id):
                yield _sse_event(event["event"], event["data"])

            # Step 4: Read result files and send complete event
            results = _read_result_files(product_dir, product_id)
            yield _sse_event(
                "complete",
                {
                    "product_id": product_id,
                    "status": "completed",
                    "results": results,
                    "run_id": temp.run_id,
                },
            )

        except Exception as e:
            logger.exception("Generation failed")
            yield _sse_event("error", {"message": "Generation failed. Please try again."})
        finally:
            temp.schedule_cleanup(ttl_seconds=3600)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
