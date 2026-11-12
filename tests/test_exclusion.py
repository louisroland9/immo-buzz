"""Unit tests for the fake high yield detection."""

from __future__ import annotations

import pytest

from immo_buzz.engine.exclusion import detect_exclusion


@pytest.mark.parametrize(
    "text",
    [
        "Appartement vendu en viager occupe",
        "Maison en viager, bouquet 50000 EUR",
        "Vente en viager libre de tout occupant",
        "Rente viagere sur immeuble de rapport",
        "Appartement en nue propriete, occupation a vie",
        "Nue-propriete sur un T3 lumineux",
        "Vente en demembrement, usufruit reserve",
        "Usufruit reserve au vendeur",
        "Nue-proprietaire souhaite vendre",
    ],
)
def test_viager_and_split_ownership_are_flagged(text: str) -> None:
    assert detect_exclusion(text) is not None


@pytest.mark.parametrize(
    "text",
    [
        "Appartement refait a neuf, libre immediatement",
        "Immeuble de rapport entierement loue",
        "Studio proche gare, investisseur",
        "Maison a renover entierement",
        "",
    ],
)
def test_standard_listings_are_not_flagged(text: str) -> None:
    assert detect_exclusion(text) is None
