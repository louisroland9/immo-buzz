"""Tests for the SQLite schema migrations."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_sold_column_is_added_to_an_existing_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE listing (id INTEGER PRIMARY KEY, url VARCHAR NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO listing (id, url) VALUES (1, 'https://example.test/1')")
        )

    monkeypatch.setenv("IMMO_DATABASE_URL", database_url)
    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))

    command.upgrade(config, "head")

    columns = {column["name"] for column in inspect(engine).get_columns("listing")}
    assert "sold" in columns
    with engine.connect() as connection:
        sold = connection.execute(text("SELECT sold FROM listing")).all()
    assert sold == [(0,)]


def test_net_yield_columns_are_added_and_gross_renamed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "legacy_yield.db"
    database_url = f"sqlite:///{database_path}"
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE listing ("
                "id INTEGER PRIMARY KEY, url VARCHAR NOT NULL, "
                "estimated_yield FLOAT)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO listing (id, url, estimated_yield) "
                "VALUES (1, 'https://example.test/1', 9.06)"
            )
        )

    monkeypatch.setenv("IMMO_DATABASE_URL", database_url)
    project_root = Path(__file__).resolve().parents[1]
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))

    command.upgrade(config, "head")

    columns = {column["name"] for column in inspect(engine).get_columns("listing")}
    assert "estimated_gross_yield" in columns
    assert "estimated_yield" not in columns
    assert {"estimated_net_yield", "estimated_property_tax"} <= columns
    assert "estimated_condo_fees" in columns
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT estimated_gross_yield FROM listing")
        ).all()
    assert row == [(9.06,)]
