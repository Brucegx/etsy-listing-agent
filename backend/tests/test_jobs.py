"""Tests for the jobs API endpoints (DEC-003).

Tests cover:
  GET /api/jobs/{job_id}  — status polling
  GET /api/jobs           — job history with pagination
"""

import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import _sign_session
from app.main import app
from app.models import Base
from app.models.job import Job, JOB_STATUS_QUEUED, JOB_STATUS_COMPLETED, JOB_STATUS_FAILED
from app.models.user import User

client = TestClient(app)


# ---------------------------------------------------------------------------
# DB + auth helpers
# ---------------------------------------------------------------------------


def _make_test_db():
    """Create a shared in-memory DB and return a session factory."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _create_user(session_factory, google_id: str = "test_google_1") -> User:
    s = session_factory()
    user = User(
        google_id=google_id,
        email=f"{google_id}@example.com",
        name="Test User",
    )
    s.add(user)
    s.commit()
    s.refresh(user)
    s.close()
    return user


def _create_job(session_factory, user: User, **kwargs) -> Job:
    s = session_factory()
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
# GET /api/jobs/{job_id}
# ---------------------------------------------------------------------------


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_get_job_returns_status(mock_get_db, mock_job_svc):
    """GET /api/jobs/{job_id} returns job details for the owning user."""
    SessionLocal = _make_test_db()
    user = _create_user(SessionLocal, "user_A")

    job = _create_job(SessionLocal, user, status=JOB_STATUS_QUEUED)

    # Wire mocks
    mock_get_db.return_value = SessionLocal()
    db_for_job = SessionLocal()
    mock_job_obj = db_for_job.query(Job).filter(Job.job_id == job.job_id).first()
    mock_job_svc.get_by_job_id.return_value = mock_job_obj

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()

        r = client.get(
            f"/api/jobs/{job.job_id}",
            cookies={"session": _sign_session("user_A")},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["job_id"] == job.job_id
    assert data["status"] == JOB_STATUS_QUEUED
    assert data["progress"] == 0
    assert data["product_id"] == "R001"

    db_for_job.close()


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_get_job_404_for_unknown(mock_get_db, mock_job_svc):
    """GET /api/jobs/{job_id} returns 404 for unknown job_id."""
    SessionLocal = _make_test_db()
    _create_user(SessionLocal, "user_B")
    mock_get_db.return_value = SessionLocal()
    mock_job_svc.get_by_job_id.return_value = None

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get(
            "/api/jobs/nonexistent_job_id",
            cookies={"session": _sign_session("user_B")},
        )

    assert r.status_code == 404


def test_get_job_401_without_auth():
    """GET /api/jobs/{job_id} without session returns 401."""
    r = client.get("/api/jobs/some_job_id")
    assert r.status_code == 401


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_get_job_403_for_wrong_user(mock_get_db, mock_job_svc):
    """GET /api/jobs/{job_id} returns 403 when job belongs to another user."""
    SessionLocal = _make_test_db()
    owner = _create_user(SessionLocal, "owner_C")
    other = _create_user(SessionLocal, "other_C")
    job = _create_job(SessionLocal, owner)

    mock_get_db.return_value = SessionLocal()
    db = SessionLocal()
    mock_job_obj = db.query(Job).filter(Job.job_id == job.job_id).first()
    mock_job_svc.get_by_job_id.return_value = mock_job_obj

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get(
            f"/api/jobs/{job.job_id}",
            cookies={"session": _sign_session("other_C")},
        )

    assert r.status_code == 403
    db.close()


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_get_job_completed_with_images(mock_get_db, mock_job_svc):
    """GET /api/jobs/{job_id} returns image_urls and result when completed."""
    SessionLocal = _make_test_db()
    user = _create_user(SessionLocal, "user_D")

    job = _create_job(
        SessionLocal,
        user,
        status=JOB_STATUS_COMPLETED,
        progress=100,
        stage_name="completed",
        image_urls=["/api/images/abc/img1.png", "/api/images/abc/img2.png"],
        result={"listing": {"title": "Test Ring"}},
    )

    mock_get_db.return_value = SessionLocal()
    db = SessionLocal()
    mock_job_obj = db.query(Job).filter(Job.job_id == job.job_id).first()
    mock_job_svc.get_by_job_id.return_value = mock_job_obj

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get(
            f"/api/jobs/{job.job_id}",
            cookies={"session": _sign_session("user_D")},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["status"] == JOB_STATUS_COMPLETED
    assert data["progress"] == 100
    assert len(data["image_urls"]) == 2
    assert data["result"]["listing"]["title"] == "Test Ring"
    db.close()


# ---------------------------------------------------------------------------
# GET /api/jobs
# ---------------------------------------------------------------------------


def test_list_jobs_401_without_auth():
    """GET /api/jobs without session returns 401."""
    r = client.get("/api/jobs")
    assert r.status_code == 401


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_list_jobs_returns_user_jobs(mock_get_db, mock_job_svc):
    """GET /api/jobs returns jobs belonging to the authenticated user."""
    SessionLocal = _make_test_db()
    user = _create_user(SessionLocal, "user_E")

    j1 = _create_job(SessionLocal, user, product_id="P001")
    j2 = _create_job(SessionLocal, user, product_id="P002")

    mock_get_db.return_value = SessionLocal()
    db = SessionLocal()
    jobs_objs = db.query(Job).filter(Job.user_id == user.id).all()

    mock_job_svc.list_for_user.return_value = (jobs_objs, 2)

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get("/api/jobs", cookies={"session": _sign_session("user_E")})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert len(data["jobs"]) == 2
    db.close()


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_list_jobs_pagination(mock_get_db, mock_job_svc):
    """GET /api/jobs respects page and page_size query params."""
    SessionLocal = _make_test_db()
    user = _create_user(SessionLocal, "user_F")

    mock_get_db.return_value = SessionLocal()
    mock_job_svc.list_for_user.return_value = ([], 25)

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get(
            "/api/jobs?page=2&page_size=10",
            cookies={"session": _sign_session("user_F")},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["total"] == 25
    assert data["total_pages"] == 3

    _, kwargs = mock_job_svc.list_for_user.call_args
    assert kwargs.get("page") == 2
    assert kwargs.get("page_size") == 10


@patch("app.api.jobs._job_service")
@patch("app.deps.get_db")
def test_list_jobs_empty(mock_get_db, mock_job_svc):
    """GET /api/jobs returns empty list for new user."""
    SessionLocal = _make_test_db()
    _create_user(SessionLocal, "user_G")
    mock_get_db.return_value = SessionLocal()
    mock_job_svc.list_for_user.return_value = ([], 0)

    with patch("app.api.jobs.get_db") as mock_jobs_db:
        mock_jobs_db.return_value = SessionLocal()
        r = client.get("/api/jobs", cookies={"session": _sign_session("user_G")})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["jobs"] == []
    assert data["total_pages"] == 1


# ---------------------------------------------------------------------------
# JobService unit tests
# ---------------------------------------------------------------------------


def test_job_service_create_and_get():
    """JobService.create_job + get_by_job_id work on in-memory DB."""
    from app.services.job_service import JobService

    SessionLocal = _make_test_db()
    s = SessionLocal()
    user = User(google_id="svc_test_1", email="svc@test.com", name="Test")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "P001", user_id=user.id, category="rings")
    assert job.job_id
    assert job.status == JOB_STATUS_QUEUED

    fetched = svc.get_by_job_id(s, job.job_id)
    assert fetched is not None
    assert fetched.job_id == job.job_id
    s.close()


def test_job_service_lifecycle():
    """JobService advances job through the full lifecycle."""
    from app.services.job_service import JobService
    from app.models.job import JOB_STATUS_STRATEGY, JOB_STATUS_GENERATING

    SessionLocal = _make_test_db()
    s = SessionLocal()
    user = User(google_id="svc_test_2", email="svc2@test.com", name="Test")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "P002", user_id=user.id)

    svc.mark_strategy(s, job.job_id)
    updated = svc.get_by_job_id(s, job.job_id)
    assert updated.status == JOB_STATUS_STRATEGY
    assert updated.progress == 10

    svc.mark_generating(s, job.job_id)
    updated = svc.get_by_job_id(s, job.job_id)
    assert updated.status == JOB_STATUS_GENERATING
    assert updated.progress == 50

    svc.mark_completed(
        s,
        job.job_id,
        result={"listing": {}},
        image_urls=["/api/images/j/img.png"],
    )
    updated = svc.get_by_job_id(s, job.job_id)
    assert updated.status == JOB_STATUS_COMPLETED
    assert updated.progress == 100
    assert updated.image_urls == ["/api/images/j/img.png"]
    s.close()


def test_job_service_mark_failed():
    """JobService.mark_failed stores the error message."""
    from app.services.job_service import JobService

    SessionLocal = _make_test_db()
    s = SessionLocal()
    user = User(google_id="svc_test_3", email="svc3@test.com", name="Test")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    job = svc.create_job(s, "P003", user_id=user.id)
    svc.mark_failed(s, job.job_id, "Gemini timeout")

    updated = svc.get_by_job_id(s, job.job_id)
    assert updated.status == JOB_STATUS_FAILED
    assert updated.error_message == "Gemini timeout"
    s.close()


def test_job_service_list_for_user_pagination():
    """JobService.list_for_user returns paginated results newest-first."""
    from app.services.job_service import JobService

    SessionLocal = _make_test_db()
    s = SessionLocal()
    user = User(google_id="svc_test_4", email="svc4@test.com", name="Test")
    s.add(user)
    s.commit()
    s.refresh(user)

    svc = JobService()
    for i in range(5):
        svc.create_job(s, f"P{i:03d}", user_id=user.id)

    jobs, total = svc.list_for_user(s, user.id, page=1, page_size=3)
    assert total == 5
    assert len(jobs) == 3

    jobs_p2, total2 = svc.list_for_user(s, user.id, page=2, page_size=3)
    assert total2 == 5
    assert len(jobs_p2) == 2
    s.close()
