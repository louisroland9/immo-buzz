"""SQLite engine and session management.

The engine enables WAL journaling and foreign keys on every connection, as
required by the project rules, and is exposed so the upcoming FastAPI or
Streamlit layers can reuse it instead of duplicating the configuration.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from immo_buzz.config import DEFAULT_DATABASE_URL


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Create the parent directory of a relative SQLite file if needed."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return
    raw_path = database_url[len(prefix) :]
    if not raw_path or raw_path.startswith(":memory:"):
        return
    parent = Path(raw_path).parent
    if parent.parts:
        parent.mkdir(parents=True, exist_ok=True)


def make_engine(database_url: str = DEFAULT_DATABASE_URL) -> Engine:
    """Create a SQLite engine configured with WAL and foreign keys."""
    _ensure_sqlite_parent_dir(database_url)
    connect_args = {"check_same_thread": False, "timeout": 30}
    engine = create_engine(database_url, connect_args=connect_args, echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection: object, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    """Create missing tables from the SQLModel metadata.

    Existing databases are upgraded with ``uv run alembic upgrade head``.
    """
    # Import for the metadata side effect: the table must be registered.
    from immo_buzz.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session(engine: Engine) -> Iterator[Session]:
    """Yield a session and guarantee its closure."""
    with Session(engine) as session:
        yield session
