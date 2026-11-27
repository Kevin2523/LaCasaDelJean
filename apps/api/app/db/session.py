"""SQLAlchemy engine and session factory helpers."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for PostgreSQL."""
    url = database_url or get_settings().database_url
    return create_engine(url, pool_pre_ping=True, future=True)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
