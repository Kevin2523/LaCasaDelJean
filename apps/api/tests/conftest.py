"""Pytest fixtures for PostgreSQL 16 migration and integrity tests."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.session import build_engine, build_session_factory

API_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def database_url() -> str:
    """Return PostgreSQL DATABASE_URL required for integration tests."""
    url = os.getenv("DATABASE_URL")
    if not url:
        pytest.fail("DATABASE_URL environment variable must be set for PostgreSQL tests.")
    return url


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    """Build Alembic Config pointing at the test PostgreSQL database."""
    cfg = Config(str(API_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture(scope="session")
def engine(database_url: str) -> Generator[Engine, None, None]:
    """Create a SQLAlchemy engine for the test session."""
    eng = build_engine(database_url)
    yield eng
    eng.dispose()


@pytest.fixture(scope="function")
def migrated_db(alembic_config: Config, engine: Engine) -> Generator[Engine, None, None]:
    """Provide a freshly migrated schema for each test function."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    yield engine


@pytest.fixture(scope="function")
def db_session(migrated_db: Engine) -> Generator[Session, None, None]:
    """Provide a SQLAlchemy Session bound to the freshly migrated database."""
    session_factory = build_session_factory(migrated_db)
    with session_factory() as session:
        yield session
