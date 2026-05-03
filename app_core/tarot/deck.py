from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Union

Arcana = Literal["major", "minor"]
Suit = Literal["cups", "pentacles", "swords", "wands"]
OrientationRank = Union[int, str]


@dataclass(frozen=True)
class TarotCard:
    slug: str
    display_name_en: str
    display_name_ru: str
    arcana: Arcana
    suit: Optional[Suit]
    rank: OrientationRank
    knowledge_path: str


_MINOR_SUIT_DISPLAY_RU: Dict[Suit, str] = {
    "cups": "Кубков",
    "pentacles": "Пентаклей",
    "swords": "Мечей",
    "wands": "Жезлов",
}

_MINOR_SUIT_DISPLAY_EN: Dict[Suit, str] = {
    "cups": "Cups",
    "pentacles": "Pentacles",
    "swords": "Swords",
    "wands": "Wands",
}

_MINOR_RANKS_EN: List[str] = [
    "ace",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "page",
    "knight",
    "queen",
    "king",
]

_MINOR_RANKS_RU: Dict[str, str] = {
    "ace": "Туз",
    "two": "Двойка",
    "three": "Тройка",
    "four": "Четвёрка",
    "five": "Пятёрка",
    "six": "Шестёрка",
    "seven": "Семёрка",
    "eight": "Восьмёрка",
    "nine": "Девятка",
    "ten": "Десятка",
    "page": "Паж",
    "knight": "Рыцарь",
    "queen": "Королева",
    "king": "Король",
}

_MINOR_RANKS_DISPLAY_EN: Dict[str, str] = {
    "ace": "Ace",
    "two": "Two",
    "three": "Three",
    "four": "Four",
    "five": "Five",
    "six": "Six",
    "seven": "Seven",
    "eight": "Eight",
    "nine": "Nine",
    "ten": "Ten",
    "page": "Page",
    "knight": "Knight",
    "queen": "Queen",
    "king": "King",
}


def _minor_slug(rank: str, suit: Suit) -> str:
    return f"{rank}_of_{suit}"


def _minor_knowledge_path(rank: str, suit: Suit) -> str:
    slug = _minor_slug(rank, suit)
    return f"knowledge_base/tarot/cards/minor_arcana/{suit}/{slug}.md"


def _build_minor_cards() -> List[TarotCard]:
    out: List[TarotCard] = []
    for suit in ("cups", "pentacles", "swords", "wands"):
        for rank in _MINOR_RANKS_EN:
            slug = _minor_slug(rank, suit)  # e.g. page_of_cups
            display_name_en = f"{_MINOR_RANKS_DISPLAY_EN[rank]} of {_MINOR_SUIT_DISPLAY_EN[suit]}"
            display_name_ru = f"{_MINOR_RANKS_RU[rank]} {_MINOR_SUIT_DISPLAY_RU[suit]}"
            out.append(
                TarotCard(
                    slug=slug,
                    display_name_en=display_name_en,
                    display_name_ru=display_name_ru,
                    arcana="minor",
                    suit=suit,
                    rank=rank,
                    knowledge_path=_minor_knowledge_path(rank, suit),
                )
            )
    return out


