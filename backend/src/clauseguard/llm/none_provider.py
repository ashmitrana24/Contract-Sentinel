"""Disabled / placeholder provider when LLM is not configured."""

from __future__ import annotations

from typing import Iterator

from clauseguard.llm.base import LLMDisabledError, LLMProvider, LLMResponse, ModelInfo


class NoneProvider(LLMProvider):
    """Provider used when LLM integration is disabled or not configured."""

    def is_available(self) -> bool:
        return False

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider="none",
            model="none",
            streaming_supported=False,
            context_window=0,
        )

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        raise LLMDisabledError(
            "LLM provider is not configured. Set LLM_PROVIDER to fake, anthropic, openai, or ollama."
        )

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> Iterator[str]:
        raise LLMDisabledError(
            "LLM provider is not configured. Set LLM_PROVIDER to fake, anthropic, openai, or ollama."
        )
