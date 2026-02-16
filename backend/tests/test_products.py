import io
from unittest.mock import patch, AsyncMock

import openpyxl
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_excel_bytes() -> bytes:
    """Create a minimal Excel file with product IDs."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["款号", "材质", "尺寸"])
    ws.append(["R001", "925银", "adjustable"])
    ws.append(["R002", "铜镀金", "7"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_products_requires_auth():
    """GET /api/products without cookies should return 401."""
    r = client.get("/api/products?folder_id=abc&excel_file_id=xyz")
    assert r.status_code == 401


@patch("app.api.products.DriveClient")
def test_list_products_from_excel(MockDriveClient):
    """GET /api/products should return product IDs from Excel."""
    mock_client = AsyncMock()
    MockDriveClient.return_value = mock_client

    excel_bytes = _make_excel_bytes()
    mock_client.list_files.return_value = [
        {"id": "excel_123", "name": "products.xlsx", "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    ]
    mock_client.download_file.return_value = excel_bytes
    mock_client.list_folders.return_value = [
        {"id": "folder_abc", "name": "Rings"}
    ]

    r = client.get(
        "/api/products?folder_id=folder_abc&excel_file_id=excel_123",
        cookies={"session": "google_123", "access_token": "test_token"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["products"] == ["R001", "R002"]
    assert data["category"] == "rings"


@patch("app.api.products.DriveClient")
def test_list_products_google_sheet(MockDriveClient):
    """GET /api/products should export Google Sheets as xlsx."""
    mock_client = AsyncMock()
    MockDriveClient.return_value = mock_client

    excel_bytes = _make_excel_bytes()
    mock_client.list_files.return_value = [
        {"id": "sheet_123", "name": "Products", "mimeType": "application/vnd.google-apps.spreadsheet"}
    ]
    mock_client.download_google_sheet_as_xlsx.return_value = excel_bytes
    mock_client.list_folders.return_value = []

    r = client.get(
        "/api/products?folder_id=folder_abc&excel_file_id=sheet_123",
        cookies={"session": "google_123", "access_token": "test_token"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["products"] == ["R001", "R002"]
    mock_client.download_google_sheet_as_xlsx.assert_called_once_with("sheet_123")
