from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app_core.tarot.deck import list_cards
CARD_ASSETS_DIR = PROJECT_ROOT / "assets" / "tarot" / "cards"
CARD_BACKS_DIR = PROJECT_ROOT / "assets" / "tarot" / "card_backs"
EXPECTED_CARD_BACK = "solar_arcana_seal.png"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _expected_card_asset_names() -> set[str]:
    return {f"{card.slug}.png" for card in list_cards()}


def _actual_card_asset_names() -> set[str]:
    return {
        path.name
        for path in CARD_ASSETS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }


def main() -> int:
    expected = _expected_card_asset_names()
    actual = _actual_card_asset_names()

    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    card_back_path = CARD_BACKS_DIR / EXPECTED_CARD_BACK

    print(f"expected_cards={len(expected)}")
    print(f"actual_cards={len(actual)}")
    print(f"missing_count={len(missing)}")
    for name in missing:
        print(f"MISSING {name}")
    print(f"extra_count={len(extra)}")
    for name in extra:
        print(f"EXTRA {name}")
    print(f"card_back_exists={card_back_path.is_file()}")
    print(f"card_back_path={card_back_path.relative_to(PROJECT_ROOT)}")

    return 1 if missing or extra or not card_back_path.is_file() else 0


if __name__ == "__main__":
    raise SystemExit(main())
