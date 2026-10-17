"""Anthropic Claude LLM provider implementation using httpx."""

from __future__ import annotations

import json
import logging
import time
from typing import Iterator

import httpx

from clauseguard.llm.base import (
    LLMAuthError,
    LLMError,
    LLMProvider,
    LLMResponse,
    LLMTimeoutError,
    ModelInfo,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic Claude models via Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout_seconds: float = 30.0,
        api_base: str | None = None,
    ) -> None:
        self.api_key = api_key or ""
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.endpoint = (api_base.rstrip("/") if api_base else "https://api.anthropic.com") + "/v1/messages"

    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider="anthropic",
            model=self.model,
            streaming_supported=True,
            context_window=200000,
        )

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMAuthError("Anthropic API key is missing. Set LLM_API_KEY environment variable.")
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        if stop:
            payload["stop_sequences"] = stop

        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(self.endpoint, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Anthropic request timed out after {self.timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise LLMError(f"Anthropic network connection error: {exc}") from exc

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if resp.status_code == 401:
            raise LLMAuthError(f"Anthropic 401 Unauthorized: {resp.text}")
        if resp.status_code >= 400:
            raise LLMError(f"Anthropic API error (status {resp.status_code}): {resp.text}")

        data = resp.json()
        content_blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")
        usage = data.get("usage", {})
        tokens = usage.get("output_tokens", max(1, len(text.split())))
        stop_reason = data.get("stop_reason", "end_turn")

        return LLMResponse(
            content=text,
            token_count=tokens,
            latency_ms=elapsed_ms,
            model=self.model,
            stop_reason=stop_reason,
        )

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> Iterator[str]:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        if system:
            payload["system"] = system
        if stop:
            payload["stop_sequences"] = stop

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                with client.stream("POST", self.endpoint, headers=self._headers(), json=payload) as resp:
                    if resp.status_code == 401:
                        raise LLMAuthError(f"Anthropic 401 Unauthorized: {resp.text}")
                    if resp.status_code >= 400:
                        raise LLMError(f"Anthropic streaming API error (status {resp.status_code})")

                    for line in resp.iter_lines():
                        line = line.strip()
                        if not line or not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            evt = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        evt_type = evt.get("type")
                        if evt_type == "content_block_delta":
                            delta = evt.get("delta", {})
                            if delta.get("type") == "text_delta":
                                text_piece = delta.get("text", "")
                                if text_piece:
                                    yield text_piece
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Anthropic stream timed out after {self.timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise LLMError(f"Anthropic streaming network error: {exc}") from exc
