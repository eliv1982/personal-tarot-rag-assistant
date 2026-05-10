from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:  # pragma: no cover - optional dependency at runtime
    Image = None  # type: ignore[assignment]

PROJECT_ROOT = Path(__file__).resolve().parents[1]
logger = logging.getLogger(__name__)

CARD_IMAGE_PATHS = (
    PROJECT_ROOT / "assets" / "tarot" / "cards",
    PROJECT_ROOT / "web" / "static" / "images" / "cards",
    PROJECT_ROOT / "telegram_bot" / "assets" / "cards",
)

CARD_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
CARD_BACKS_DIR = PROJECT_ROOT / "assets" / "tarot" / "card_backs"
DEFAULT_CARD_BACK_ASSET_NAME = "solar_arcana_seal.png"
REVERSED_CARD_IMAGE_CACHE_DIR = (
    PROJECT_ROOT / "runtime" / "tarot_card_images" / "reversed"
)


def get_card_image_path(card_slug: str) -> Optional[Path]:
    slug = (card_slug or "").strip()
    if not slug:
        return None

    for directory in CARD_IMAGE_PATHS:
        for extension in CARD_IMAGE_EXTENSIONS:
            candidate = directory / f"{slug}{extension}"
            if candidate.is_file():
                return candidate
    return None


def get_oriented_card_image_path(card_slug: str, orientation: str) -> Optional[Path]:
    source_path = get_card_image_path(card_slug)
    if source_path is None:
        return None
    if (orientation or "").strip() != "reversed":
        return source_path
    return _get_reversed_card_image_path(source_path)


def get_card_back_image_path(asset_name: str = DEFAULT_CARD_BACK_ASSET_NAME) -> Optional[Path]:
    candidate = CARD_BACKS_DIR / (asset_name or "").strip()
    if candidate.is_file():
        return candidate
    return None


def _get_reversed_card_image_path(source_path: Path) -> Path:
    cached_path = REVERSED_CARD_IMAGE_CACHE_DIR / source_path.name

    if Image is None:
        logger.warning(
            "Pillow is unavailable; using original tarot card image for reversed orientation path=%s",
            source_path,
        )
        return source_path

    try:
        if _needs_refresh(source_path, cached_path):
            cached_path.parent.mkdir(parents=True, exist_ok=True)
            with Image.open(source_path) as image:
                rotated = image.rotate(180, expand=False)
                rotated.save(cached_path)
        return cached_path
    except Exception:
        logger.warning(
            "Failed to prepare reversed tarot card image source=%s cache=%s; using original asset",
            source_path,
            cached_path,
            exc_info=True,
        )
        return source_path


def _needs_refresh(source_path: Path, cached_path: Path) -> bool:
    if not cached_path.is_file():
        return True
    try:
        return source_path.stat().st_mtime > cached_path.stat().st_mtime
    except OSError:
        return True
