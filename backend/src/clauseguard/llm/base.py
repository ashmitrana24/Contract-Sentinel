"""Base protocols, dataclasses, and exceptions for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol, runtime_checkable


class LLMError(Exception):
    """Base exception for LLM provider errors."""


class LLMTimeoutError(LLMError):
    """Provider timed out during generation."""


class LLMAuthError(LLMError):
    """Provider authentication failed (invalid or missing API key)."""


class LLMDisabledError(LLMError):
    """LLM provider is disabled or not configured."""


@dataclass(frozen=True)
class LLMResponse:
    """Standardized response from an LLM call."""

    content: str
    token_count: int
    latency_ms: int
    model: str
    stop_reason: str = "end_turn"


@dataclass(frozen=True)
class ModelInfo:
    """Metadata describing a provider model."""

    provider: str
    model: str
    streaming_supported: bool = True
    context_window: int = 128000


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for pluggable LLM backends."""

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Execute a non-streaming completion."""
        ...

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> Iterator[str]:
        """Stream response tokens."""
        ...

    def get_model_info(self) -> ModelInfo:
        """Return model metadata."""
        ...

    def is_available(self) -> bool:
        """Check if provider is configured and reachable."""
        ...
