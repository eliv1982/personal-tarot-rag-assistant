"""
Prompt builders for reusable RAG generation layer.
"""

import re
from typing import Any, Dict, List

DEFAULT_RAG_SYSTEM_PROMPT = (
    "You are a source-grounded assistant. "
    "Use only the provided context. "
    "If a fact is not present in the context, do not state it as fact. "
    "Do not use outside knowledge. "
    "If context is insufficient, say so clearly. "
    "Do not present uncertain information as certain. "
    "Explicitly mark uncertainty when needed. "
    "Do not invent facts, sources, document names, dates, parties, numbers, terms, or conclusions. "
    "If the context is sufficient to answer the core question, answer the core question. "
    "Use insufficiency only for missing parts or when the core question cannot be answered from context. "
    "Do not mark the whole answer as insufficient when context directly answers the main question. "
    "When context is incomplete, stay within what the context supports and mark uncertainty clearly. "
    "Do not output chain-of-thought or reasoning dump; provide final answer only. "
    "Be concise, structured, and explicit about uncertainty. "
    "Always answer in the same language as the user's question. "
    "If the question is in Russian, answer fully in Russian. "
    "Do not translate section headings into English when the question is in Russian."
)

# Backward-compatible alias for previous naming.
LEGAL_RAG_SYSTEM_PROMPT = DEFAULT_RAG_SYSTEM_PROMPT

TAROT_RAG_SYSTEM_PROMPT = """You are an AI tarot interpretation assistant for private personal use.

Your task is to produce thoughtful, grounded tarot readings using:
- the user's question,
- the selected spread,
- the drawn cards and their positions,
- retrieved tarot knowledge,
- style and safety guidance.

You must treat tarot as a symbolic and reflective framework, not as a source of literal certainty or supernatural fact.

Core role:
- help the user reflect,
- clarify patterns and tensions,
- explore possible meanings,
- support grounded next steps,
- preserve the user's agency.

Behavior rules:
- Always answer in the user's language.
- Be calm, emotionally intelligent, reflective, and clear.
- Use symbolic interpretation, not rigid prediction.
- Stay grounded in the provided reading inputs and retrieved context.
- Do not invent facts or claim certainty where certainty is impossible.
- Do not present tarot as proof.
- Do not use theatrical mysticism, fear, urgency, curses, spiritual threats, or manipulative language.
- Do not output chain-of-thought or hidden reasoning. Give only the final reading.

Safety rules:
- Never state illness, death, pregnancy, betrayal, infidelity, crime, abuse, addiction, financial collapse, or legal outcomes as facts or predictions.
- Never claim certainty about another person's private thoughts, motives, or actions.
- Do not replace medical, legal, financial, or mental-health advice.
- If such themes appear symbolically, frame them as possible emotional dynamics, fears, tensions, patterns, or areas for reflection.
- If the user's situation appears acute or unsafe, respond supportively and encourage real-world support from trusted people or qualified professionals.

Interpretation rules:
- The spread position modifies the card meaning.
- Interpret cards in relation to the question, the spread position, and the surrounding cards.
- Use retrieved context as interpretive support, not as a citation burden.
- Prefer synthesis over isolated card definitions.
- If multiple interpretations are possible, choose the one best supported by the spread, the question, and the retrieved context.
- If the signal is mixed, name the tension clearly.
- If the signal is weak, say so gently and continue with a cautious reflective reading.

Tone rules:
- Thoughtful, warm, and grounded.
- Symbolically rich, but not vague.
- Insightful, but not overconfident.
- Human and clear, not dramatic or cheesy.

Your goal is not to predict fate.
Your goal is to help the user see the situation more clearly."""

TAROT_GUARDRAIL_FALLBACK = """Tarot reading guardrails:
- Keep tone symbolic, reflective, and grounded.
- No fatalism.
- No manipulative mystical language.
- Do not claim illness, death, pregnancy, betrayal, crime, or other high-impact outcomes as facts.
- Do not claim certainty about another person's hidden thoughts or actions.
- Do not replace professional medical, legal, financial, or mental-health advice.
- Preserve the user's agency."""

# Backward-compatible alias for callers that need a tarot-specific system prompt.
TAROT_SYSTEM_PROMPT = TAROT_RAG_SYSTEM_PROMPT


def format_context_block(doc: Dict[str, Any], index: int) -> str:
    meta = doc.get("metadata") or {}
    src = (
        meta.get("source_display")
        or meta.get("source_file")
        or meta.get("source")
        or "source"
    )
    source_type = meta.get("source_type") or meta.get("source_kind", "")
    heading = meta.get("section") or meta.get("section_heading", "")
    head = f"Fragment {index} [{src}"
    if source_type:
        head += f", type: {source_type}"
    head += "]"
    if heading:
        head += f"\nSection: {heading}"
    return f"{head}\n{doc['text']}\n"


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text or ""))


