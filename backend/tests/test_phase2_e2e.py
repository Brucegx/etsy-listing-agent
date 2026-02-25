"""Phase 2 E2E: Mock Drive + mock LangGraph → verify full SSE flow."""

import io
import json
from unittest.mock import patch, AsyncMock, MagicMock

import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base
from app.models.user import User

client = TestClient(app)


def _make_excel_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["款号", "材质", "尺寸"])
    ws.append(["R001", "925银", "adjustable"])
    ws.append(["R002", "铜镀金", "7"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


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


def _make_test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


class TestPhase2E2E:
    """Full user journey: login → list products → generate → save."""

    @patch("app.api.auth.get_user_info", new_callable=AsyncMock)
    @patch("app.api.auth.exchange_code", new_callable=AsyncMock)
    @patch("app.api.auth.get_db")
    def test_login_sets_cookies(self, mock_get_db, mock_exchange, mock_userinfo):
        """Step 1: OAuth callback sets both cookies and creates user."""
        SessionLocal = _make_test_db()
        mock_get_db.return_value = SessionLocal()
        mock_exchange.return_value = {
            "access_token": "live_token",
            "refresh_token": "refresh_xyz",
        }
        mock_userinfo.return_value = {
            "id": "g_123",
            "email": "artisan@example.com",
            "name": "Artisan",
        }

        r = client.get("/api/auth/callback?code=auth_code", follow_redirects=False)
        assert r.status_code == 302
        cookies = {c.name: c.value for c in r.cookies.jar}
        assert cookies["session"].startswith("g_123:")
        assert cookies["access_token"] == "live_token"

    @patch("app.api.products.DriveClient")
    def test_list_products(self, MockDriveClient):
        """Step 2: List products from Excel in a Drive folder."""
        mock_client = AsyncMock()
        MockDriveClient.return_value = mock_client

        excel_bytes = _make_excel_bytes()
        mock_client.list_files.return_value = [
            {"id": "excel_1", "name": "data.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ]
        mock_client.download_file.return_value = excel_bytes
        mock_client.list_folders.return_value = [
            {"id": "folder_1", "name": "Rings"},
        ]

        r = client.get(
            "/api/products?folder_id=folder_1&excel_file_id=excel_1",
            cookies={"session": "g_123", "access_token": "live_token"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["products"] == ["R001", "R002"]
        assert data["category"] == "rings"

    @patch("app.api.generate._get_workflow_runner")
    @patch("app.api.generate.DriveClient")
    def test_generate_full_sse_flow(self, MockDriveClient, mock_get_runner):
        """Step 3: Generate produces SSE stream with start→progress→complete."""
        mock_client = AsyncMock()
        MockDriveClient.return_value = mock_client

        excel_bytes = _make_excel_bytes()
        mock_client.list_files.return_value = [
            {"id": "excel_1", "name": "data.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        ]
        mock_client.download_file.return_value = excel_bytes

        mock_runner = MagicMock()
        mock_get_runner.return_value = mock_runner
        mock_runner.build_state.return_value = {
            "product_id": "R001",
            "product_path": "/tmp/test",
            "category": "rings",
        }

        async def fake_workflow(state, run_id=None):
            yield {"event": "progress", "data": {"stage": "preprocess", "message": "Extracting product data..."}}
            yield {"event": "progress", "data": {"stage": "listing", "message": "Generating Etsy listing..."}}
            yield {"event": "progress", "data": {"stage": "prompts", "message": "Creating image prompts..."}}

        mock_runner.run_with_events = fake_workflow

        with patch("app.api.generate._read_result_files") as mock_read:
            mock_read.return_value = {
                "listing": {
                    "title": "Handmade Sterling Silver Ring",
                    "tags": "ring, sterling silver, handmade, adjustable",
                    "description": "A beautiful handmade ring...",
                },
                "prompts": {
                    "product_id": "R001",
                    "prompts": [
                        {"index": 1, "type": "hero", "prompt": "REFERENCE ANCHOR: silver ring..."},
                        {"index": 2, "type": "macro_detail", "prompt": "REFERENCE ANCHOR: close-up..."},
                    ],
                },
                "product_data": {"category": "rings", "materials": ["925 silver"]},
            }

            r = client.post(
                "/api/generate/single/stream",
                json={
                    "drive_folder_id": "folder_1",
                    "product_id": "R001",
                    "category": "rings",
                    "excel_file_id": "excel_1",
                },
                cookies={"session": "g_123", "access_token": "live_token"},
            )

        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]

        events = _parse_sse_events(r.text)
        types = [e["event"] for e in events]

        # Should have: start, downloading progress, parsing progress, 3 workflow progress, complete
        assert types[0] == "start"
        assert "progress" in types
        assert types[-1] == "complete"

        complete = events[-1]
        assert complete["data"]["status"] == "completed"
        assert "listing" in complete["data"]["results"]
        assert "prompts" in complete["data"]["results"]
        assert complete["data"]["results"]["listing"]["title"] == "Handmade Sterling Silver Ring"
        assert len(complete["data"]["results"]["prompts"]["prompts"]) == 2

    @patch("app.api.save.DriveClient")
    def test_save_results_to_drive(self, MockDriveClient):
        """Step 4: Save generated results back to Drive."""
        mock_client = AsyncMock()
        MockDriveClient.return_value = mock_client
        mock_client.upload_file.return_value = {"id": "saved_1", "name": "R001_Listing.json"}

        r = client.post(
            "/api/save",
            json={
                "drive_folder_id": "folder_1",
                "product_id": "R001",
                "listing": {
                    "title": "Handmade Sterling Silver Ring",
                    "tags": "ring, sterling silver",
                    "description": "A beautiful ring...",
                },
                "prompts": {
                    "prompts": [{"index": 1, "type": "hero", "prompt": "A ring..."}],
                },
            },
            cookies={"session": "g_123", "access_token": "live_token"},
        )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert len(data["uploaded"]) == 2
        assert mock_client.upload_file.call_count == 2
