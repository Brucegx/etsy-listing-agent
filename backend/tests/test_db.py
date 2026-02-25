import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.models import Base
from app.models.user import User
from app.models.job import Job


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_user_model(db_session):
    user = User(
        google_id="123456",
        email="test@example.com",
        name="Test User",
        access_token="token_abc",
        refresh_token="refresh_abc",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@example.com"
    assert user.google_id == "123456"


def test_job_model(db_session):
    import uuid
    user = User(google_id="123", email="test@example.com", name="Test")
    db_session.add(user)
    db_session.commit()

    job = Job(
        job_id=uuid.uuid4().hex,
        user_id=user.id,
        product_id="R001",
        category="rings",
        drive_folder_id="folder_abc",
        status="queued",
        progress=0,
        stage_name="queued",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.id is not None
    assert job.job_id is not None
    assert job.status == "queued"
    assert job.progress == 0
    assert job.user_id == user.id


def test_job_model_status_lifecycle(db_session):
    """Job status can be advanced through the expected lifecycle."""
    import uuid
    from app.models.job import (
        JOB_STATUS_QUEUED, JOB_STATUS_STRATEGY,
        JOB_STATUS_GENERATING, JOB_STATUS_COMPLETED
    )

    user = User(google_id="456", email="lifecycle@example.com", name="Test")
    db_session.add(user)
    db_session.commit()

    job = Job(
        job_id=uuid.uuid4().hex,
        user_id=user.id,
        product_id="R002",
        status=JOB_STATUS_QUEUED,
        progress=0,
        stage_name="queued",
    )
    db_session.add(job)
    db_session.commit()

    # Advance through lifecycle
    job.status = JOB_STATUS_STRATEGY
    job.progress = 10
    db_session.commit()
    assert job.status == JOB_STATUS_STRATEGY

    job.status = JOB_STATUS_GENERATING
    job.progress = 50
    db_session.commit()
    assert job.status == JOB_STATUS_GENERATING

    job.status = JOB_STATUS_COMPLETED
    job.progress = 100
    job.image_urls = ["/api/images/job_id/img1.png"]
    job.result = {"listing": {"title": "Test"}}
    db_session.commit()
    db_session.refresh(job)

    assert job.status == JOB_STATUS_COMPLETED
    assert job.progress == 100
    assert job.image_urls is not None
    assert len(job.image_urls) == 1


def test_tables_created(db_session):
    inspector = inspect(db_session.get_bind())
    tables = inspector.get_table_names()
    assert "users" in tables
    assert "jobs" in tables
