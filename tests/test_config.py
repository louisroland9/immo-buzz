"""Tests for the settings resolution and .env loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from immo_buzz.config import DEFAULT_MAX_PAGES, load_settings


def test_env_file_is_loaded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text("IMMO_MAX_PAGES=20\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("IMMO_MAX_PAGES", raising=False)

    assert load_settings().max_pages == 20


def test_real_environment_wins_over_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("IMMO_MAX_PAGES=20\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("IMMO_MAX_PAGES", "7")

    assert load_settings().max_pages == 7


def test_default_is_used_without_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("IMMO_MAX_PAGES", raising=False)

    assert load_settings().max_pages == DEFAULT_MAX_PAGES
