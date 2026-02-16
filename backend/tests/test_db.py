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
    user = User(google_id="123", email="test@example.com", name="Test")
    db_session.add(user)
    db_session.commit()

    job = Job(
        user_id=user.id,
        product_id="R001",
        category="rings",
        drive_folder_id="folder_abc",
        status="pending",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    assert job.id is not None
    assert job.status == "pending"
    assert job.user_id == user.id


def test_tables_created(db_session):
    inspector = inspect(db_session.get_bind())
    tables = inspector.get_table_names()
    assert "users" in tables
    assert "jobs" in tables
