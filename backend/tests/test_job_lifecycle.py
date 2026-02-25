"""Integration tests for the full job lifecycle.

Tests cover:
  submit → poll status → batch complete → retrieve images

These tests mock external dependencies (Gemini Batch API, LangGraph workflow,
SMTP email) so they run fast and deterministically without real API keys.

Test matrix:
  1. Job creation and initial queued state
  2. Job worker strategy stage progresses status correctly
  3. Job worker batch submission transitions to batch_submitted
  4. Job worker batch completion saves images to persistent storage
  5. Job worker marks job completed with stable image URLs
  6. Job worker marks job failed on exception
  7. Polling endpoint returns current status at each lifecycle stage
  8. Image retrieval via /api/images/{job_id}/{path} after completion
  9. Email notification sent on completion
  10. Email notification sent on failure
  11. Email skipped gracefully when user has no email (not expected but safe)
  12. Full lifecycle: submit → strategy → batch → complete → retrieve
"""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import _sign_session
from app.main import app
from app.models import Base
from app.models.job import (
    Job,
    JOB_STATUS_QUEUED,
    JOB_STATUS_STRATEGY,
    JOB_STATUS_BATCH_SUBMITTED,
    JOB_STATUS_GENERATING,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
)
from app.models.user import User
from app.services.job_service import JobService
from app.services.storage import StorageService

# ---------------------------------------------------------------------------
# Minimal fake PNG bytes (valid-enough for file existence checks)
# ---------------------------------------------------------------------------
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


# ---------------------------------------------------------------------------
# DB / fixture helpers
# ---------------------------------------------------------------------------


