from __future__ import annotations

from pathlib import Path

from app_core.tarot.deck import list_cards
from telegram_bot.card_assets import CARD_IMAGE_EXTENSIONS, CARD_IMAGE_PATHS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CARD_ASSETS_DIR = PROJECT_ROOT / "assets" / "tarot" / "cards"
CARD_BACK_PATH = PROJECT_ROOT / "assets" / "tarot" / "card_backs" / "solar_arcana_seal.png"


def test_tarot_card_assets_match_deck_slugs() -> None:
    expected = {f"{card.slug}.png" for card in list_cards()}
    actual = {
        path.name
        for path in CARD_ASSETS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in CARD_IMAGE_EXTENSIONS
    }

    assert len(expected) == 78
    assert actual == expected


def test_card_assets_directory_is_primary_lookup_path() -> None:
    assert CARD_IMAGE_PATHS[0] == CARD_ASSETS_DIR


def test_virtual_deck_card_back_asset_exists() -> None:
    assert CARD_BACK_PATH.is_file()
