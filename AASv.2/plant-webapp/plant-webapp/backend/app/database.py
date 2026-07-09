"""
Database engine/session management. Replaces the old JSON file storage
(tank_levels.json, fertilizer_log.json) with a proper SQL database.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session per-request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Called on startup. Use Alembic migrations in production."""
    from app import models  # noqa: F401 ensures models are registered on Base
    Base.metadata.create_all(bind=engine)
