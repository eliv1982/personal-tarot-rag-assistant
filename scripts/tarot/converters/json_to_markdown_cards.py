from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[3]
METABISMUTH_PATH = ROOT_DIR / "raw_sources" / "tarot" / "cards" / "tarot_json_metabismuth.json"
INTERPRETATIONS_PATH = ROOT_DIR / "raw_sources" / "tarot" / "cards" / "tarot_interpretations.json"
OUTPUT_ROOT = ROOT_DIR / "knowledge_base" / "tarot" / "cards"

MAJOR_ARCANA_NAMES: list[str] = [
    "The Fool",
    "The Magician",
    "The High Priestess",
    "The Empress",
    "The Emperor",
    "The Hierophant",
    "The Lovers",
    "The Chariot",
    "Strength",
    "The Hermit",
    "Wheel of Fortune",
    "Justice",
    "The Hanged Man",
    "Death",
    "Temperance",
    "The Devil",
    "The Tower",
    "The Star",
    "The Moon",
    "The Sun",
    "Judgement",
    "The World",
]

MINOR_RANKS: list[str] = [
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

MINOR_SUITS: list[str] = ["cups", "pentacles", "swords", "wands"]

RANK_TO_NUMBER: dict[str, int] = {
    "ace": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "page": 11,
    "knight": 12,
    "queen": 13,
    "king": 14,
}

MAJOR_ALIAS_TO_CANONICAL: dict[str, str] = {
    "the fool": "The Fool",
    "fool": "The Fool",
    "the magician": "The Magician",
    "magician": "The Magician",
    "the high priestess": "The High Priestess",
    "high priestess": "The High Priestess",
    "the papess high priestess": "The High Priestess",
    "papess high priestess": "The High Priestess",
    "the papess": "The High Priestess",
    "papess": "The High Priestess",
    "the empress": "The Empress",
    "empress": "The Empress",
    "the emperor": "The Emperor",
    "emperor": "The Emperor",
    "the hierophant": "The Hierophant",
    "hierophant": "The Hierophant",
    "the pope hierophant": "The Hierophant",
    "pope hierophant": "The Hierophant",
    "the pope": "The Hierophant",
    "pope": "The Hierophant",
    "the lovers": "The Lovers",
    "lovers": "The Lovers",
    "the chariot": "The Chariot",
    "chariot": "The Chariot",
    "strength": "Strength",
    "the hermit": "The Hermit",
    "hermit": "The Hermit",
    "wheel of fortune": "Wheel of Fortune",
    "the wheel": "Wheel of Fortune",
    "wheel": "Wheel of Fortune",
    "justice": "Justice",
    "the hanged man": "The Hanged Man",
    "hanged man": "The Hanged Man",
    "death": "Death",
    "temperance": "Temperance",
    "the devil": "The Devil",
    "devil": "The Devil",
    "the tower": "The Tower",
    "tower": "The Tower",
    "the star": "The Star",
    "star": "The Star",
    "the moon": "The Moon",
    "moon": "The Moon",
    "the sun": "The Sun",
    "sun": "The Sun",
    "judgement": "Judgement",
    "judgment": "Judgement",
    "the world": "The World",
    "world": "The World",
}


@dataclass(frozen=True)
class CardSpec:
    arcana: str
    canonical_name: str
    suit: str
    rank: str
    number: int | None


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_for_match(value: str) -> str:
    text = value.lower().replace("/", " ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return normalize_whitespace(text)


def slugify(value: str) -> str:
    text = normalize_for_match(value).replace(" ", "_")
    return re.sub(r"_+", "_", text).strip("_")


def normalize_arcana(value: Any) -> str:
    text = normalize_for_match(str(value)) if value is not None else ""
    if "major" in text:
        return "major"
    if "minor" in text:
        return "minor"
    return ""


def normalize_suit(value: Any) -> str:
    text = normalize_for_match(str(value)) if value is not None else ""
    mapping = {
        "major": "major",
        "cups": "cups",
        "cup": "cups",
        "swords": "swords",
        "sword": "swords",
        "wands": "wands",
        "wand": "wands",
        "coins": "pentacles",
        "coin": "pentacles",
        "pentacles": "pentacles",
        "pentacle": "pentacles",
    }
    return mapping.get(text, "")


def normalize_rank(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        for rank, number in RANK_TO_NUMBER.items():
            if number == value:
                return rank
        return ""
    text = normalize_for_match(str(value))
    for rank in MINOR_RANKS:
        if text == rank:
            return rank
    if text.isdigit():
        numeric = int(text)
        for rank, number in RANK_TO_NUMBER.items():
            if number == numeric:
                return rank
    return ""


def normalize_major_name(name: Any) -> str:
    if not name:
        return ""
    normalized = normalize_for_match(str(name))
    return MAJOR_ALIAS_TO_CANONICAL.get(normalized, "")


def parse_minor_from_name(name: Any) -> tuple[str, str]:
    if not name:
        return ("", "")
    normalized = normalize_for_match(str(name))
    match = re.match(r"(ace|two|three|four|five|six|seven|eight|nine|ten|page|knight|queen|king)\s+of\s+([a-z]+)", normalized)
    if not match:
        return ("", "")
    rank = match.group(1)
    suit = normalize_suit(match.group(2))
    return (rank, suit)


def build_card_key(record: dict[str, Any]) -> tuple[str, str, str]:
    arcana = normalize_arcana(record.get("arcana"))
    suit = normalize_suit(record.get("suit"))
    name = record.get("name")
    rank = normalize_rank(record.get("rank"))

    if arcana == "major" or suit == "major":
        canonical_name = normalize_major_name(name)
        if not canonical_name and isinstance(record.get("rank"), int):
            rank_number = int(record["rank"])
            if 0 <= rank_number < len(MAJOR_ARCANA_NAMES):
                canonical_name = MAJOR_ARCANA_NAMES[rank_number]
        return ("major", canonical_name, "")

    if not rank or not suit:
        parsed_rank, parsed_suit = parse_minor_from_name(name)
        if not rank:
            rank = parsed_rank
        if not suit:
            suit = parsed_suit

    return ("minor", suit, rank)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and value.strip() == "":
            continue
        return value
    return None


def value_as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def markdown_list(items: list[str]) -> str:
    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items)


def build_card_specs() -> list[CardSpec]:
    specs: list[CardSpec] = []
    for number, name in enumerate(MAJOR_ARCANA_NAMES):
        specs.append(CardSpec(arcana="major", canonical_name=name, suit="", rank="", number=number))
    for suit in MINOR_SUITS:
        for rank in MINOR_RANKS:
            display_name = f"{rank.title()} of {suit.title()}"
            specs.append(
                CardSpec(
                    arcana="minor",
                    canonical_name=display_name,
                    suit=suit,
                    rank=rank,
                    number=RANK_TO_NUMBER[rank],
                )
            )
    return specs


def card_spec_key(spec: CardSpec) -> tuple[str, str, str]:
    if spec.arcana == "major":
        return ("major", spec.canonical_name, "")
    return ("minor", spec.suit, spec.rank)


def destination_for(spec: CardSpec) -> tuple[Path, str]:
    if spec.arcana == "major":
        directory = OUTPUT_ROOT / "major_arcana"
        number = spec.number if spec.number is not None else 0
        filename = f"{number:02d}_{slugify(spec.canonical_name)}.md"
        return directory, filename

    directory = OUTPUT_ROOT / "minor_arcana" / spec.suit
    filename = f"{spec.rank}_of_{spec.suit}.md"
    return directory, filename


def render_markdown(
    card_name: str,
    slug: str,
    arcana: str,
    suit: str,
    rank: str,
    number: str,
    keywords: list[str],
    fortune_telling: list[str],
    meanings_light: list[str],
    meanings_shadow: list[str],
) -> str:
    return (
        f"# {card_name}\n\n"
        "## Metadata\n"
        f"card_name: {card_name}\n"
        f"slug: {slug}\n"
        f"arcana: {arcana}\n"
        f"suit: {suit}\n"
        f"rank: {rank}\n"
        f"number: {number}\n\n"
        "## Keywords\n"
        f"{markdown_list(keywords)}\n\n"
        "## Fortune telling\n"
        f"{markdown_list(fortune_telling)}\n\n"
        "## Meanings - Light\n"
        f"{markdown_list(meanings_light)}\n\n"
        "## Meanings - Shadow\n"
        f"{markdown_list(meanings_shadow)}\n"
    )


def build_source_index(records: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    index: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in records:
        key = build_card_key(record)
        if key in index:
            continue
        index[key] = record
    return index


def convert() -> None:
    metabismuth = load_json(METABISMUTH_PATH)
    interpretations = load_json(INTERPRETATIONS_PATH)

    metabismuth_cards = metabismuth.get("cards", [])
    interpretations_cards = interpretations.get("tarot_interpretations", [])

    if not isinstance(metabismuth_cards, list) or not isinstance(interpretations_cards, list):
        raise ValueError("Input JSON has unexpected structure.")

    metabismuth_index = build_source_index(metabismuth_cards)
    interpretations_index = build_source_index(interpretations_cards)

    processed = 0
    created_paths: set[str] = set()

    for spec in build_card_specs():
        key = card_spec_key(spec)
        source_a = metabismuth_index.get(key, {})
        source_b = interpretations_index.get(key, {})

        card_name = str(first_non_empty(source_a.get("name"), source_b.get("name"), spec.canonical_name))
        arcana = str(first_non_empty(normalize_arcana(source_a.get("arcana")), normalize_arcana(source_b.get("arcana")), spec.arcana))
        suit = str(first_non_empty(normalize_suit(source_a.get("suit")), normalize_suit(source_b.get("suit")), spec.suit))
        rank = str(first_non_empty(normalize_rank(source_a.get("rank")), normalize_rank(source_b.get("rank")), spec.rank))
        if spec.arcana == "major":
            suit = ""
            rank = ""

        number_raw = first_non_empty(source_a.get("number"), source_b.get("number"), source_a.get("rank"), source_b.get("rank"), spec.number)
        number = "" if number_raw is None else str(number_raw)

        meanings = source_b.get("meanings", {}) if isinstance(source_b.get("meanings"), dict) else {}
        keywords = value_as_list(first_non_empty(source_b.get("keywords"), source_a.get("keywords"), []))
        fortune_telling = value_as_list(first_non_empty(source_b.get("fortune_telling"), source_a.get("fortune_telling"), []))
        meanings_light = value_as_list(first_non_empty(meanings.get("light"), source_a.get("meanings_light"), []))
        meanings_shadow = value_as_list(first_non_empty(meanings.get("shadow"), source_a.get("meanings_shadow"), []))

        directory, filename = destination_for(spec)
        directory.mkdir(parents=True, exist_ok=True)
        created_paths.add(str(directory))

        markdown = render_markdown(
            card_name=card_name,
            slug=slugify(card_name),
            arcana=arcana,
            suit=suit,
            rank=rank,
            number=number,
            keywords=keywords,
            fortune_telling=fortune_telling,
            meanings_light=meanings_light,
            meanings_shadow=meanings_shadow,
        )

        output_path = directory / filename
        output_path.write_text(markdown, encoding="utf-8")
        processed += 1

    print(f"Processed cards: {processed}")
    print("Output directories:")
    for path in sorted(created_paths):
        print(f"- {path}")


if __name__ == "__main__":
    convert()
