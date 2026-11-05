"""Unit tests for the renovation intensity detection."""

from __future__ import annotations

import pytest

from immo_buzz.engine.condition import detect_condition, normalize_text
from immo_buzz.engine.grids import Condition


def test_normalize_text_strips_accents_and_punctuation() -> None:
    assert normalize_text("À rénover !!!") == "a renover"


def test_normalize_text_resolves_html_entities_and_tags() -> None:
    assert normalize_text("Travaux &agrave; pr&eacute;voir<br>&rarr;") == (
        "travaux a prevoir"
    )
    assert normalize_text("Maison &agrave; r&eacute;nover<br>Situ&eacute;e") == (
        "maison a renover situee"
    )
    # An entity splitting a keyword must be repaired.
    assert normalize_text("bien &agrave; r&eacute;nov er") == "bien a renov er"


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


def test_work_to_do_flag_triggers_renovation() -> None:
    assert detect_condition("Appartement lumineux", works_signalled=True) is (
        Condition.RENOVATION
    )
    assert detect_condition("Appartement lumineux", works_signalled=False) is (
        Condition.GOOD
    )
    assert detect_condition("Appartement lumineux", works_signalled=None) is (
        Condition.GOOD
    )


def test_keyword_wins_over_work_to_do_flag() -> None:
    text = "Immeuble a restaurer"
    assert detect_condition(text, works_signalled=True) is Condition.HEAVY


def test_html_encoded_keyword_is_detected() -> None:
    text = "Travaux &agrave; pr&eacute;voir : r&eacute;novation int&eacute;rieure"
    assert detect_condition(text) is Condition.RENOVATION


def test_good_energy_class_keeps_good_condition() -> None:
    assert detect_condition("Appartement lumineux", "B") is Condition.GOOD


def test_heavy_keyword_wins_over_light_one() -> None:
    text = "A rafraichir mais toiture a refaire"
    assert detect_condition(text) is Condition.HEAVY