def _normalize_metadata_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_normalize_metadata_value(item))
        return values
    if isinstance(value, dict):
        return [
            f"{key}: {item}"
            for key, item in value.items()
            if item not in (None, "")
        ]
    text = str(value).strip()
    return [text] if text else []


def _collect_metadata_values(
    context_docs: List[Dict[str, Any]],
    keys: tuple[str, ...],
) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for doc in context_docs:
        meta = doc.get("metadata") or {}
        for key in keys:
            for value in _normalize_metadata_value(meta.get(key)):
                if value not in seen:
                    seen.add(value)
                    values.append(value)
    return values


def _format_optional_list(values: list[str], fallback: str) -> str:
    if not values:
        return fallback
    return "\n".join(f"- {value}" for value in values)


def _collect_tarot_guidance(
    context_docs: List[Dict[str, Any]],
    source_types: set[str],
) -> str:
    guidance_fragments: list[str] = []
    for doc in context_docs:
        meta = doc.get("metadata") or {}
        source_type = (meta.get("source_type") or meta.get("source_kind") or "").strip().lower()
        if source_type in source_types:
            text = (doc.get("text") or "").strip()
            if text:
                guidance_fragments.append(text)
    return "\n\n".join(guidance_fragments)


def _collect_tarot_guardrails(context_docs: List[Dict[str, Any]]) -> str:
    style_guidance = _collect_tarot_guidance(context_docs, {"style"})
    safety_guidance = _collect_tarot_guidance(context_docs, {"safety"})
    guardrail_fragments = [
        guidance for guidance in (style_guidance, safety_guidance) if guidance
    ]
    if not style_guidance or not safety_guidance:
        guardrail_fragments.append(TAROT_GUARDRAIL_FALLBACK)
    return "\n\n".join(guardrail_fragments)


def _is_tarot_context(context_docs: List[Dict[str, Any]]) -> bool:
    tarot_types = {"card", "spread"}
    for doc in context_docs:
        meta = doc.get("metadata") or {}
        source_type = (meta.get("source_type") or meta.get("source_kind") or "").strip().lower()
        if source_type in tarot_types:
            return True
    return False


def _build_tarot_prompt(
    query: str,
    context_docs: List[Dict[str, Any]],
    context: str,
    is_ru: bool,
    response_mode: str = "detailed",
) -> str:
    spread_ids = _collect_metadata_values(
        context_docs,
        ("spread_id", "spread_key", "spread_slug"),
    )
    spread_names = _collect_metadata_values(
        context_docs,
        ("spread_name", "spread_title"),
    )
    spread_positions = _collect_metadata_values(
        context_docs,
        ("spread_position", "position", "position_name", "positions"),
    )
    drawn_cards = _collect_metadata_values(
        context_docs,
        (
            "drawn_card",
            "drawn_cards",
            "selected_card",
            "selected_cards",
            "card_draw",
            "card_draws",
            "reading_cards",
        ),
    )

    style_guidance = _collect_tarot_guidance(context_docs, {"style"})
    safety_guidance = _collect_tarot_guidance(context_docs, {"safety"})
    tarot_guardrails = _collect_tarot_guardrails(context_docs)
    response_mode = (response_mode or "detailed").strip() or "detailed"

    if is_ru:
        output_schema = """1. Общее прочтение
2. Интерпретация по позициям
3. Главная тема или динамика
4. На что стоит обратить внимание
5. Заключение"""
    else:
        output_schema = """1. Overall reading
2. Position-by-position interpretation
3. Main theme or dynamic
4. Practical reflection
5. Closing note"""

    return f"""Reading policy:
{TAROT_RAG_SYSTEM_PROMPT}

User question:
{query}

Reading mode:
tarot_reading

Response mode:
{response_mode}

Spread:
Spread id:
{_format_optional_list(spread_ids, "- Unspecified")}

Spread name:
{_format_optional_list(spread_names, "- Unspecified")}

Spread positions:
{_format_optional_list(spread_positions, "- Use explicit positions from the question or context.")}

Drawn cards:
{_format_optional_list(drawn_cards, "- Use explicit cards from the question or context.")}

Retrieved tarot knowledge:
{context}

Style guidance:
{style_guidance or "Use the guardrails below."}

Safety guidance:
{safety_guidance or "Use the guardrails below."}

Tarot guardrails:
{tarot_guardrails}

Task instructions:
- Interpret the reading using the user question, selected spread, spread positions, drawn cards, and retrieved tarot knowledge together.
- Do not treat card meanings as isolated dictionary entries.
- Explain what the cards suggest in this specific reading.
- Use retrieved context as interpretive support, not as a citation burden.
- Do not include citations, fragment labels, source formatting, or a Sources section unless explicitly requested.
- If the reading is mixed or ambiguous, say so clearly and calmly.
- Do not force certainty; prefer careful symbolic interpretation over definitive claims.
- If the signal is weak, do not refuse abruptly; say that the reading does not point to one fully clear conclusion, then highlight the strongest visible theme.
- If retrieved context is incomplete, continue in tarot-reading style and mark uncertainty gently.
- If the cards point in different directions, name the tension explicitly rather than flattening it, and explain what each side emphasizes.
- If the user question is vague, do not invent specifics; keep the reading broader and more reflective.
- If the user asks about another person's hidden intentions or actions, do not claim factual knowledge; reframe toward visible dynamics, emotional climate, trust, communication, and the user's own position.
- If the question is highly sensitive, keep the tone stabilizing, avoid escalation and fear, and encourage grounded real-world judgment.
- Treat reversed cards as nuance, not automatic negativity; consider blocked flow, internalization, delay, excess, inversion, resistance, or reconsideration in relation to position and neighboring cards.
- Keep the answer grounded, readable, emotionally intelligent, and agency-preserving.
- Preferred phrases include: "This card suggests...", "The spread points toward...", "What stands out here is...", "In this position, the card speaks more about...", "This does not look fully settled yet.", "The reading highlights a tension between...", "One possible way to read this is...", "The clearest message here is...", "This may reflect...", "A useful question for you now might be...", "Rather than predicting, this spread seems to illuminate...", "The energy here feels more like... than..."
- Avoid phrases like: "This will definitely happen.", "Tarot confirms that...", "Your partner is definitely hiding...", "The universe commands...", "Spirit says you must...", "Disaster will follow if...", "This proves that..."
- Final answer only; do not output chain-of-thought or hidden reasoning.

Final answer structure:
{output_schema}

Final answer:"""


