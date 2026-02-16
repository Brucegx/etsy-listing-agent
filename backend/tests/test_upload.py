"""Tests for the upload-based generate endpoint."""

import io
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# Minimal 1x1 PNG
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _parse_sse_events(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        event_type = ""
        data = ""
        for line in block.strip().split("\n"):
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        if event_type and data:
            events.append({"event": event_type, "data": json.loads(data)})
    return events


def test_upload_requires_images():
    """POST /api/generate/upload without images returns 422."""
    r = client.post(
        "/api/generate/upload",
        data={"material": "925 silver", "size": "2cm"},
    )
    assert r.status_code == 422


def test_upload_requires_material():
    """POST /api/generate/upload without material returns 422."""
    r = client.post(
        "/api/generate/upload",
        files=[("images", ("test.png", PNG_BYTES, "image/png"))],
        data={"size": "2cm"},
    )
    assert r.status_code == 422


def test_upload_requires_size():
    """POST /api/generate/upload without size returns 422."""
    r = client.post(
        "/api/generate/upload",
        files=[("images", ("test.png", PNG_BYTES, "image/png"))],
        data={"material": "925 silver"},
    )
    assert r.status_code == 422


def test_upload_no_auth_required():
    """POST /api/generate/upload works without auth cookies."""
    # Should not return 401 — it may fail later in workflow, but auth is not checked
    r = client.post(
        "/api/generate/upload",
        files=[("images", ("test.png", PNG_BYTES, "image/png"))],
        data={"material": "925 silver", "size": "2cm"},
    )
    # Should be 200 (SSE stream), not 401
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]


@patch("app.api.generate._get_workflow_runner")
def test_upload_streams_sse_events(mock_get_runner):
    """POST /api/generate/upload streams SSE events through workflow."""
    mock_runner = MagicMock()
    mock_get_runner.return_value = mock_runner

    mock_runner.build_state.return_value = {
        "product_id": "upload_abc",
        "product_path": "/tmp/test",
        "category": "",
    }

    async def fake_run(state, run_id=None):
        yield {"event": "progress", "data": {"stage": "preprocess", "message": "Preprocessing..."}}

    mock_runner.run_with_events = fake_run

    with patch("app.api.generate._read_result_files") as mock_read:
        mock_read.return_value = {
            "listing": {"title": "Silver Earrings", "tags": "earrings, silver", "description": "Beautiful..."},
        }

        r = client.post(
            "/api/generate/upload",
            files=[
                ("images", ("photo1.png", PNG_BYTES, "image/png")),
                ("images", ("photo2.png", PNG_BYTES, "image/png")),
            ],
            data={"material": "925 silver", "size": "2cm x 1.5cm"},
        )

    assert r.status_code == 200
    events = _parse_sse_events(r.text)
    event_types = [e["event"] for e in events]

    assert "start" in event_types
    assert "progress" in event_types
    assert "complete" in event_types

    complete = next(e for e in events if e["event"] == "complete")
    assert complete["data"]["status"] == "completed"
    assert "listing" in complete["data"]["results"]
    assert "run_id" in complete["data"]


@patch("app.api.generate._get_workflow_runner")
def test_upload_saves_multiple_images(mock_get_runner):
    """Uploaded images are saved to the product temp directory."""
    mock_runner = MagicMock()
    mock_get_runner.return_value = mock_runner
    mock_runner.build_state.return_value = {}

    saved_files: list[str] = []

    async def fake_run(state, run_id=None):
        yield {"event": "progress", "data": {"stage": "done", "message": "Done"}}

    mock_runner.run_with_events = fake_run

    with patch("app.api.generate._read_result_files") as mock_read, \
         patch("app.api.generate.TempManager") as mock_temp_cls:
        mock_temp = MagicMock()
        mock_temp_cls.return_value = mock_temp
        mock_temp.run_id = "test-run"

        from pathlib import Path
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        mock_temp.setup.return_value = tmp

        mock_read.return_value = {}

        r = client.post(
            "/api/generate/upload",
            files=[
                ("images", ("a.png", PNG_BYTES, "image/png")),
                ("images", ("b.png", PNG_BYTES, "image/png")),
                ("images", ("c.png", PNG_BYTES, "image/png")),
            ],
            data={"material": "copper", "size": "3cm"},
        )

    assert r.status_code == 200
    # Verify images were written to temp dir
    written = list(tmp.iterdir())
    filenames = {f.name for f in written}
    assert {"a.png", "b.png", "c.png"} == filenames


def test_upload_workflow_error_streams_error_event():
    """If workflow throws, an error SSE event is streamed."""
    with patch("app.api.generate._get_workflow_runner") as mock_get_runner:
        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        mock_runner.build_state.side_effect = RuntimeError("Workflow crashed")

        r = client.post(
            "/api/generate/upload",
            files=[("images", ("test.png", PNG_BYTES, "image/png"))],
            data={"material": "silver", "size": "1cm"},
        )

    assert r.status_code == 200
    events = _parse_sse_events(r.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert len(error_events) >= 1
    assert error_events[0]["data"]["message"] == "Generation failed. Please try again."