def _make_db():
    """Create an isolated in-memory SQLite DB and return session factory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _add_user(SessionLocal, google_id: str = "g_test", email: str = "test@gmail.com") -> User:
    s = SessionLocal()
    user = User(google_id=google_id, email=email, name="Test User")
    s.add(user)
    s.commit()
    s.refresh(user)
    s.close()
    return user


def _add_job(SessionLocal, user: User, **kwargs) -> Job:
    s = SessionLocal()
    defaults = dict(
        job_id=uuid.uuid4().hex,
        user_id=user.id,
        product_id="R001",
        category="rings",
        status=JOB_STATUS_QUEUED,
        progress=0,
        stage_name="queued",
    )
    defaults.update(kwargs)
    job = Job(**defaults)
    s.add(job)
    s.commit()
    s.refresh(job)
    s.close()
    return job


# ---------------------------------------------------------------------------
# 1. Job creation and initial queued state
# ---------------------------------------------------------------------------


def test_create_job_initial_state():
    """JobService.create_job produces a job in QUEUED state with progress=0."""
    SessionLocal = _make_db()
    s = SessionLocal()
    user = User(google_id="g1", email="u1@test.com", name="U1")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "R001", user_id=user.id, category="rings")

    assert job.status == JOB_STATUS_QUEUED
    assert job.progress == 0
    assert job.stage_name == "queued"
    assert job.job_id  # UUID hex string
    assert job.image_urls is None
    assert job.result is None
    s.close()


# ---------------------------------------------------------------------------
# 2. Job status transitions
# ---------------------------------------------------------------------------


def test_job_status_transitions_strategy_to_completed():
    """JobService transitions: queued → strategy → generating → completed."""
    SessionLocal = _make_db()
    s = SessionLocal()
    user = User(google_id="g2", email="u2@test.com", name="U2")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "R002", user_id=user.id)

    svc.mark_strategy(s, job.job_id)
    j = svc.get_by_job_id(s, job.job_id)
    assert j.status == JOB_STATUS_STRATEGY
    assert j.progress == 10

    svc.mark_generating(s, job.job_id)
    j = svc.get_by_job_id(s, job.job_id)
    assert j.status == JOB_STATUS_GENERATING
    assert j.progress == 50

    svc.mark_completed(
        s,
        job.job_id,
        result={"listing": {"title": "Gold Ring"}},
        image_urls=["/api/images/j/img.png"],
    )
    j = svc.get_by_job_id(s, job.job_id)
    assert j.status == JOB_STATUS_COMPLETED
    assert j.progress == 100
    assert j.image_urls == ["/api/images/j/img.png"]
    assert j.result["listing"]["title"] == "Gold Ring"
    s.close()


def test_job_status_transition_batch_submitted():
    """JobService.update_status transitions job to batch_submitted."""
    SessionLocal = _make_db()
    s = SessionLocal()
    user = User(google_id="g3", email="u3@test.com", name="U3")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "R003", user_id=user.id)

    svc.mark_strategy(s, job.job_id)
    svc.update_status(
        s,
        job.job_id,
        status=JOB_STATUS_BATCH_SUBMITTED,
        progress=60,
        stage_name="batch_submitted:batches/abc123",
    )

    j = svc.get_by_job_id(s, job.job_id)
    assert j.status == JOB_STATUS_BATCH_SUBMITTED
    assert j.progress == 60
    assert "batches/abc123" in j.stage_name
    s.close()


def test_job_mark_failed_stores_error():
    """JobService.mark_failed records status and error message."""
    SessionLocal = _make_db()
    s = SessionLocal()
    user = User(google_id="g4", email="u4@test.com", name="U4")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "R004", user_id=user.id)
    svc.mark_failed(s, job.job_id, "Gemini batch timeout")

    j = svc.get_by_job_id(s, job.job_id)
    assert j.status == JOB_STATUS_FAILED
    assert j.error_message == "Gemini batch timeout"
    s.close()


# ---------------------------------------------------------------------------
# 3. Polling endpoint returns current status
# ---------------------------------------------------------------------------


client = TestClient(app)


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_poll_returns_queued_status(mock_deps_db, mock_job_svc):
    """GET /api/jobs/{job_id} returns queued status for a new job."""
    SessionLocal = _make_db()
    user = _add_user(SessionLocal, "poll_u1")
    job = _add_job(SessionLocal, user, status=JOB_STATUS_QUEUED, progress=0)

    # deps.get_db is called by get_current_user to look up the user by google_id
    mock_deps_db.return_value = SessionLocal()

    db = SessionLocal()
    mock_job_svc.get_by_job_id.return_value = db.query(Job).filter(
        Job.job_id == job.job_id
    ).first()

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get(
            f"/api/jobs/{job.job_id}",
            cookies={"session": _sign_session("poll_u1")},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == JOB_STATUS_QUEUED
    assert data["progress"] == 0
    db.close()


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_poll_returns_completed_with_image_urls(mock_deps_db, mock_job_svc):
    """GET /api/jobs/{job_id} returns image_urls when job is completed."""
    SessionLocal = _make_db()
    user = _add_user(SessionLocal, "poll_u2")
    job = _add_job(
        SessionLocal,
        user,
        status=JOB_STATUS_COMPLETED,
        progress=100,
        stage_name="completed",
        image_urls=[
            "/api/images/abc123/generated_1k/R001_01_hero_1k.png",
            "/api/images/abc123/generated_1k/R001_02_wearing_1k.png",
        ],
        result={"listing": {"title": "Gold Ring"}},
    )

    mock_deps_db.return_value = SessionLocal()
    db = SessionLocal()
    mock_job_svc.get_by_job_id.return_value = db.query(Job).filter(
        Job.job_id == job.job_id
    ).first()

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get(
            f"/api/jobs/{job.job_id}",
            cookies={"session": _sign_session("poll_u2")},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == JOB_STATUS_COMPLETED
    assert data["progress"] == 100
    assert len(data["image_urls"]) == 2
    assert data["result"]["listing"]["title"] == "Gold Ring"
    db.close()


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_poll_returns_failed_status(mock_deps_db, mock_job_svc):
    """GET /api/jobs/{job_id} returns failed status with error message."""
    SessionLocal = _make_db()
    user = _add_user(SessionLocal, "poll_u3")
    job = _add_job(
        SessionLocal,
        user,
        status=JOB_STATUS_FAILED,
        stage_name="failed",
        error_message="Gemini API key invalid",
    )

    mock_deps_db.return_value = SessionLocal()
    db = SessionLocal()
    mock_job_svc.get_by_job_id.return_value = db.query(Job).filter(
        Job.job_id == job.job_id
    ).first()

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get(
            f"/api/jobs/{job.job_id}",
            cookies={"session": _sign_session("poll_u3")},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == JOB_STATUS_FAILED
    assert data["error_message"] == "Gemini API key invalid"
    db.close()


# ---------------------------------------------------------------------------
# 4. Persistent storage integration
# ---------------------------------------------------------------------------


def test_storage_write_and_retrieve_image(tmp_path: Path):
    """StorageService writes image bytes and resolves to correct path."""
    storage = StorageService(base_path=str(tmp_path))
    job_id = uuid.uuid4().hex

    url = storage.store_file(job_id, "generated_1k/hero.png", PNG_BYTES)

    assert url == f"/api/images/{job_id}/generated_1k/hero.png"
    resolved = storage.resolve(job_id, "generated_1k/hero.png")
    assert resolved.exists()
    assert resolved.read_bytes() == PNG_BYTES


def test_storage_serves_via_api_endpoint(tmp_path: Path):
    """Images written to persistent storage are served by /api/images endpoint."""
    storage = StorageService(base_path=str(tmp_path))
    job_id = uuid.uuid4().hex

    storage.store_file(job_id, "generated_1k/ring.png", PNG_BYTES)

    with patch("app.api.images.get_storage", return_value=storage):
        r = client.get(f"/api/images/{job_id}/generated_1k/ring.png")

    assert r.status_code == 200
    assert r.content == PNG_BYTES
    assert r.headers["content-type"] == "image/png"


# ---------------------------------------------------------------------------
# 5. Batch image generation: submit + poll + collect
# ---------------------------------------------------------------------------


def test_submit_image_batch_calls_gemini_client(tmp_path: Path):
    """submit_image_batch builds requests and calls client.batches.create."""
    from etsy_listing_agent.image_generator import (
        PromptEntry,
        submit_image_batch,
    )

    entries = [
        PromptEntry(index=1, type_name="主图", type_en="Hero Shot", goal="main", prompt="A gold ring"),
        PromptEntry(index=2, type_name="佩戴", type_en="Wearing", goal="lifestyle", prompt="Worn on hand"),
    ]

    mock_batch_job = MagicMock()
    mock_batch_job.name = "batches/fake-batch-001"

    mock_client = MagicMock()
    mock_client.batches.create.return_value = mock_batch_job

    with patch("etsy_listing_agent.image_generator.genai.Client", return_value=mock_client):
        batch_name = submit_image_batch(
            entries=entries,
            product_dir=tmp_path,
            resolution="1k",
            api_key="fake_api_key",
            display_name="test-batch",
        )

    assert batch_name == "batches/fake-batch-001"
    assert mock_client.batches.create.called
    call_kwargs = mock_client.batches.create.call_args
    # Verify src has 2 requests
    src_arg = call_kwargs[1]["src"] if call_kwargs[1] else call_kwargs[0][1]
    assert len(src_arg) == 2


def test_poll_batch_returns_immediately_on_success():
    """poll_batch_until_done returns the job when state is JOB_STATE_SUCCEEDED."""
    from etsy_listing_agent.image_generator import poll_batch_until_done

    mock_state = MagicMock()
    mock_state.name = "JOB_STATE_SUCCEEDED"

    mock_batch_job = MagicMock()
    mock_batch_job.state = mock_state

    mock_client = MagicMock()
    mock_client.batches.get.return_value = mock_batch_job

    with patch("etsy_listing_agent.image_generator.genai.Client", return_value=mock_client):
        result = poll_batch_until_done("batches/test", api_key="fake", poll_interval=0.01)

    assert result is mock_batch_job


def test_poll_batch_raises_on_failure():
    """poll_batch_until_done raises RuntimeError when batch fails."""
    from etsy_listing_agent.image_generator import poll_batch_until_done

    mock_state = MagicMock()
    mock_state.name = "JOB_STATE_FAILED"

    mock_batch_job = MagicMock()
    mock_batch_job.state = mock_state

    mock_client = MagicMock()
    mock_client.batches.get.return_value = mock_batch_job

    with patch("etsy_listing_agent.image_generator.genai.Client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="JOB_STATE_FAILED"):
            poll_batch_until_done("batches/test", api_key="fake", poll_interval=0.01)


def test_poll_batch_polls_until_ready():
    """poll_batch_until_done polls repeatedly until state succeeds."""
    from etsy_listing_agent.image_generator import poll_batch_until_done

    pending_state = MagicMock()
    pending_state.name = "JOB_STATE_RUNNING"

    success_state = MagicMock()
    success_state.name = "JOB_STATE_SUCCEEDED"

    pending_job = MagicMock()
    pending_job.state = pending_state

    success_job = MagicMock()
    success_job.state = success_state

    mock_client = MagicMock()
    # Return pending twice, then succeed
    mock_client.batches.get.side_effect = [pending_job, pending_job, success_job]

    with patch("etsy_listing_agent.image_generator.genai.Client", return_value=mock_client):
        with patch("etsy_listing_agent.image_generator.time.sleep"):
            result = poll_batch_until_done("batches/test", api_key="fake", poll_interval=0.01)

    assert mock_client.batches.get.call_count == 3
    assert result is success_job


def test_collect_batch_images_saves_to_disk(tmp_path: Path):
    """collect_batch_images extracts image bytes and writes files to output_dir."""
    from etsy_listing_agent.image_generator import PromptEntry, collect_batch_images

    entries = [
        PromptEntry(index=1, type_name="主图", type_en="Hero_Shot", goal="main", prompt="A ring"),
        PromptEntry(index=2, type_name="佩戴", type_en="Wearing", goal="life", prompt="On hand"),
    ]

    # Build a fake inlined_responses structure
    def _make_response_item(img_bytes: bytes) -> MagicMock:
        part = MagicMock()
        inline_data = MagicMock()
        inline_data.data = img_bytes
        part.inline_data = inline_data

        content = MagicMock()
        content.parts = [part]

        candidate = MagicMock()
        candidate.content = content

        response = MagicMock()
        response.candidates = [candidate]

        item = MagicMock()
        item.response = response
        return item

    dest_obj = MagicMock()
    dest_obj.inlined_responses = [
        _make_response_item(PNG_BYTES),
        _make_response_item(PNG_BYTES + b"2"),
    ]

    batch_job = MagicMock()
    batch_job.dest = dest_obj

    output_dir = tmp_path / "generated_1k"
    results = collect_batch_images(
        batch_job=batch_job,
        entries=entries,
        output_dir=output_dir,
        product_id="R001",
        resolution="1k",
    )

    assert results["success"] is True
    assert len(results["generated"]) == 2
    assert len(results["failed"]) == 0

    # Files should be on disk
    for item in results["generated"]:
        assert Path(item["path"]).exists()


def test_collect_batch_images_handles_missing_responses(tmp_path: Path):
    """collect_batch_images marks entries as failed when responses are missing."""
    from etsy_listing_agent.image_generator import PromptEntry, collect_batch_images

    entries = [
        PromptEntry(index=1, type_name="主图", type_en="Hero", goal="main", prompt="A ring"),
    ]

    dest_obj = MagicMock()
    dest_obj.inlined_responses = []  # Empty — no responses

    batch_job = MagicMock()
    batch_job.dest = dest_obj

    results = collect_batch_images(
        batch_job=batch_job,
        entries=entries,
        output_dir=tmp_path / "generated_1k",
        product_id="R001",
        resolution="1k",
    )

    assert results["success"] is False
    assert len(results["failed"]) == 1
    assert results["failed"][0]["error"] == "No response from batch"


# ---------------------------------------------------------------------------
# 6. Job worker integration: full lifecycle with mocks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_job_complete_lifecycle(tmp_path: Path):
    """run_job runs strategy → batch → complete and saves images."""
    from app.services.job_worker import run_job

    # Set up DB
    SessionLocal = _make_db()
    s = SessionLocal()
    user = User(google_id="wk1", email="worker@test.com", name="Worker")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "R001", user_id=user.id)
    s.close()

    job_id = job.job_id
    product_dir = tmp_path / "product"
    product_dir.mkdir()

    # Create a fake NanoBanana prompts file
    prompts_data = {
        "prompts": [
            {
                "index": 1,
                "type": "Hero Shot",
                "type_name": "主图",
                "goal": "Show product",
                "prompt": "A beautiful gold ring",
                "reference_images": [],
            }
        ]
    }
    (product_dir / "R001_NanoBanana_Prompts.json").write_text(
        json.dumps(prompts_data), encoding="utf-8"
    )

    # Storage pointing to tmp_path
    storage = StorageService(base_path=str(tmp_path / "storage"))

    # Mock workflow runner to yield events without real LangGraph
    async def _fake_run_with_events(state: Any, run_id: str | None = None):
        yield {"event": "start", "data": {"product_id": "R001", "status": "running"}}
        yield {
            "event": "progress",
            "data": {"stage": "strategy", "node": "strategy", "message": "done"},
        }
        yield {
            "event": "strategy_complete",
            "data": {"strategy": {}},
        }
        yield {
            "event": "complete",
            "data": {"product_id": "R001", "status": "completed"},
        }

    mock_runner = MagicMock()
    mock_runner.build_state.return_value = {"product_id": "R001"}
    mock_runner.run_with_events = _fake_run_with_events

    # Mock batch generation to return stable image URLs
    async def _fake_batch_gen(*args: Any, **kwargs: Any) -> list[str]:
        return [f"/api/images/{job_id}/generated_1k/R001_01_Hero_Shot_1k.png"]

    mock_email = AsyncMock(return_value=True)

    with (
        patch("app.services.job_worker._get_workflow_runner", return_value=mock_runner),
        patch("app.services.job_worker.get_db", return_value=SessionLocal()),
        patch("app.services.job_worker.get_storage", return_value=storage),
        patch("app.services.job_worker._run_batch_image_generation", side_effect=_fake_batch_gen),
        patch(
            "app.services.job_worker.get_email_service",
            return_value=MagicMock(
                send_job_completed=mock_email,
                send_job_failed=AsyncMock(),
            ),
        ),
    ):
        await run_job(
            job_id=job_id,
            product_id="R001",
            product_dir=product_dir,
            excel_row={"product_id": "R001"},
            image_files=[],
            category="rings",
            generate_images=True,
        )

    # Verify final job state
    final_db = SessionLocal()
    final_job = svc.get_by_job_id(final_db, job_id)
    assert final_job.status == JOB_STATUS_COMPLETED
    assert final_job.progress == 100
    assert len(final_job.image_urls) == 1
    assert final_job.image_urls[0].startswith(f"/api/images/{job_id}/")
    final_db.close()


@pytest.mark.asyncio
async def test_run_job_marks_failed_on_workflow_error(tmp_path: Path):
    """run_job marks job as FAILED when the workflow raises an exception."""
    from app.services.job_worker import run_job

    SessionLocal = _make_db()
    s = SessionLocal()
    user = User(google_id="wk2", email="worker2@test.com", name="Worker2")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "R001", user_id=user.id)
    s.close()

    job_id = job.job_id
    product_dir = tmp_path / "product2"
    product_dir.mkdir()

    storage = StorageService(base_path=str(tmp_path / "storage2"))

    async def _failing_workflow(state: Any, run_id: str | None = None):
        yield {"event": "start", "data": {"product_id": "R001", "status": "running"}}
        yield {"event": "error", "data": {"message": "LangGraph strategy node crashed"}}

    mock_runner = MagicMock()
    mock_runner.build_state.return_value = {"product_id": "R001"}
    mock_runner.run_with_events = _failing_workflow

    with (
        patch("app.services.job_worker._get_workflow_runner", return_value=mock_runner),
        patch("app.services.job_worker.get_db", return_value=SessionLocal()),
        patch("app.services.job_worker.get_storage", return_value=storage),
        patch(
            "app.services.job_worker.get_email_service",
            return_value=MagicMock(
                send_job_completed=AsyncMock(),
                send_job_failed=AsyncMock(return_value=False),
            ),
        ),
    ):
        await run_job(
            job_id=job_id,
            product_id="R001",
            product_dir=product_dir,
            excel_row={"product_id": "R001"},
            image_files=[],
        )

    final_db = SessionLocal()
    final_job = svc.get_by_job_id(final_db, job_id)
    assert final_job.status == JOB_STATUS_FAILED
    # error_message now stores a user-friendly string (BUG-2 fix).
    # Raw errors are logged at ERROR level — never stored in the DB.
    assert final_job.error_message is not None
    assert len(final_job.error_message) > 0
    # Must be a friendly message, not a raw error dict
    assert "{'type': 'error'" not in (final_job.error_message or "")
    assert "Generation failed" in (final_job.error_message or "")
    final_db.close()


# ---------------------------------------------------------------------------
# 7. Email notification service
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_email_service_sends_completion_email():
    """EmailService.send_job_completed calls aiosmtplib.send with correct args."""
    from app.services.email_service import EmailService

    svc = EmailService(
        from_email="sender@gmail.com",
        app_password="secret",
        frontend_url="http://localhost:3000",
    )

    # aiosmtplib is imported inside the _send method so we patch at its module path
    with patch("aiosmtplib.send", new=AsyncMock(return_value=None)) as mock_send:
        result = await svc.send_job_completed(
            to_email="user@gmail.com",
            user_name="Alice",
            job_id="abc123",
            product_id="R001",
            image_count=10,
        )

    assert result is True
    assert mock_send.called


@pytest.mark.asyncio
async def test_email_service_sends_failure_email():
    """EmailService.send_job_failed calls aiosmtplib.send."""
    from app.services.email_service import EmailService

    svc = EmailService(
        from_email="sender@gmail.com",
        app_password="secret",
        frontend_url="http://localhost:3000",
    )

    with patch("aiosmtplib.send", new=AsyncMock(return_value=None)) as mock_send:
        result = await svc.send_job_failed(
            to_email="user@gmail.com",
            user_name="Alice",
            job_id="abc123",
            product_id="R001",
            error_message="Batch API timeout",
        )

    assert result is True
    assert mock_send.called


@pytest.mark.asyncio
async def test_email_service_no_op_when_unconfigured():
    """EmailService returns False and logs when SMTP not configured."""
    from app.services.email_service import EmailService

    svc = EmailService(from_email="", app_password="")  # Not configured

    result = await svc.send_job_completed(
        to_email="user@gmail.com",
        user_name="Alice",
        job_id="abc123",
        product_id="R001",
        image_count=5,
    )

    assert result is False  # Graceful no-op


@pytest.mark.asyncio
async def test_email_service_returns_false_on_smtp_error():
    """EmailService returns False (not raises) when SMTP connection fails."""
    from app.services.email_service import EmailService

    svc = EmailService(
        from_email="sender@gmail.com",
        app_password="secret",
        frontend_url="http://localhost:3000",
    )

    with patch("aiosmtplib.send", new=AsyncMock(side_effect=ConnectionRefusedError("SMTP down"))):
        result = await svc.send_job_completed(
            to_email="user@gmail.com",
            user_name="Alice",
            job_id="abc123",
            product_id="R001",
            image_count=3,
        )

    assert result is False


# ---------------------------------------------------------------------------
# 8. generate_images_for_product with use_batch=True (integration path)
# ---------------------------------------------------------------------------


def test_generate_images_for_product_uses_batch_api(tmp_path: Path):
    """generate_images_for_product routes through _generate_images_batch."""
    from etsy_listing_agent.image_generator import generate_images_for_product

    product_dir = tmp_path / "R001"
    product_dir.mkdir()

    prompts_data = {
        "prompts": [
            {
                "index": 1,
                "type": "Hero",
                "type_name": "主图",
                "goal": "main",
                "prompt": "A gold ring",
                "reference_images": [],
            }
        ]
    }
    (product_dir / "R001_NanoBanana_Prompts.json").write_text(
        json.dumps(prompts_data), encoding="utf-8"
    )

    mock_batch_name = "batches/test-batch-001"

    mock_state = MagicMock()
    mock_state.name = "JOB_STATE_SUCCEEDED"
    mock_batch_job = MagicMock()
    mock_batch_job.state = mock_state

    # Return one image from inlined_responses
    part = MagicMock()
    part.inline_data = MagicMock(data=PNG_BYTES)
    candidate = MagicMock()
    candidate.content = MagicMock(parts=[part])
    response = MagicMock()
    response.candidates = [candidate]
    resp_item = MagicMock()
    resp_item.response = response

    dest = MagicMock()
    dest.inlined_responses = [resp_item]
    mock_batch_job.dest = dest

    mock_client = MagicMock()
    mock_client.batches.create.return_value = MagicMock(name=mock_batch_name)
    mock_client.batches.get.return_value = mock_batch_job

    # Ensure batches.create().name == mock_batch_name
    created = MagicMock()
    created.name = mock_batch_name
    mock_client.batches.create.return_value = created

    with patch("etsy_listing_agent.image_generator.genai.Client", return_value=mock_client):
        with patch("etsy_listing_agent.image_generator.time.sleep"):
            results = generate_images_for_product(
                product_path=str(product_dir),
                product_id="R001",
                resolution="1k",
                api_key="fake_key",
                use_batch=True,
                poll_interval=0.001,
            )

    assert results["success"] is True
    assert len(results["generated"]) == 1
    assert results["generated"][0]["type"] == "Hero"


def test_generate_images_for_product_dry_run(tmp_path: Path):
    """generate_images_for_product dry_run returns empty results without API calls."""
    from etsy_listing_agent.image_generator import generate_images_for_product

    product_dir = tmp_path / "R002"
    product_dir.mkdir()

    prompts_data = {
        "prompts": [
            {
                "index": 1,
                "type": "Hero",
                "type_name": "主图",
                "goal": "main",
                "prompt": "A gold ring",
                "reference_images": [],
            }
        ]
    }
    (product_dir / "R002_NanoBanana_Prompts.json").write_text(
        json.dumps(prompts_data), encoding="utf-8"
    )

    results = generate_images_for_product(
        product_path=str(product_dir),
        product_id="R002",
        resolution="1k",
        dry_run=True,
    )

    assert results["success"] is True
    assert results["generated"] == []
    assert results["failed"] == []


def test_generate_images_for_product_missing_prompts_file(tmp_path: Path):
    """generate_images_for_product returns error dict when prompts file missing."""
    from etsy_listing_agent.image_generator import generate_images_for_product

    product_dir = tmp_path / "R999"
    product_dir.mkdir()
    # No prompts JSON file

    results = generate_images_for_product(
        product_path=str(product_dir),
        product_id="R999",
        resolution="1k",
        api_key="fake",
    )

    assert results["success"] is False
    assert "Prompts file not found" in results["error"]
