"""End-to-end API surface tests covering all Phase 1 + Phase 2 endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_full_api_surface():
    """All API routes are registered and respond with correct auth behavior."""
    # Health (public)
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    # Auth: me requires session
    r = client.get("/api/auth/me")
    assert r.status_code == 401

    # Auth: login redirects to Google
    r = client.get("/api/auth/login", follow_redirects=False)
    assert r.status_code == 307
    assert "accounts.google.com" in r.headers["location"]

    # Auth: callback requires code
    r = client.get("/api/auth/callback")
    assert r.status_code == 400

    # Drive: requires auth
    r = client.get("/api/drive/folders")
    assert r.status_code == 401

    r = client.get("/api/drive/files/test_folder")
    assert r.status_code == 401

    # Products: requires auth
    r = client.get("/api/products?folder_id=abc&excel_file_id=xyz")
    assert r.status_code == 401

    # Generate: requires auth
    r = client.post(
        "/api/generate/single",
        json={
            "drive_folder_id": "test_folder",
            "product_id": "R001",
            "category": "rings",
            "excel_file_id": "test_excel",
        },
    )
    assert r.status_code == 401

    # Save: requires auth
    r = client.post(
        "/api/save",
        json={
            "drive_folder_id": "folder_abc",
            "product_id": "R001",
            "listing": {"title": "Test"},
        },
    )
    assert r.status_code == 401

    # Logout: always succeeds (redirects)
    r = client.post("/api/auth/logout", follow_redirects=False)
    assert r.status_code == 302
