"""Tests for the wired generate endpoint with mocked Drive + LangGraph."""

import io
import json
from unittest.mock import patch, AsyncMock, MagicMock

import openpyxl
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_excel_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["款号", "材质", "尺寸"])
    ws.append(["R001", "925银", "adjustable"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
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


def test_generate_requires_auth():
    """POST /api/generate/single without cookies should return 401."""
    r = client.post(
        "/api/generate/single",
        json={
            "drive_folder_id": "folder_abc",
            "product_id": "R001",
            "category": "rings",
            "excel_file_id": "excel_123",
        },
    )
    assert r.status_code == 401


@patch("app.api.generate._get_workflow_runner")
@patch("app.api.generate.DriveClient")
def test_generate_streams_sse_events(MockDriveClient, mock_get_runner):
    """POST /api/generate/single should stream SSE events through the full flow."""
    # Mock Drive client
    mock_client = AsyncMock()
    MockDriveClient.return_value = mock_client

    excel_bytes = _make_excel_bytes()
    mock_client.list_files.return_value = [
        {"id": "excel_123", "name": "products.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ]
    mock_client.download_file.return_value = excel_bytes

    # Mock workflow runner
    mock_runner = MagicMock()
    mock_get_runner.return_value = mock_runner

    mock_runner.build_state.return_value = {
        "product_id": "R001",
        "product_path": "/tmp/test",
        "category": "rings",
    }

    async def fake_run_with_events(state, run_id=None):
        yield {"event": "progress", "data": {"stage": "preprocess", "message": "Preprocessing..."}}
        yield {"event": "progress", "data": {"stage": "listing", "message": "Generating listing..."}}

    mock_runner.run_with_events = fake_run_with_events

    # Also mock _read_result_files since no real files exist
    with patch("app.api.generate._read_result_files") as mock_read:
        mock_read.return_value = {
            "listing": {"title": "Beautiful Ring", "tags": "ring, silver"},
            "prompts": {"prompts": [{"type": "hero", "prompt": "A silver ring..."}]},
        }

        r = client.post(
            "/api/generate/single",
            json={
                "drive_folder_id": "folder_abc",
                "product_id": "R001",
                "category": "rings",
                "excel_file_id": "excel_123",
            },
            cookies={"session": "google_123", "access_token": "test_token"},
        )

    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]

    events = _parse_sse_events(r.text)
    event_types = [e["event"] for e in events]

    assert "start" in event_types
    assert "progress" in event_types
    assert "complete" in event_types

    # Verify complete event has results
    complete = next(e for e in events if e["event"] == "complete")
    assert complete["data"]["status"] == "completed"
    assert "listing" in complete["data"]["results"]
    assert "prompts" in complete["data"]["results"]
    assert "run_id" in complete["data"]
