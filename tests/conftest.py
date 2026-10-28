"""Shared fixtures for the test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def bienici_payload() -> dict:
    """Load a recorded Bien'ici response."""
    raw = (FIXTURES_DIR / "bienici_page.json").read_text(encoding="utf-8")
    return json.loads(raw)
