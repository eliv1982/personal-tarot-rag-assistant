"""
Vector store module based on ChromaDB.
Supports corpus loading, chunking, embedding, and similarity search.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
import time
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError

from app_core.llm.client import get_llm_client

PROJECT_ROOT = Path(__file__).resolve().parents[2]
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

_STATUTE_BOUNDARY = re.compile(
    r"(?m)^(?=(?:§\s*\d+(?:\.\d+)?[\.\s]|Статья\s+\d+))"
)
_TITLE_RE = re.compile(r"^#\s+(.+)$", flags=re.MULTILINE)
_METADATA_BLOCK_RE = re.compile(r"^##\s+Metadata\s*\n(.*?)(?=\n##\s+|\Z)", flags=re.MULTILINE | re.DOTALL)
_SECTION_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
_LOOKUP_NON_WORD_RE = re.compile(r"[^0-9a-zа-я\s]+")


def _normalize_lookup_text(text: str) -> str:
    normalized = (text or "").lower().replace("ё", "е")
    normalized = _LOOKUP_NON_WORD_RE.sub(" ", normalized)
    return " ".join(normalized.split())


def _build_tarot_card_alias_map() -> Dict[str, str]:
    alias_to_slug: Dict[str, str] = {}
    suits = {
        "cups": ["cups", "кубков", "чаш"],
        "pentacles": ["pentacles", "пентаклей", "монет", "дисков"],
        "swords": ["swords", "мечей"],
        "wands": ["wands", "жезлов", "посохов"],
    }
    ranks = [
        ("ace", ["ace", "туз"]),
        ("two", ["two", "2", "двоика", "двойка"]),
        ("three", ["three", "3", "троика", "тройка"]),
        ("four", ["four", "4", "четверка"]),
        ("five", ["five", "5", "пятерка"]),
        ("six", ["six", "6", "шестерка"]),
        ("seven", ["seven", "7", "семерка"]),
        ("eight", ["eight", "8", "восьмерка"]),
        ("nine", ["nine", "9", "девятка"]),
        ("ten", ["ten", "10", "десятка"]),
        ("page", ["page", "паж"]),
        ("knight", ["knight", "рыцарь"]),
        ("queen", ["queen", "королева"]),
        ("king", ["king", "король"]),
    ]
    for rank_en, rank_aliases in ranks:
        for suit_en, suit_aliases in suits.items():
            slug = f"{rank_en}_of_{suit_en}"
            for rank_alias in rank_aliases:
                for suit_alias in suit_aliases:
                    alias_to_slug[_normalize_lookup_text(f"{rank_alias} {suit_alias}")] = slug
                    alias_to_slug[_normalize_lookup_text(f"{rank_alias} of {suit_alias}")] = slug

    major_aliases = {
        "death": ["death", "смерть"],
        "the_world": ["the world", "world", "мир", "карта мир"],
    }
    for slug, aliases in major_aliases.items():
        for alias in aliases:
            alias_to_slug[_normalize_lookup_text(alias)] = slug
    return alias_to_slug


_TAROT_CARD_ALIAS_TO_SLUG = _build_tarot_card_alias_map()
_MAJOR_SLUG_TO_SOURCE_FILE = {
    "death": "13_death.md",
    "the_world": "21_the_world.md",
}

# Hard safety cap for a single "card" chunk (source_kind == "card"). Card
# documents are indexed as one semantic chunk each so Light/Shadow meanings
# stay together; this bounds how large that single chunk may grow (current
# card files top out around ~2000 chars). Independent from RAG_CHUNK_SIZE,
# which governs generic (non-card) chunking.
CARD_CHUNK_HARD_LIMIT = 6000


class VectorStore:
    """Векторное хранилище на основе ChromaDB."""

    def __init__(
        self,
        collection_name: str = "rag_collection",
        persist_directory: Optional[str] = None,
    ):
        self.collection_name = collection_name
        if persist_directory is None:
            persist_directory = str(PROJECT_ROOT / "runtime" / "chroma_db")
        self.persist_directory = persist_directory
        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_directory)

        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"Коллекция '{collection_name}' загружена. Документов: {self.collection.count()}")
        except Exception:
            self.collection = self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            print(f"Создана новая коллекция '{collection_name}'")

        self.openai_client = get_llm_client()
        self.embedding_model = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        self.chunk_size = int(os.getenv("RAG_CHUNK_SIZE", "800"))
        self.chunk_overlap = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
        self.min_chunk_len = int(os.getenv("RAG_MIN_CHUNK_LEN", "80"))

        max_distance_raw = (os.getenv("RAG_MAX_DISTANCE") or "").strip()
        self.max_distance: Optional[float] = float(max_distance_raw) if max_distance_raw else None

    def _split_sentences(self, text: str) -> List[str]:
        try:
            from pysbd import Segmenter

            segmenter = Segmenter(language="ru", clean=False)
            return [s.strip() for s in segmenter.segment(text) if s.strip()]
        except Exception:
            return self._split_sentences_regex(text)

    def _split_sentences_regex(self, text: str) -> List[str]:
        parts = re.split(r"([.!?]+\s+)", text)
        full: List[str] = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts):
                full.append((parts[i] + parts[i + 1]).strip())
                i += 2
            else:
                if parts[i].strip():
                    full.append(parts[i].strip())
                i += 1
        return [s for s in full if s]

    def _get_overlap_text(self, text: str, overlap_size: int) -> str:
        if len(text) <= overlap_size:
            return text
        overlap_candidate = text[-overlap_size:]
        sentence_starts = [". ", "! ", "? ", "\n"]
        best_start = 0
        for delimiter in sentence_starts:
            pos = overlap_candidate.find(delimiter)
            if pos != -1 and pos > best_start:
                best_start = pos + len(delimiter)
        if best_start > 0:
            return overlap_candidate[best_start:].strip()
        return overlap_candidate.strip()

    def _split_long_block(self, paragraph: str, chunk_size: int, overlap: int) -> List[str]:
        sentences = self._split_sentences(paragraph)
        chunks: List[str] = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= chunk_size:
                current = (current + " " + sentence).strip() if current else sentence
            else:
                if current:
                    chunks.append(current)
                    overlap_text = self._get_overlap_text(current, overlap)
                    current = (overlap_text + " " + sentence).strip() if overlap_text else sentence
                else:
                    current = sentence
        if current:
            chunks.append(current)
        return chunks

    def _chunk_semantic(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        paragraphs = text.split("\n\n")
        chunks: List[str] = []
        current = ""
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(current) + len(paragraph) + 2 <= chunk_size:
                current = current + "\n\n" + paragraph if current else paragraph
            elif current:
                chunks.append(current)
                overlap_text = self._get_overlap_text(current, overlap)
                current = overlap_text + "\n\n" + paragraph if overlap_text else paragraph
            else:
                if len(paragraph) > chunk_size:
                    sent_chunks = self._split_long_block(paragraph, chunk_size, overlap)
                    if sent_chunks:
                        chunks.extend(sent_chunks[:-1])
                        current = sent_chunks[-1]
                else:
                    current = paragraph
        if current:
            chunks.append(current)
        return [c for c in chunks if len(c) >= self.min_chunk_len]

    def _split_oversized_chunk(self, text: str, max_len: int, overlap: int) -> List[str]:
        cleaned = (text or "").strip()
        if not cleaned:
            return []
        if max_len <= 0:
            return [cleaned]
        if len(cleaned) <= max_len:
            return [cleaned]

        overlap = max(0, min(overlap, max_len // 2)) if max_len > 1 else 0
        step = max(1, max_len - overlap)
        min_natural_cut = max(1, int(max_len * 0.5))
        separators = ["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "]

        chunks: List[str] = []
        start = 0
        total_len = len(cleaned)

        while start < total_len:
            end = min(start + max_len, total_len)
            if end >= total_len:
                tail = cleaned[start:].strip()
                if tail:
                    chunks.append(tail)
                break

            window = cleaned[start:end]
            cut = -1
            for sep in separators:
                idx = window.rfind(sep)
                if idx >= min_natural_cut:
                    cut = start + idx + len(sep)
                    break

            if cut <= start:
                cut = end

            piece = cleaned[start:cut].strip()
            if piece:
                chunks.append(piece)
            else:
                cut = end

            next_start = max(0, cut - overlap)
            if next_start <= start:
                next_start = start + step
            start = next_start

        return chunks

    def _max_len_for_row(self, meta: Dict[str, str]) -> int:
        if meta.get("source_kind") == "card":
            return max(self.chunk_size, CARD_CHUNK_HARD_LIMIT)
        return self.chunk_size

    def _enforce_hard_chunk_limit(
        self, rows: List[Tuple[str, Dict[str, str]]], overlap: int
    ) -> List[Tuple[str, Dict[str, str]]]:
        out: List[Tuple[str, Dict[str, str]]] = []
        for doc_text, meta in rows:
            max_len = self._max_len_for_row(meta)
            if max_len <= 0 or len(doc_text) <= max_len:
                out.append((doc_text, meta))
                continue

            split_parts = self._split_oversized_chunk(doc_text, max_len, overlap)
            if not split_parts:
                continue

            for idx, part in enumerate(split_parts):
                if not part:
                    continue
                new_meta = dict(meta)
                new_meta["hard_split_index"] = str(idx)
                out.append((part, new_meta))

        return out

    def _split_statute_sections(self, text: str) -> List[str]:
        parts = _STATUTE_BOUNDARY.split(text)
        parts = [p.strip() for p in parts if p.strip()]
        if len(parts) <= 1:
            stripped = text.strip()
            return [stripped] if stripped else []
        return parts

    def _section_heading(self, section: str, max_len: int = 160) -> str:
        line = section.strip().split("\n", 1)[0].strip()
        if len(line) > max_len:
            return line[:max_len] + "…"
        return line

    def _split_markdown_sections(self, text: str) -> List[Tuple[str, str]]:
        lines = (text or "").splitlines()
        if not lines:
            return []

        sections: List[Tuple[str, str]] = []
        default_title = self._extract_markdown_title(text) or "Document"
        current_title = default_title
        current_buffer: List[str] = []

        for line in lines:
            heading_match = _SECTION_HEADING_RE.match(line.strip())
            if heading_match:
                if current_buffer and any(item.strip() for item in current_buffer):
                    sections.append((current_title, "\n".join(current_buffer).strip()))
                current_title = heading_match.group(2).strip()
                current_buffer = [line]
                continue
            current_buffer.append(line)

        if current_buffer and any(item.strip() for item in current_buffer):
            sections.append((current_title, "\n".join(current_buffer).strip()))

        return sections

    def _kind_label(self, source_kind: str) -> str:
        return {
            "law": "закон РФ",
            "rules": "правила (URDG)",
            "case_law_summary": "обзор судебной практики",
            "card": "tarot card",
            "spread": "tarot spread",
            "style": "tarot style",
            "safety": "tarot safety",
        }.get(source_kind, source_kind)

    @staticmethod
    def _extract_markdown_title(text: str) -> str:
        match = _TITLE_RE.search(text or "")
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_markdown_metadata(text: str) -> Dict[str, str]:
        block = _METADATA_BLOCK_RE.search(text or "")
        if not block:
            return {}
        parsed: Dict[str, str] = {}
        for line in block.group(1).splitlines():
            clean = line.strip()
            if not clean or ":" not in clean:
                continue
            key, value = clean.split(":", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    @staticmethod
    def _is_tarot_source_kind(source_kind: str) -> bool:
        return source_kind in {"card", "spread", "style", "safety"}

    def _build_base_metadata(
        self,
        source: str,
        source_display: str,
        source_kind: str,
        doc_type: str,
        source_path: str,
        text: str,
    ) -> Dict[str, str]:
        metadata_block = self._extract_markdown_metadata(text)
        title = self._extract_markdown_title(text)
        base_meta: Dict[str, str] = {
            "source": source,
            "source_display": source_display,
            "source_kind": source_kind,
            "doc_type": doc_type,
            "source_path": source_path,
            "relative_path": source_path,
            "source_file": Path(source_path).name if source_path else "",
            "doc_title": title,
        }
        if self._is_tarot_source_kind(source_kind):
            base_meta["source_type"] = source_kind
            if source_kind == "card":
                base_meta["card_name"] = metadata_block.get("card_name", title)
                base_meta["arcana"] = metadata_block.get("arcana", "")
                base_meta["suit"] = metadata_block.get("suit", "")
                base_meta["rank"] = metadata_block.get("rank", "")
                base_meta["slug"] = metadata_block.get("slug", "")
            elif source_kind == "spread":
                base_meta["spread_id"] = metadata_block.get("spread_id", "")
                base_meta["category"] = metadata_block.get("category", "")
        return base_meta

    def _build_chunks_for_file(
        self,
        text: str,
        source: str,
        source_display: str,
        source_kind: str,
        doc_type: str,
        source_path: str = "",
    ) -> List[Tuple[str, Dict[str, str]]]:
        chunk_size = self.chunk_size
        overlap = self.chunk_overlap
        kind_label = self._kind_label(source_kind)
        is_tarot = self._is_tarot_source_kind(source_kind)
        if is_tarot:
            prefix_template = ""
        else:
            # Keep legacy behavior with a source prefix for non-tarot corpora.
            prefix_template = f"[Источник: {source_display} | {kind_label}]\n[Фрагмент: {{heading}}]\n\n"
        base_meta = self._build_base_metadata(
            source=source,
            source_display=source_display,
            source_kind=source_kind,
            doc_type=doc_type,
            source_path=source_path,
            text=text,
        )

        if doc_type == "statute":
            sections_with_titles: List[Tuple[str, str]] = [
                (self._section_heading(section), section)
                for section in self._split_statute_sections(text)
            ]
        elif source_kind == "card":
            # A card document is indexed as a single semantic chunk so that
            # Light/Shadow and other sections of the same card stay together.
            # The hard safety cap below (not RAG_CHUNK_SIZE) still applies to
            # oversized files via _enforce_hard_chunk_limit in load_corpus().
            stripped_text = text.strip()
            heading = self._extract_markdown_title(text) or "Document"
            if stripped_text and len(stripped_text) >= self.min_chunk_len:
                meta = {
                    **base_meta,
                    "section_heading": heading,
                    "section": heading,
                    "subchunk_index": "",
                }
                return [(stripped_text, meta)]
            return []
        elif is_tarot:
            sections_with_titles = self._split_markdown_sections(text)
        else:
            stripped_text = text.strip()
            sections_with_titles = (
                [(self._extract_markdown_title(text) or "Document", stripped_text)]
                if stripped_text
                else []
            )

        out: List[Tuple[str, Dict[str, str]]] = []
        for section_title, section in sections_with_titles:
            heading = section_title or self._section_heading(section)
            prefix = prefix_template.format(heading=heading) if prefix_template else ""
            max_body_len = max(1, chunk_size - len(prefix))
            if len(section) <= chunk_size:
                meta = {
                    **base_meta,
                    "section_heading": heading,
                    "section": heading,
                    "subchunk_index": "",
                }
                for body_part in self._split_oversized_chunk(section, max_body_len, overlap):
                    doc_text = f"{prefix}{body_part}"
                    if len(doc_text) < self.min_chunk_len:
                        continue
                    out.append((doc_text, meta))
                continue

            subchunks = self._chunk_semantic(section, chunk_size, overlap)
            for i, sub in enumerate(subchunks):
                body = sub.strip()
                if len(body) < self.min_chunk_len:
                    continue
                meta = {
                    **base_meta,
                    "section_heading": heading,
                    "section": heading,
                    "subchunk_index": str(i),
                }
                for body_part in self._split_oversized_chunk(body, max_body_len, overlap):
                    doc_text = f"{prefix}{body_part}"
                    if len(doc_text) < self.min_chunk_len:
                        continue
                    out.append((doc_text, meta))
        return out

    def _resolve_path(self, path: Path, base_dir: Path) -> Path:
        p = Path(path)
        if p.is_absolute():
            return p
        return (base_dir / p).resolve()

    def load_corpus(
        self,
        corpus_entries: List[Dict[str, Any]],
        base_dir: Optional[Path] = None,
    ) -> None:
        """
        Загрузка нескольких файлов с метаданными. Пропускает загрузку, если коллекция не пуста.
        corpus_entries: path (Path | str), source, source_display, source_kind, doc_type
        """
        if self.collection.count() > 0:
            print("Документы уже загружены в коллекцию")
            return

        effective_embed_batch_size = max(1, int(os.getenv("RAG_EMBED_BATCH_SIZE", "16")))
        print(
            "[INFO] Effective config: "
            f"embedding_model={self.embedding_model} "
            f"chunk_size={self.chunk_size} "
            f"chunk_overlap={self.chunk_overlap} "
            f"min_chunk_len={self.min_chunk_len} "
            f"embed_batch_size={effective_embed_batch_size}"
        )

        base = base_dir or Path(__file__).resolve().parent
        all_rows: List[Tuple[str, Dict[str, str]]] = []

        for entry in corpus_entries:
            raw_path = entry["path"]
            path = self._resolve_path(Path(raw_path), base)
            if not path.exists():
                raise FileNotFoundError(f"Файл корпуса не найден: {path}")

            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

            rows = self._build_chunks_for_file(
                text,
                source=str(entry["source"]),
                source_display=str(entry["source_display"]),
                source_kind=str(entry.get("source_kind", "unknown")),
                doc_type=str(entry.get("doc_type", "overview")),
                source_path=str(entry.get("path", "")),
            )
            print(f"  {path.name}: {len(rows)} чанков")
            all_rows.extend(rows)

        if not all_rows:
            raise ValueError("Корпус пуст после нарезки")

        before_total = len(all_rows)
        before_max_len = max((len(doc) for doc, _ in all_rows), default=0)
        print(
            "[INFO] Chunk summary before hard-limit pass: "
            f"total={before_total} max_len={before_max_len}"
        )

        all_rows = self._enforce_hard_chunk_limit(all_rows, overlap=self.chunk_overlap)

        if not all_rows:
            raise ValueError("Корпус пуст после hard-limit pass")

        after_total = len(all_rows)
        after_max_len = max((len(doc) for doc, _ in all_rows), default=0)
        print(
            "[INFO] Chunk summary after hard-limit pass: "
            f"total={after_total} max_len={after_max_len}"
        )

        print(f"Всего чанков: {after_total}. Создание эмбеддингов…")
        documents = [r[0] for r in all_rows]
        metadatas = [r[1] for r in all_rows]
        embeddings = self._create_embeddings_batched(documents)

        ids = [f"doc_{i}" for i in range(len(documents))]
        batch = 100
        for start in range(0, len(documents), batch):
            end = min(start + batch, len(documents))
            self.collection.add(
                ids=ids[start:end],
                documents=documents[start:end],
                embeddings=embeddings[start:end],
                metadatas=metadatas[start:end],
            )
            print(f"  В Chroma записано {end}/{len(documents)}")

        print(f"Загружено {len(documents)} фрагментов в '{self.collection_name}'")

    def load_documents(self, file_path: str, base_dir: Optional[Path] = None) -> None:
        """Обратная совместимость: один файл как корпус из одного источника."""
        base = base_dir or Path(__file__).resolve().parent
        p = self._resolve_path(Path(file_path), base)
        self.load_corpus(
            [
                {
                    "path": p,
                    "source": "single_file",
                    "source_display": p.name,
                    "source_kind": "unknown",
                    "doc_type": "overview",
                }
            ],
            base_dir=base,
        )

    @staticmethod
    def _embedding_connection_hint(exc: BaseException) -> str:
        cause = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
        tail = f" Детали: {cause}" if cause else ""
        return (
            "Не удалось связаться с API OpenAI (Connection error / таймаут). "
            "Проверьте интернет, VPN (если API недоступен из вашей сети), файрвол и корпоративный прокси. "
            "Для прокси задайте HTTPS_PROXY в системе или в PowerShell: "
            "$env:HTTPS_PROXY='http://127.0.0.1:ПОРТ'. "
            "Можно увеличить OPENAI_TIMEOUT (сек) и уменьшить RAG_EMBED_BATCH_SIZE. "
            "При использовании зеркала/шлюза укажите OPENAI_BASE_URL."
            + tail
        )

    def _create_embeddings_batched(self, texts: List[str], batch_size: Optional[int] = None) -> List[List[float]]:
        if batch_size is None:
            batch_size = int(os.getenv("RAG_EMBED_BATCH_SIZE", "16"))
        batch_size = max(1, batch_size)
        embed_retries = max(1, int(os.getenv("OPENAI_EMBED_RETRIES", "5")))
        all_emb: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i: i + batch_size]
            last_err: Optional[BaseException] = None
            for attempt in range(embed_retries):
                try:
                    response = self.openai_client.embeddings.create(
                        input=batch,
                        model=self.embedding_model,
                    )
                    by_index = sorted(response.data, key=lambda d: d.index)
                    all_emb.extend([d.embedding for d in by_index])
                    break
                except (APIConnectionError, APITimeoutError) as e:
                    last_err = e
                    wait = min(30, 2**attempt)
                    print(
                        f"  Сеть/API: попытка {attempt + 1}/{embed_retries} не удалась, "
                        f"пауза {wait} с… ({e.__class__.__name__})"
                    )
                    time.sleep(wait)
                except Exception:
                    batch_lengths = [len(item) for item in batch]
                    max_batch_len = max(batch_lengths) if batch_lengths else 0
                    min_batch_len = min(batch_lengths) if batch_lengths else 0
                    print(
                        "[ERROR] Embedding batch failed: "
                        f"start={i} batch_size={len(batch)} "
                        f"min_item_len={min_batch_len} max_item_len={max_batch_len} "
                        f"model={self.embedding_model}"
                    )
                    raise
            else:
                raise RuntimeError(self._embedding_connection_hint(last_err)) from last_err
        return all_emb

    def _create_embedding(self, text: str) -> List[float]:
        response = self.openai_client.embeddings.create(
            input=text,
            model=self.embedding_model,
        )
        return response.data[0].embedding

    @staticmethod
    def _detect_tarot_card_slugs(query: str) -> List[str]:
        """Detect card slugs from RU/EN aliases in user query."""
        normalized = _normalize_lookup_text(query)
        if not normalized:
            return []
        slugs: List[str] = []
        seen: set[str] = set()
        for alias, slug in _TAROT_CARD_ALIAS_TO_SLUG.items():
            if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", normalized):
                if slug not in seen:
                    seen.add(slug)
                    slugs.append(slug)
        return slugs

    @staticmethod
    def _rerank_with_exact_card_match(
        documents: List[Dict[str, Any]],
        detected_slugs: List[str],
    ) -> List[Dict[str, Any]]:
        """Boost card docs that match detected slug path/file name."""
        if not detected_slugs:
            return documents
        def _is_exact(doc: Dict[str, Any]) -> bool:
            return bool(VectorStore._match_exact_slug(doc, detected_slugs))

        ranked = list(enumerate(documents))
        ranked.sort(key=lambda item: (0 if _is_exact(item[1]) else 1, item[0]))
        return [doc for _, doc in ranked]

    @staticmethod
    def _source_file_for_slug(slug: str) -> str:
        return _MAJOR_SLUG_TO_SOURCE_FILE.get(slug, f"{slug}.md")

    @staticmethod
    def _match_exact_slug(doc: Dict[str, Any], detected_slugs: List[str]) -> Optional[str]:
        meta = doc.get("metadata") or {}
        relative_path = str(meta.get("relative_path") or meta.get("source_path") or "").lower()
        source_file = str(meta.get("source_file") or "").lower()
        meta_slug = str(meta.get("slug") or "").lower()
        for slug in detected_slugs:
            source_token = VectorStore._source_file_for_slug(slug).lower()
            if source_token in relative_path or source_token in source_file or meta_slug == slug:
                return slug
        return None

    def _fetch_exact_card_backfill_docs(
        self,
        missing_slugs: List[str],
        limit_per_slug: int = 2,
    ) -> List[Dict[str, Any]]:
        """Fetch 1-2 chunks by exact source_file when semantic results missed a card."""
        out: List[Dict[str, Any]] = []
        for slug in missing_slugs:
            source_file = self._source_file_for_slug(slug)
            fetched = self.collection.get(
                where={"source_file": source_file},
                include=["documents", "metadatas"],
                limit=max(1, limit_per_slug),
            )
            ids = fetched.get("ids") or []
            docs = fetched.get("documents") or []
            metas = fetched.get("metadatas") or []
            for i, doc_id in enumerate(ids):
                meta = dict(metas[i] or {}) if i < len(metas) else {}
                meta["_exact_backfill"] = True
                out.append(
                    {
                        "id": doc_id,
                        "text": docs[i] if i < len(docs) else "",
                        "distance": None,
                        "metadata": meta,
                    }
                )
        return out

    @staticmethod
    def _apply_diversity_cap(
        documents: List[Dict[str, Any]],
        detected_slugs: List[str],
        top_k: int,
        max_exact_per_slug: int = 3,
    ) -> List[Dict[str, Any]]:
        """Keep exact-card hits high, but avoid filling output with one card only."""
        selected: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        exact_counts: Dict[str, int] = {slug: 0 for slug in detected_slugs}

        for doc in documents:
            if len(selected) >= top_k:
                break
            doc_id = str(doc.get("id") or "")
            if doc_id and doc_id in seen_ids:
                continue
            matched_slug = VectorStore._match_exact_slug(doc, detected_slugs)
            if matched_slug and exact_counts.get(matched_slug, 0) >= max_exact_per_slug:
                continue
            selected.append(doc)
            if doc_id:
                seen_ids.add(doc_id)
            if matched_slug:
                exact_counts[matched_slug] = exact_counts.get(matched_slug, 0) + 1
        return selected

    @staticmethod
    def _filter_by_max_distance(
        documents: List[Dict[str, Any]], max_distance: Optional[float]
    ) -> List[Dict[str, Any]]:
        """
        Drop candidates whose cosine distance exceeds max_distance.

        Documents with distance=None (e.g. exact-slug backfill hits fetched
        by metadata rather than similarity) are not evaluated against the
        threshold and always pass through.
        """
        if max_distance is None:
            return documents
        return [
            doc
            for doc in documents
            if doc.get("distance") is None or doc["distance"] <= max_distance
        ]

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_embedding = self._create_embedding(query)
        detected_slugs = self._detect_tarot_card_slugs(query)
        n = min(top_k, max(1, self.collection.count()))
        if detected_slugs:
            n = min(max(top_k, 30), max(1, self.collection.count()))
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
        )
        documents: List[Dict[str, Any]] = []
        if results["documents"] and len(results["documents"][0]) > 0:
            for i in range(len(results["documents"][0])):
                meta = {}
                if results.get("metadatas") and results["metadatas"][0]:
                    meta = dict(results["metadatas"][0][i] or {})
                documents.append(
                    {
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "distance": results["distances"][0][i] if results.get("distances") else None,
                        "metadata": meta,
                    }
                )
        documents = self._filter_by_max_distance(documents, self.max_distance)
        if detected_slugs:
            documents = self._rerank_with_exact_card_match(documents, detected_slugs)
            found_slugs = {
                slug for slug in detected_slugs if any(self._match_exact_slug(doc, [slug]) for doc in documents)
            }
            missing_slugs = [slug for slug in detected_slugs if slug not in found_slugs]
            if missing_slugs:
                backfilled = self._fetch_exact_card_backfill_docs(missing_slugs, limit_per_slug=2)
                documents = backfilled + documents
            documents = self._rerank_with_exact_card_match(documents, detected_slugs)
            return self._apply_diversity_cap(documents, detected_slugs, top_k=top_k, max_exact_per_slug=3)
        return documents[:top_k]

    def get_collection_stats(self) -> Dict[str, Any]:
        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "persist_directory": self.persist_directory,
            "embedding_model": self.embedding_model,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }


if __name__ == "__main__":
    import sys

    if not (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")):
        print("Ошибка: установите переменную окружения LLM_API_KEY (или OPENAI_API_KEY)")
        sys.exit(1)

    from app_core.config.knowledge import default_corpus_entries

    vs = VectorStore(collection_name="test_collection")
    if vs.collection.count() == 0:
        vs.load_corpus(default_corpus_entries())

    r = vs.search("What is the core message of The Fool card?", top_k=4)
    for i, doc in enumerate(r, 1):
        print(f"\n{i}. {doc['metadata'].get('source_display', '')} | {doc['text'][:180]}…")