_MAJOR_CARDS: List[dict[str, object]] = [
    {"num": 0, "slug": "the_fool", "en": "The Fool", "ru": "Шут", "file": "00_the_fool.md"},
    {"num": 1, "slug": "the_magician", "en": "The Magician", "ru": "Маг", "file": "01_the_magician.md"},
    {
        "num": 2,
        "slug": "the_high_priestess",
        "en": "The High Priestess",
        "ru": "Верховная Жрица",
        "file": "02_the_high_priestess.md",
    },
    {"num": 3, "slug": "the_empress", "en": "The Empress", "ru": "Императрица", "file": "03_the_empress.md"},
    {"num": 4, "slug": "the_emperor", "en": "The Emperor", "ru": "Император", "file": "04_the_emperor.md"},
    {"num": 5, "slug": "the_hierophant", "en": "The Hierophant", "ru": "Иерофант", "file": "05_the_hierophant.md"},
    {"num": 6, "slug": "the_lovers", "en": "The Lovers", "ru": "Влюбленные", "file": "06_the_lovers.md"},
    {"num": 7, "slug": "the_chariot", "en": "The Chariot", "ru": "Колесница", "file": "07_the_chariot.md"},
    {"num": 8, "slug": "strength", "en": "Strength", "ru": "Сила", "file": "08_strength.md"},
    {"num": 9, "slug": "the_hermit", "en": "The Hermit", "ru": "Отшельник", "file": "09_the_hermit.md"},
    {
        "num": 10,
        "slug": "wheel_of_fortune",
        "en": "Wheel of Fortune",
        "ru": "Колесо Фортуны",
        "file": "10_wheel_of_fortune.md",
    },
    {"num": 11, "slug": "justice", "en": "Justice", "ru": "Справедливость", "file": "11_justice.md"},
    {
        "num": 12,
        "slug": "the_hanged_man",
        "en": "The Hanged Man",
        "ru": "Повешенный",
        "file": "12_the_hanged_man.md",
    },
    {"num": 13, "slug": "death", "en": "Death", "ru": "Смерть", "file": "13_death.md"},
    {"num": 14, "slug": "temperance", "en": "Temperance", "ru": "Умеренность", "file": "14_temperance.md"},
    {"num": 15, "slug": "the_devil", "en": "The Devil", "ru": "Дьявол", "file": "15_the_devil.md"},
    {"num": 16, "slug": "the_tower", "en": "The Tower", "ru": "Башня", "file": "16_the_tower.md"},
    {"num": 17, "slug": "the_star", "en": "The Star", "ru": "Звезда", "file": "17_the_star.md"},
    {"num": 18, "slug": "the_moon", "en": "The Moon", "ru": "Луна", "file": "18_the_moon.md"},
    {"num": 19, "slug": "the_sun", "en": "The Sun", "ru": "Солнце", "file": "19_the_sun.md"},
    {"num": 20, "slug": "judgement", "en": "Judgement", "ru": "Суд", "file": "20_judgement.md"},
    {"num": 21, "slug": "the_world", "en": "The World", "ru": "Мир", "file": "21_the_world.md"},
]


def _build_major_cards() -> List[TarotCard]:
    out: List[TarotCard] = []
    for item in _MAJOR_CARDS:
        num = int(item["num"])  # type: ignore[arg-type]
        slug = str(item["slug"])  # type: ignore[arg-type]
        display_name_en = str(item["en"])  # type: ignore[arg-type]
        display_name_ru = str(item["ru"])  # type: ignore[arg-type]
        file_name = str(item["file"])  # type: ignore[arg-type]
        out.append(
            TarotCard(
                slug=slug,
                display_name_en=display_name_en,
                display_name_ru=display_name_ru,
                arcana="major",
                suit=None,
                rank=num,
                knowledge_path=f"knowledge_base/tarot/cards/major_arcana/{file_name}",
            )
        )
    return out


ALL_TAROT_CARDS: List[TarotCard] = _build_major_cards() + _build_minor_cards()
CARD_BY_SLUG: Dict[str, TarotCard] = {c.slug: c for c in ALL_TAROT_CARDS}
_CARD_NAME_INDEX: Dict[str, TarotCard] = {}

_MAJOR_ARCANA_ALIASES: Dict[str, tuple[str, ...]] = {
    "the_fool": ("шут", "дурак", "fool", "the fool"),
    "the_magician": ("маг", "фокусник", "magician", "the magician"),
    "the_high_priestess": (
        "жрица",
        "верховная жрица",
        "папесса",
        "high priestess",
        "the high priestess",
    ),
    "the_empress": ("императрица", "empress", "the empress"),
    "the_emperor": ("император", "emperor", "the emperor"),
    "the_hierophant": (
        "иерофант",
        "верховный жрец",
        "жрец",
        "папа",
        "hierophant",
        "the hierophant",
    ),
    "the_lovers": ("влюбленные", "влюблённые", "любовники", "lovers", "the lovers"),
    "the_chariot": ("колесница", "chariot", "the chariot"),
    "strength": ("сила", "strength"),
    "the_hermit": ("отшельник", "hermit", "the hermit"),
    "wheel_of_fortune": (
        "колесо фортуны",
        "фортуна",
        "wheel of fortune",
        "the wheel of fortune",
    ),
    "justice": ("справедливость", "правосудие", "justice"),
    "the_hanged_man": (
        "повешенный",
        "повешенный человек",
        "hanged man",
        "the hanged man",
    ),
    "death": ("смерть", "death"),
    "temperance": ("умеренность", "temperance"),
    "the_devil": ("дьявол", "devil", "the devil"),
    "the_tower": ("башня", "tower", "the tower"),
    "the_star": ("звезда", "star", "the star"),
    "the_moon": ("луна", "moon", "the moon"),
    "the_sun": ("солнце", "sun", "the sun"),
    "judgement": ("суд", "страшный суд", "judgement", "judgment", "rebirth"),
    "the_world": ("мир", "вселенная", "world", "the world"),
}

