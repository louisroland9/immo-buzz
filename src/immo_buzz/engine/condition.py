"""Text based renovation intensity detection.

Rather than matching a fixed list of contiguous expressions (too brittle:
"travaux à prévoir" never matched "travaux de rénovation à prévoir"), the
detection scores the co-occurrence of pivot tokens. A renovation family token
(``travaux``, ``renover``...) combined with an action token (``a prevoir``,
``a faire``...) yields an intensity, from refresh up to heavy renovation.
"""

from __future__ import annotations

import html
import re
import unicodedata

from immo_buzz.engine.grids import POOR_ENERGY_CLASSES, Condition

# Optional gap between a family token and an action token, e.g.
# "travaux **de renovation** a prevoir" or "gros **travaux** importants".
_GAP = r"(?:\s+[a-z0-9]+){0,4}\s+"

# Tokens that announce renovation work in the listing vocabulary.
FAMILY_TOKENS = (
    "travaux",
    "travau",
    "renovation",
    "renover",
    "restaurer",
    "rafraichissement",
    "rafraichir",
    "rehabiliter",
    "rehabilitation",
)

# Tokens carrying the intensity of the announced work.
ACTION_TOKENS = (
    "a prevoir",
    "a faire",
    "a realiser",
    "a engager",
    "a effectuer",
    "a entreprendre",
    "importants",
    "consequences",
    "budget travaux",
    "remise en etat",
    "modernisation",
)

# Ready made severe signals that do not need a family/action pairing.
HEAVY_PATTERNS = (
    r"a restaurer",
    r"a renover entierement",
    r"renovation complete",
    r"renovation lourde",
    r"renovation totale",
    r"gros travaux",
    r"travaux lourds",
    r"travaux importants",
    r"travaux considerables",
    r"a reconstruire",
    r"insalubre",
    r"toiture a refaire",
    r"effondrement",
    r"structure a reprendre",
)

# Ready made renovation signals (moderate work).
RENOVATION_PATTERNS = (
    r"a renover",
    r"a moderniser",
    r"a mettre au gout du jour",
    r"a remettre au gout du jour",
    r"a amenager",
    r"electricite a refaire",
    r"plomberie a refaire",
    r"sans cuisine",
    r"sans salle d eau",
    r"remise au gout du jour",
    r"a refaire entierement",
)

# Ready made refresh signals (light work).
REFRESH_PATTERNS = (
    r"a rafraichir",
    r"rafraichissement",
    r"quelques travaux",
    r"petits travaux",
    r"a peindre",
    r"peintures a refaire",
    r"a actualiser",
    r"a deco",
    r"a embellir",
)


def _build_rule(patterns: tuple[str, ...]) -> re.Pattern[str]:
    return re.compile("|".join(patterns))


# Family token followed by an action token (with a small gap). The intensity
# depends on the words found around: handled by the caller.
_WORKS_ACTION = re.compile(
    rf"\b(?:{'|'.join(FAMILY_TOKENS)})\b{_GAP}\b(?:{'|'.join(ACTION_TOKENS)})\b"
)

# A bare "travaux" family token with no action gives only a light signal.
_WORKS_BARE = re.compile(rf"\b(?:{'|'.join(FAMILY_TOKENS)})\b")

_HEAVY_RULE = _build_rule(HEAVY_PATTERNS)
_RENOVATION_RULE = _build_rule(RENOVATION_PATTERNS)
_REFRESH_RULE = _build_rule(REFRESH_PATTERNS)

# A "travaux" signal followed by a heavy qualifier becomes a heavy renovation.
_HEAVY_QUALIFIERS = re.compile(
    r"lourd|importants|considerables|lourds|majeurs|structure|toiture|"
    r"gros|entierement|complete|complet|totale|integral"
)

# A "travaux" signal followed by a refresh qualifier stays light.
_REFRESH_QUALIFIERS = re.compile(r"rafraich|peinture|peindre|deco|cosmetique|leger")

_HTML_TAG = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize_text(text: str) -> str:
    """Decode HTML, strip tags, accents and separators from a raw text.

    Listing descriptions come from HTML endpoints: entities (``&agrave;``) and
    tags (``<br>``) must be resolved before matching keywords, otherwise an
    accented letter encoded as an entity breaks the pattern.
    """
    unescaped = html.unescape(text)
    without_tags = _HTML_TAG.sub(" ", unescaped)
    decomposed = unicodedata.normalize("NFKD", without_tags.lower())
    without_accents = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return _NON_WORD.sub(" ", without_accents).strip()


def _detect_from_text(normalized: str) -> Condition | None:
    """Return the strongest renovation signal found in a normalized text."""
    if _HEAVY_RULE.search(normalized):
        return Condition.HEAVY
    if _RENOVATION_RULE.search(normalized):
        return Condition.RENOVATION
    if _REFRESH_RULE.search(normalized):
        return Condition.REFRESH

    # Co-occurrence of a work family and an action token: the intensity comes
    # from the qualifiers found in the matched window.
    for match in _WORKS_ACTION.finditer(normalized):
        window = normalized[max(0, match.start() - 20) : match.end() + 40]
        if _HEAVY_QUALIFIERS.search(window):
            return Condition.HEAVY
        if _REFRESH_QUALIFIERS.search(window):
            return Condition.REFRESH
        return Condition.RENOVATION

    # A bare "travaux"/"renovation" word is a light signal at best.
    if _WORKS_BARE.search(normalized):
        return Condition.REFRESH
    return None


def detect_condition(
    text: str,
    energy_class: str | None = None,
    works_signalled: bool | None = None,
) -> Condition:
    """Infer the renovation intensity of a listing.

    ``text`` should combine title and description. A poor energy label and an
    explicit ``workToDo`` flag from the source are used as fallback signals
    when no textual clue is found.
    """
    condition = _detect_from_text(normalize_text(text))
    if condition is not None:
        return condition
    if energy_class is not None and energy_class.strip().upper() in POOR_ENERGY_CLASSES:
        return Condition.RENOVATION
    if works_signalled:
        return Condition.RENOVATION
    return Condition.GOOD
