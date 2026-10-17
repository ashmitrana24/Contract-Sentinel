"""LLM Provider factory and exports."""

from __future__ import annotations

from clauseguard.config import Settings, get_settings
from clauseguard.llm.anthropic_provider import AnthropicProvider
from clauseguard.llm.base import (
    LLMAuthError,
    LLMDisabledError,
    LLMError,
    LLMProvider,
    LLMResponse,
    LLMTimeoutError,
    ModelInfo,
)
from clauseguard.llm.fake import FakeProvider
from clauseguard.llm.none_provider import NoneProvider
from clauseguard.llm.openai_compat import OpenAICompatProvider

__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ModelInfo",
    "LLMError",
    "LLMTimeoutError",
    "LLMAuthError",
    "LLMDisabledError",
    "FakeProvider",
    "NoneProvider",
    "AnthropicProvider",
    "OpenAICompatProvider",
    "get_provider",
]


def get_provider(cfg: Settings | None = None) -> LLMProvider:
    """Instantiate and return the configured LLM provider."""
    settings = cfg or get_settings()
    provider_type = (settings.llm_provider or "fake").strip().lower()

    if provider_type == "none":
        return NoneProvider()
    elif provider_type == "fake":
        return FakeProvider(model=settings.llm_model)
    elif provider_type == "anthropic":
        return AnthropicProvider(
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
            api_base=settings.llm_api_base,
        )
    elif provider_type in ("openai", "openai_compat", "ollama", "groq"):
        api_base = settings.effective_llm_base_url
        if not api_base and provider_type == "ollama":
            api_base = "http://localhost:11434/v1"
        return OpenAICompatProvider(
            api_key=settings.llm_api_key or ("ollama" if provider_type == "ollama" else None),
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
            api_base=api_base,
            provider_name=provider_type,
        )
    else:
        # Fallback to FakeProvider with warning
        return FakeProvider(model=settings.llm_model)
