"""Detection of listings that only look like high yield opportunities.

Some ads advertise an unrealistically high yield because they do not sell the
full ownership of a rented dwelling: ``viager`` sales and ``demembrement``
(bare ownership / usufruct) are the usual culprits. Those listings are not
comparable to a standard buy to let deal and must be discarded before any
yield computation.

The detection works on the normalized listing text (title plus description) and
mirrors the token strategy used by :mod:`immo_buzz.engine.condition`.
"""

from __future__ import annotations

import re

from immo_buzz.engine.condition import normalize_text

# Ready made signals announcing a viager sale or a split ownership.
VIAGER_PATTERNS = (
    r"\bviager\b",
    r"\bviagere\b",
    r"\ben viager\b",
    r"\brente viagere\b",
    r"\bbouquet\b",
    r"\bnue propriete\b",
    r"\bnue-propriete\b",
    r"\bnue proprietaire\b",
    r"\bnue-proprietaire\b",
    r"\bdemembrement\b",
    r"\busufruit\b",
    r"\busufruitier\b",
)

# Human readable reason returned for each family of patterns.
_VIAGER_REASON = "viager ou demembrement (nue-propriete, usufruit)"

_RULE = re.compile("|".join(VIAGER_PATTERNS))


def detect_exclusion(text: str) -> str | None:
    """Return the reason to reject a listing, or ``None`` when it is valid.

    ``text`` should combine the title and the description of the listing. The
    only textual exclusion handled here is the viager / split ownership family:
    price sanity checks live in :mod:`immo_buzz.engine.yield_calc`.
    """
    if _RULE.search(normalize_text(text)):
        return _VIAGER_REASON
    return None
