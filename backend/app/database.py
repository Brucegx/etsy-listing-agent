import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

# Use sync engine since SQLite + sync is simpler and we're not truly concurrent
_db_url = settings.database_url.replace("+aiosqlite", "")
_is_sqlite = _db_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(_db_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, class_=Session)


def _migrate_jobs_table() -> None:
    """Add Phase 6A columns to the jobs table if they don't exist yet."""
    insp = inspect(engine)
    if not insp.has_table("jobs"):
        return
    existing = {col["name"] for col in insp.get_columns("jobs")}
    migrations: list[str] = []
    if "job_type" not in existing:
        migrations.append(
            "ALTER TABLE jobs ADD COLUMN job_type VARCHAR(30) NOT NULL DEFAULT 'full_listing'"
        )
    if "image_config" not in existing:
        migrations.append("ALTER TABLE jobs ADD COLUMN image_config JSON")
    if "product_info" not in existing:
        migrations.append("ALTER TABLE jobs ADD COLUMN product_info TEXT")
    if migrations:
        with engine.begin() as conn:
            for sql in migrations:
                conn.execute(text(sql))
        logger.info("Applied %d migration(s) to jobs table", len(migrations))


def init_db() -> None:
    """Create all tables and run lightweight migrations."""
    Base.metadata.create_all(engine)
    _migrate_jobs_table()


def get_db() -> Session:
    """Get a database session. Caller must close it."""
    return SessionLocal()