_MINOR_RANK_ALIASES: Dict[str, tuple[str, ...]] = {
    "ace": ("туз", "ace"),
    "two": ("двойка", "два", "2", "two"),
    "three": ("тройка", "три", "3", "three"),
    "four": ("четверка", "четвёрка", "четыре", "4", "four"),
    "five": ("пятерка", "пятёрка", "пять", "5", "five"),
    "six": ("шестерка", "шестёрка", "шесть", "6", "six"),
    "seven": ("семерка", "семёрка", "семь", "7", "seven"),
    "eight": ("восьмерка", "восьмёрка", "восемь", "8", "eight"),
    "nine": ("девятка", "девять", "9", "nine"),
    "ten": ("десятка", "десять", "10", "ten"),
    "page": ("паж", "валет", "принцесса", "page"),
    "knight": ("рыцарь", "всадник", "knight"),
    "queen": ("королева", "дама", "queen"),
    "king": ("король", "king"),
}

_MINOR_SUIT_ALIASES: Dict[Suit, tuple[str, ...]] = {
    "wands": (
        "жезлов",
        "жезлы",
        "посохов",
        "посохи",
        "скипетров",
        "скипетры",
        "палок",
        "палки",
        "wands",
        "of wands",
    ),
    "cups": ("кубков", "кубки", "чаш", "чаши", "cups", "of cups"),
    "swords": ("мечей", "мечи", "swords", "of swords"),
    "pentacles": (
        "пентаклей",
        "пентакли",
        "монет",
        "монеты",
        "дисков",
        "диски",
        "денариев",
        "денарии",
        "pentacles",
        "of pentacles",
        "coins",
        "of coins",
        "disks",
        "of disks",
    ),
}


def _normalize_card_lookup_name(value: str) -> str:
    normalized = (value or "").strip().lower().replace("ё", "е")
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"[-–—/\\]+", " ", normalized)
    normalized = re.sub(r"[\"'`“”‘’.,:;!?(){}\[\]]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _build_card_name_index() -> Dict[str, TarotCard]:
    candidates: Dict[str, set[str]] = {}

    def register(card: TarotCard, variant: str) -> None:
        key = _normalize_card_lookup_name(variant)
        if not key:
            return
        candidates.setdefault(key, set()).add(card.slug)

    for card in ALL_TAROT_CARDS:
        for variant in _card_lookup_variants(card):
            register(card, variant)

    index: Dict[str, TarotCard] = {}
    for key, slugs in candidates.items():
        if len(slugs) == 1:
            slug = next(iter(slugs))
            card = CARD_BY_SLUG.get(slug)
            if card is not None:
                index[key] = card
    return index


def _card_lookup_variants(card: TarotCard) -> set[str]:
    variants = {
        card.slug,
        card.slug.replace("_", " "),
        card.display_name_en,
        card.display_name_ru,
    }

    if card.arcana == "major":
        variants.update(_MAJOR_ARCANA_ALIASES.get(card.slug, ()))
        return variants

    rank = str(card.rank)
    suit = card.suit
    if suit is None:
        return variants

    rank_aliases = _MINOR_RANK_ALIASES.get(rank, (rank,))
    suit_aliases = _MINOR_SUIT_ALIASES.get(suit, (suit,))
    for rank_alias in rank_aliases:
        for suit_alias in suit_aliases:
            variants.add(f"{rank_alias} {suit_alias}")

    return variants


_CARD_NAME_INDEX = _build_card_name_index()


def list_cards() -> List[TarotCard]:
    """Return all 78 cards."""
    return list(ALL_TAROT_CARDS)


def resolve_card_by_name(name: str) -> Optional[TarotCard]:
    normalized = _normalize_card_lookup_name(name)
    if not normalized:
        return None
    return _CARD_NAME_INDEX.get(normalized) or CARD_BY_SLUG.get(normalized)

