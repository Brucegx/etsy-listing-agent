from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models import Base

# Use sync engine since SQLite + sync is simpler and we're not truly concurrent
_db_url = settings.database_url.replace("+aiosqlite", "")
engine = create_engine(_db_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, class_=Session)


def init_db() -> None:
    """Create all tables."""
    Base.metadata.create_all(engine)


def get_db() -> Session:
    """Get a database session. Caller must close it."""
    return SessionLocal()
