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
    with pytest.raises(ValueError, match="interval"):
        OpenAIProvider(
            model="configured-benchmark-model",
            minimum_request_interval_seconds=-0.1,
        )
    with pytest.raises(ValueError, match="retries"):
        OpenAIProvider(model="configured-benchmark-model", max_retries=-1)
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
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            assert api_key == "test-key"
            assert max_retries == 6
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
    assert result.finish_reason == "completed"


def test_openai_provider_paces_repeated_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage = SimpleNamespace(
        input_tokens=1,
        output_tokens=1,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    completed = SimpleNamespace(output_text="answer", usage=usage)

    class FakeResponses:
        def create(self, **request: object) -> list[SimpleNamespace]:
            return [SimpleNamespace(type="response.completed", response=completed)]

    class FakeOpenAI:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            self.responses = FakeResponses()

    ticks = iter((0.0, 0.0, 0.0, 0.5, 2.0, 2.0))
    sleeps: list[float] = []
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "contextos.providers.openai.importlib.import_module",
        lambda name: SimpleNamespace(OpenAI=FakeOpenAI),
    )
    monkeypatch.setattr("contextos.providers.openai.perf_counter", lambda: next(ticks))
    monkeypatch.setattr("contextos.providers.openai.sleep", sleeps.append)
    provider = OpenAIProvider(
        model="configured-benchmark-model",
        minimum_request_interval_seconds=2.0,
    )

    provider.complete("first", max_output_tokens=8)
    provider.complete("second", max_output_tokens=8)

    assert sleeps == [1.5]


def test_openai_provider_retains_output_truncated_at_declared_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage = SimpleNamespace(
        input_tokens=11,
        output_tokens=8,
        input_tokens_details=SimpleNamespace(cached_tokens=0),
    )
    incomplete = SimpleNamespace(
        output_text="partial output",
        usage=usage,
        incomplete_details=SimpleNamespace(reason="max_output_tokens"),
    )
    events = [
        SimpleNamespace(type="response.output_text.delta", delta="partial "),
        SimpleNamespace(type="response.output_text.delta", delta="output"),
        SimpleNamespace(type="response.incomplete", response=incomplete),
    ]

    class FakeResponses:
        def create(self, **request: object) -> list[SimpleNamespace]:
            return events

    class FakeOpenAI:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "contextos.providers.openai.importlib.import_module",
        lambda name: SimpleNamespace(OpenAI=FakeOpenAI),
    )

    result = OpenAIProvider(model="configured-benchmark-model").complete(
        "prompt", max_output_tokens=8
    )

    assert result.text == "partial output"
    assert result.input_tokens == 11
    assert result.output_tokens == 8
    assert result.finish_reason == "max_output_tokens"


def test_openai_provider_rejects_other_incomplete_reasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete = SimpleNamespace(
        incomplete_details=SimpleNamespace(reason="content_filter"),
    )

    class FakeResponses:
        def create(self, **request: object) -> list[SimpleNamespace]:
            return [SimpleNamespace(type="response.incomplete", response=incomplete)]

    class FakeOpenAI:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "contextos.providers.openai.importlib.import_module",
        lambda name: SimpleNamespace(OpenAI=FakeOpenAI),
    )

    with pytest.raises(LLMProviderError, match="content_filter"):
        OpenAIProvider(model="configured-benchmark-model").complete("prompt", max_output_tokens=8)


def test_openai_provider_rejects_incomplete_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponses:
        def create(self, **request: object) -> list[SimpleNamespace]:
            return [SimpleNamespace(type="response.created")]

    class FakeOpenAI:
        def __init__(self, *, api_key: str, max_retries: int) -> None:
            self.responses = FakeResponses()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        "contextos.providers.openai.importlib.import_module",
        lambda name: SimpleNamespace(OpenAI=FakeOpenAI),
    )

    with pytest.raises(LLMProviderError, match="without completion"):
        OpenAIProvider(model="configured-benchmark-model").complete("prompt", max_output_tokens=8)
