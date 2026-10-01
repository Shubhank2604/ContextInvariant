"""Offline-safe optional language-model provider tests."""

from types import SimpleNamespace

import pytest

from contextos.errors import LLMProviderError
from contextos.providers import MockLLMProvider, OpenAIProvider


def test_mock_provider_is_deterministic() -> None:
    result = MockLLMProvider("fixed").complete("ignored", max_output_tokens=4)
    assert result.text == "fixed"
    assert result.model == "mock"


def test_openai_provider_requires_explicit_model_and_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        OpenAIProvider(model=" ")
    with pytest.raises(ValueError, match="temperature"):
        OpenAIProvider(model="configured-benchmark-model", temperature=2.1)
    with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
        OpenAIProvider(model="configured-benchmark-model").complete("prompt", max_output_tokens=8)


def test_openai_provider_streams_text_usage_and_ttft(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []
    usage = SimpleNamespace(
        input_tokens=11,
        output_tokens=2,
        input_tokens_details=SimpleNamespace(cached_tokens=3),
    )
    completed = SimpleNamespace(output_text="fallback", usage=usage)
    events = [
        SimpleNamespace(type="response.created"),
        SimpleNamespace(type="response.output_text.delta", delta="safe "),
        SimpleNamespace(type="response.output_text.delta", delta="answer"),
        SimpleNamespace(type="response.completed", response=completed),
    ]

    class FakeResponses:
        def create(self, **request: object) -> list[SimpleNamespace]:
            requests.append(request)
            return events

    class FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            assert api_key == "test-key"
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "contextos.providers.openai.importlib.import_module",
        lambda name: SimpleNamespace(OpenAI=FakeOpenAI),
    )

    result = OpenAIProvider(
        model="configured-benchmark-model",
        temperature=0.0,
    ).complete("prompt", max_output_tokens=8)

    assert requests == [
        {
            "model": "configured-benchmark-model",
            "input": "prompt",
            "max_output_tokens": 8,
            "temperature": 0.0,
            "stream": True,
        }
    ]
    assert result.text == "safe answer"
    assert result.input_tokens == 11
    assert result.output_tokens == 2
    assert result.cached_tokens == 3
    assert result.ttft_ms is not None
    assert result.ttft_ms >= 0.0


def test_openai_provider_rejects_incomplete_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponses:
        def create(self, **request: object) -> list[SimpleNamespace]:
            return [SimpleNamespace(type="response.created")]

    class FakeOpenAI:
        def __init__(self, *, api_key: str) -> None:
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "contextos.providers.openai.importlib.import_module",
        lambda name: SimpleNamespace(OpenAI=FakeOpenAI),
    )

    with pytest.raises(LLMProviderError, match="without completion"):
        OpenAIProvider(model="configured-benchmark-model").complete("prompt", max_output_tokens=8)
