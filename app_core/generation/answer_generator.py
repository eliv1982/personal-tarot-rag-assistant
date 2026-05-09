"""
LLM answer generation helpers for reusable RAG core.
"""

import logging

from openai import BadRequestError

from app_core.generation.prompts import DEFAULT_RAG_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def _uses_max_completion_tokens(model: str) -> bool:
    normalized = (model or "").strip().lower()
    return normalized.startswith("gpt-5")


def _build_token_limit_kwargs(model: str, max_tokens: int) -> dict:
    if _uses_max_completion_tokens(model):
        return {"max_completion_tokens": max_tokens}
    return {"max_tokens": max_tokens}


def _unsupported_max_tokens_use_max_completion_tokens(exc: BaseException) -> bool:
    """
    Detect OpenAI 400 where the model rejects max_tokens and expects
    max_completion_tokens (newer chat completion models). We match on the error
    payload text rather than model id so callers do not need per-model branches.
    """
    text = str(exc).lower()
    return (
        "max_completion_tokens" in text
        and "max_tokens" in text
        and ("unsupported" in text or "not supported" in text)
    )


def generate_answer(
    llm_client,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> str:
    messages = [
        {"role": "system", "content": DEFAULT_RAG_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    request_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        **_build_token_limit_kwargs(model, max_tokens),
    }
    # Use the model-appropriate token limit parameter up front; keep the retry as
    # a safety net for OpenAI-compatible backends with different expectations.
    try:
        response = llm_client.chat.completions.create(**request_kwargs)
    except BadRequestError as e:
        _log_bad_request_error(
            exc=e,
            model=model,
            stage="generation.chat_completions",
        )
        if not _unsupported_max_tokens_use_max_completion_tokens(e):
            raise
        logger.info(
            "Retrying chat completion with max_completion_tokens model=%s stage=%s",
            model,
            "generation.chat_completions",
        )
        response = llm_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
    return response.choices[0].message.content.strip()


def _log_bad_request_error(*, exc: BadRequestError, model: str, stage: str) -> None:
    logger.warning(
        "OpenAI BadRequestError stage=%s model=%s exception_type=%s status_code=%s message=%s body=%s",
        stage,
        model,
        exc.__class__.__name__,
        getattr(exc, "status_code", None),
        str(exc),
        _safe_error_body(exc),
    )


def _safe_error_body(exc: BadRequestError):
    body = getattr(exc, "body", None)
    if body not in (None, ""):
        return body

    response = getattr(exc, "response", None)
    if response is not None:
        try:
            return response.json()
        except Exception:
            try:
                return response.text
            except Exception:
                return None
    return None