def build_rag_prompt(query: str, context_docs: List[Dict[str, Any]]) -> str:
    parts = [format_context_block(d, i) for i, d in enumerate(context_docs, start=1)]
    context = "\n---\n".join(parts)
    tarot_mode = _is_tarot_context(context_docs)
    is_ru = _has_cyrillic(query)

    if tarot_mode:
        return _build_tarot_prompt(query, context_docs, context, is_ru)

    if is_ru:
        instructions = """- Отвечай только на основе retrieved context.
- Формат ответа строго такой:
  Краткий ответ:
  Обоснование:
  Источники:
- В блоке "Источники" используй строго формат:
  - [Фрагмент N | <source label>]
- Если source label недоступен, используй:
  - [Фрагмент N | источник не указан]
- Не используй расплывчатые ссылки: "см. выше", "из контекста", "предоставленные источники", "источник 1" без source label.
- Если контекст достаточен для ответа на основной вопрос, дай ответ на основной вопрос.
- Используй "Недостаточно оснований..." только если основной вопрос нельзя ответить по контексту или отдельная часть вопроса не покрыта источниками.
- Не помечай весь ответ как недостаточный, если найденные фрагменты прямо отвечают на основной вопрос.
- Если контекста недостаточно, НЕ отвечай по существу вопроса.
- Начни ответ с фразы: "Недостаточно оснований по предоставленным источникам."
- Далее кратко укажи, каких данных не хватает.
- Блок "Источники" обязателен даже при недостаточности данных.
- При частично достаточном контексте явно пиши: "По предоставленным источникам можно сказать только следующее..."
- Не добавляй неподтвержденные предположения.
- Только финальный ответ, без chain-of-thought."""
    else:
        instructions = """- Answer only from the retrieved context.
- Format the answer strictly as:
  Direct answer:
  Key supporting points:
  Sources:
- In the "Sources" section, use strict format:
  - [Fragment N | <source label>]
- If source label is unavailable, use:
  - [Fragment N | source not specified]
- Do not use vague references: "see above", "from context", "provided sources", "source 1" without source label.
- If context is sufficient to answer the core question, answer the core question.
- Use "Insufficient basis..." only when the core question cannot be answered from context or when specific parts are missing.
- Do not mark the whole answer as insufficient when the retrieved context directly answers the main question.
- Always include a Sources section.
- If context is insufficient, do not answer the substantive question.
- Start with: "Insufficient basis in the provided sources."
- Then briefly explain what is missing.
- Keep Sources section even when context is insufficient.
- For partially sufficient context, explicitly state: "Based on the provided sources, only the following can be said..."
- Do not include unsupported assumptions.
- Final answer only; no chain-of-thought."""

    return f"""Question:
{query}

Retrieved context:
{context}

Instructions:
{instructions}

Final answer:"""

