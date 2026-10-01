"""Lazy optional OpenAI Responses API provider for explicit benchmark runs."""

from __future__ import annotations

import importlib
import os
from time import perf_counter
from typing import Any

from contextos.errors import LLMProviderError
from contextos.providers.base import ProviderResponse


class OpenAIProvider:
    """Call OpenAI only when ``complete`` is explicitly invoked."""

    def __init__(self, *, model: str, temperature: float | None = None) -> None:
        if not model.strip():
            raise ValueError("OpenAI provider model must not be empty")
        if temperature is not None and not 0.0 <= temperature <= 2.0:
            raise ValueError("OpenAI provider temperature must be between zero and two")
        self.model = model
        self.temperature = temperature

    def complete(self, prompt: str, *, max_output_tokens: int) -> ProviderResponse:
        """Generate one bounded response using an environment-provided API key."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMProviderError(
                "OPENAI_API_KEY is required only for an explicitly requested OpenAI run"
            )
        try:
            module = importlib.import_module("openai")
        except ImportError as exc:
            raise LLMProviderError(
                "Install the 'openai' optional dependency to run OpenAI benchmarks"
            ) from exc
        try:
            client_type: Any = module.OpenAI
            client = client_type(api_key=api_key)
            request: dict[str, Any] = {
                "model": self.model,
                "input": prompt,
                "max_output_tokens": max_output_tokens,
            }
            if self.temperature is not None:
                request["temperature"] = self.temperature
            request["stream"] = True
            started = perf_counter()
            stream = client.responses.create(**request)
            text_parts: list[str] = []
            ttft_ms: float | None = None
            response: Any | None = None
            terminal_event_type: str | None = None
            for event in stream:
                event_type = getattr(event, "type", None)
                if event_type == "response.output_text.delta":
                    if ttft_ms is None:
                        ttft_ms = (perf_counter() - started) * 1_000
                    text_parts.append(str(getattr(event, "delta", "")))
                elif event_type in {"response.completed", "response.incomplete"}:
                    response = getattr(event, "response", None)
                    terminal_event_type = event_type
                elif event_type == "error":
                    message = getattr(event, "message", "unknown error")
                    raise LLMProviderError(f"OpenAI streaming response failed: {message}")
            if response is None:
                raise LLMProviderError("OpenAI streaming response ended without completion")
            finish_reason = "completed"
            if terminal_event_type == "response.incomplete":
                incomplete_details = getattr(response, "incomplete_details", None)
                finish_reason = str(getattr(incomplete_details, "reason", "unknown"))
                if finish_reason != "max_output_tokens":
                    raise LLMProviderError(f"OpenAI streaming response incomplete: {finish_reason}")
            usage = getattr(response, "usage", None)
            input_details = getattr(usage, "input_tokens_details", None)
            return ProviderResponse(
                text="".join(text_parts) or str(getattr(response, "output_text", "")),
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                cached_tokens=getattr(input_details, "cached_tokens", None),
                ttft_ms=ttft_ms,
                model=self.model,
                finish_reason=finish_reason,
            )
        except LLMProviderError:
            raise
        except Exception as exc:
            raise LLMProviderError(f"OpenAI response failed: {exc}") from exc
