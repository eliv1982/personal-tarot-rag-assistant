from __future__ import annotations

from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CARD_IMAGE_PATHS = (
    PROJECT_ROOT / "assets" / "tarot" / "cards",
    PROJECT_ROOT / "web" / "static" / "images" / "cards",
)


def get_card_image_path(card_slug: str) -> Optional[Path]:
    slug = (card_slug or "").strip()
    if not slug:
        return None

    for directory in CARD_IMAGE_PATHS:
        candidate = directory / f"{slug}.png"
        if candidate.is_file():
            return candidate
    return None
