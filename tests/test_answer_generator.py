from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_core.generation.answer_generator import generate_answer


class _FakeCompletions:
    def __init__(self, content: str = "ok") -> None:
        self.calls = []
        self._response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class _FakeClient:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletions())


def test_generate_answer_uses_max_completion_tokens_for_gpt5_models():
    client = _FakeClient()

    result = generate_answer(
        llm_client=client,
        model="gpt-5.4-mini",
        prompt="test prompt",
        temperature=0.3,
        max_tokens=321,
    )

    assert result == "ok"
    assert len(client.chat.completions.calls) == 1
    payload = client.chat.completions.calls[0]
    assert payload["max_completion_tokens"] == 321
    assert "max_tokens" not in payload


def test_generate_answer_keeps_max_tokens_for_legacy_models():
    client = _FakeClient()

    result = generate_answer(
        llm_client=client,
        model="gpt-4o-mini",
        prompt="test prompt",
        temperature=0.3,
        max_tokens=654,
    )

    assert result == "ok"
    assert len(client.chat.completions.calls) == 1
    payload = client.chat.completions.calls[0]
    assert payload["max_tokens"] == 654
    assert "max_completion_tokens" not in payload
