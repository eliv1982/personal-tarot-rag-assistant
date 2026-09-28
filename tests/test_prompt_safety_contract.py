from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_core.generation.prompts import (
    TAROT_GUARDRAIL_FALLBACK,
    TAROT_RAG_SYSTEM_PROMPT,
    build_rag_prompt,
)


def _card_doc(text: str = "The Fool suggests a fresh start.") -> dict:
    return {
        "text": text,
        "metadata": {"source_type": "card", "source_kind": "card", "section": "Upright Meaning"},
    }


def test_tarot_mode_activates_for_card_context_and_falls_back_to_guardrails():
    prompt = build_rag_prompt("Что означает эта карта?", [_card_doc()])

    assert TAROT_RAG_SYSTEM_PROMPT in prompt
    # No style/safety doc supplied -> the fixed guardrail fallback must be present.
    assert TAROT_GUARDRAIL_FALLBACK in prompt


def test_tarot_mode_uses_retrieved_safety_guidance_when_present():
    safety_doc = {
        "text": "Never state medical or legal outcomes as fact.",
        "metadata": {"source_type": "safety", "source_kind": "safety"},
    }
    style_doc = {
        "text": "Keep tone warm and reflective.",
        "metadata": {"source_type": "style", "source_kind": "style"},
    }
    prompt = build_rag_prompt("What does this card mean?", [_card_doc(), safety_doc, style_doc])

    assert "Never state medical or legal outcomes as fact." in prompt
    assert "Keep tone warm and reflective." in prompt


def test_non_tarot_context_uses_generic_grounded_prompt_not_tarot_mode():
    doc = {"text": "Some reference text.", "metadata": {"source_type": "law"}}
    prompt = build_rag_prompt("What does this mean?", [doc])

    assert TAROT_RAG_SYSTEM_PROMPT not in prompt
    assert "Insufficient basis" in prompt


def test_empty_context_does_not_crash_and_is_not_tarot_mode():
    prompt = build_rag_prompt("Some question with no retrieved context", [])

    assert TAROT_RAG_SYSTEM_PROMPT not in prompt
    assert "Insufficient basis" in prompt
