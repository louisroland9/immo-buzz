"""Text based renovation intensity detection."""

from __future__ import annotations

import re
import unicodedata

from immo_buzz.engine.grids import Condition

# Ordered from the most severe to the lightest pattern so the worst signals
# win when several keywords appear in the same description.
CONDITION_KEYWORDS: tuple[tuple[Condition, tuple[str, ...]], ...] = (
    (
        Condition.HEAVY,
        (
            "a restaurer",
            "a renover entierement",
            "renovation complete",
            "renovation lourde",
            "gros travaux",
            "travaux importants",
            "a reconstruire",
            "insalubre",
            "toiture a refaire",
            "effondrement",
        ),
    ),
    (
        Condition.RENOVATION,
        (
            "a renover",
            "travaux a prevoir",
            "travaux a realiser",
            "a rafraichir et renover",
            "a moderniser",
            "a mettre au gout du jour",
            "a remettre au gout du jour",
            "a amenager",
            "electicite a refaire",
            "electricite a refaire",
            "plomberie a refaire",
            "sans cuisine",
            "sans salle d eau",
        ),
    ),
    (
        Condition.REFRESH,
        (
            "a rafraichir",
            "rafraichissement",
            "quelques travaux",
            "petits travaux",
            "a peindre",
            "peintures a refaire",
            "a actualiser",
            "a deco",
        ),
    ),
)

POOR_ENERGY_CLASSES: frozenset[str] = frozenset({"F", "G"})

_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    """Lowercase, strip accents and collapse separators to single spaces."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return _NON_WORD.sub(" ", without_accents).strip()


def detect_condition(text: str, energy_class: str | None = None) -> Condition:
    """Infer the renovation intensity of a listing.

    ``text`` should combine title and description. A poor energy label is
    treated as a renovation signal when no keyword is found.
    """
    normalized = f" {normalize_text(text)} "
    for condition, keywords in CONDITION_KEYWORDS:
        if any(f" {keyword} " in normalized for keyword in keywords):
            return condition
    if energy_class is not None and energy_class.strip().upper() in POOR_ENERGY_CLASSES:
        return Condition.RENOVATION
    return Condition.GOOD
