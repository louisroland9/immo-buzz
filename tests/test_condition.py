"""Unit tests for the renovation intensity detection."""

from __future__ import annotations

import pytest

from immo_buzz.engine.condition import detect_condition, normalize_text
from immo_buzz.engine.grids import Condition


def test_normalize_text_strips_accents_and_punctuation() -> None:
    assert normalize_text("À rénover !!!") == "a renover"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Appartement à rénover entièrement", Condition.HEAVY),
        ("Maison de caractère à restaurer", Condition.HEAVY),
        ("Appartement à rafraîchir, peintures à refaire", Condition.REFRESH),
        ("Studio sympa, petits travaux", Condition.REFRESH),
        ("Appartement à rénover avec cuisine à refaire", Condition.RENOVATION),
        ("Immeuble de rapport, travaux à prévoir", Condition.RENOVATION),
        ("Bel appartement refait à neuf", Condition.GOOD),
        ("", Condition.GOOD),
    ],
)
def test_detect_condition_from_keywords(text: str, expected: Condition) -> None:
    assert detect_condition(text) is expected


def test_poor_energy_class_triggers_renovation() -> None:
    assert detect_condition("Appartement lumineux", "G") is Condition.RENOVATION
    assert detect_condition("Appartement lumineux", "F") is Condition.RENOVATION


def test_good_energy_class_keeps_good_condition() -> None:
    assert detect_condition("Appartement lumineux", "B") is Condition.GOOD


def test_heavy_keyword_wins_over_light_one() -> None:
    text = "A rafraichir mais toiture a refaire"
    assert detect_condition(text) is Condition.HEAVY
