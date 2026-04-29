"""
LLM answer generation helpers for reusable RAG core.
"""

from openai import BadRequestError

from app_core.generation.prompts import DEFAULT_RAG_SYSTEM_PROMPT


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
    # Prefer max_tokens for broad OpenAI-compatible compatibility; some models
    # return 400 and require max_completion_tokens instead — retry once on that signal.
    try:
        response = llm_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except BadRequestError as e:
        if not _unsupported_max_tokens_use_max_completion_tokens(e):
            raise
        response = llm_client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
    return response.choices[0].message.content.strip()

