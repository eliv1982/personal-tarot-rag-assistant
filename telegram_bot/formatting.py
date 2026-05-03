from __future__ import annotations

import html
import re


_MARKDOWN_MARKERS_RE = re.compile(r"(\*\*|__|`|~~)")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_SECTION_HEADINGS = (
    "Расклад:",
    "Карты:",
    "Смысл карты:",
    "Связь с вопросом:",
    "На что обратить внимание:",
    "Вопрос к себе:",
    "Общий рисунок:",
    "По позициям:",
    "Ключевые акценты:",
    "Следующий бережный шаг:",
    "Интерпретация:",
)
_TRAILING_INVITATION_STARTS = (
    "если хотите",
    "могу",
)


def clean_telegram_text(text: str) -> str:
    cleaned = _MARKDOWN_MARKERS_RE.sub("", text or "")
    cleaned = cleaned.replace("\r\n", "\n").strip()
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned)
    cleaned = _remove_trailing_invitation(cleaned)
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned).strip()
    return cleaned


def split_telegram_message(text: str, limit: int = 3500) -> list[str]:
    normalized = (text or "").strip()
    if len(normalized) <= limit:
        return [normalized] if normalized else []

    paragraphs = normalized.split("\n\n")
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= limit:
            current = candidate
            continue

        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= limit:
            current = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + limit, len(paragraph))
            split_at = paragraph.rfind("\n", start, end)
            if split_at <= start:
                split_at = paragraph.rfind(" ", start, end)
            if split_at <= start:
                split_at = end
            chunks.append(paragraph[start:split_at].strip())
            start = split_at
            while start < len(paragraph) and paragraph[start] in {" ", "\n"}:
                start += 1

    if current:
        chunks.append(current)

    return chunks


def format_telegram_section_headings(text: str) -> str:
    escaped = html.escape(text or "").replace("\r\n", "\n")
    for heading in _SECTION_HEADINGS:
        escaped_heading = html.escape(heading)
        escaped = re.sub(
            rf"(^|\n)({re.escape(escaped_heading)})(.*?)(?=\n|$)",
            lambda match: f"{match.group(1)}<b>{match.group(2)}</b>{match.group(3)}",
            escaped,
            flags=re.MULTILINE,
        )
    return escaped


def build_question_confirmation(text: str, limit: int = 300) -> str:
    normalized = " ".join((text or "").strip().split())
    if len(normalized) > limit:
        normalized = normalized[:limit].rstrip() + "…"
    return f"✅ Задан вопрос/тема: {normalized}"


def _remove_trailing_invitation(text: str) -> str:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return ""

    last = paragraphs[-1].lower()
    if last.startswith(_TRAILING_INVITATION_STARTS):
        paragraphs = paragraphs[:-1]

    return "\n\n".join(paragraphs)
