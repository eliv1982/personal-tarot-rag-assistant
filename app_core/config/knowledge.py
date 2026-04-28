"""
Domain-agnostic knowledge configuration for reusable RAG core.

Core-level config should not hardcode vertical-specific legal sources.
Vertical/demo projects must provide their own knowledge entries.
"""

from pathlib import Path
from typing import Any, Dict, List

KnowledgeEntry = Dict[str, Any]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAROT_KNOWLEDGE_ROOT = PROJECT_ROOT / "knowledge_base" / "tarot"


def _iter_markdown_files(base_dir: Path, pattern: str, recursive: bool = True) -> list[Path]:
    if not base_dir.exists():
        return []
    if recursive:
        return sorted(base_dir.rglob(pattern))
    return sorted(base_dir.glob(pattern))


def _source_type_from_relative_path(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/")
    if normalized.startswith("knowledge_base/tarot/cards/"):
        return "card"
    if normalized.startswith("knowledge_base/tarot/spreads/"):
        return "spread"
    if normalized.startswith("knowledge_base/tarot/style/"):
        return "style"
    if normalized.startswith("knowledge_base/tarot/safety/"):
        return "safety"
    return "unknown"


def _source_display(source_type: str, path: Path) -> str:
    stem = path.stem.replace("_", " ").strip()
    prefix = {
        "card": "Card",
        "spread": "Spread",
        "style": "Style",
        "safety": "Safety",
    }.get(source_type, "Source")
    return f"{prefix}: {stem}" if stem else f"{prefix}: {path.name}"


def default_knowledge_entries() -> List[KnowledgeEntry]:
    """
    Neutral default for core starter kit.

    Returns knowledge entries for the current project vertical.
    """
    files: list[Path] = []
    files.extend(_iter_markdown_files(TAROT_KNOWLEDGE_ROOT / "cards", "*.md", recursive=True))
    files.extend(_iter_markdown_files(TAROT_KNOWLEDGE_ROOT / "spreads", "*.md", recursive=False))
    files.extend(_iter_markdown_files(TAROT_KNOWLEDGE_ROOT / "style", "*.md", recursive=False))
    files.extend(_iter_markdown_files(TAROT_KNOWLEDGE_ROOT / "safety", "*.md", recursive=False))

    entries: list[KnowledgeEntry] = []
    for file_path in files:
        relative = file_path.relative_to(PROJECT_ROOT).as_posix()
        source_type = _source_type_from_relative_path(relative)
        entries.append(
            {
                "path": relative,
                "source": relative,
                "source_display": _source_display(source_type, file_path),
                "source_kind": source_type,
                "doc_type": "overview",
            }
        )
    return entries


def default_corpus_entries() -> List[KnowledgeEntry]:
    """
    Backward-compatible alias for legacy naming.
    """
    return default_knowledge_entries()

