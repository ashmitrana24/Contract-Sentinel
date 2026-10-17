"""OpenAI-compatible LLM provider implementation for OpenAI, Ollama, vLLM, etc."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator

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


class OpenAICompatProvider(LLMProvider):
    """Provider for OpenAI-compatible Chat Completions endpoints."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_tokens: int = 1024,
        timeout_seconds: float = 30.0,
        api_base: str | None = None,
        provider_name: str = "openai",
    ) -> None:
        self.api_key = api_key or ""
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds
        self.provider_name = provider_name
        base = (api_base.rstrip("/") if api_base else "https://api.openai.com/v1")
        if not base.endswith("/chat/completions"):
            self.endpoint = f"{base}/chat/completions"
        else:
            self.endpoint = base

    def is_available(self) -> bool:
        # If ollama or local endpoint, api_key can be empty or "ollama"
        if self.provider_name in ("ollama", "local"):
            return True
        return bool(self.api_key and self.api_key.strip())

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider=self.provider_name,
            model=self.model,
            streaming_supported=True,
            context_window=128000,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        elif self.provider_name not in ("ollama", "local"):
            raise LLMAuthError(f"{self.provider_name} API key is missing. Set LLM_API_KEY.")
        return headers

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if stop:
            payload["stop"] = stop

        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(self.endpoint, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Request to {self.endpoint} timed out after {self.timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise LLMError(f"Connection error to {self.endpoint}: {exc}") from exc

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if resp.status_code == 401:
            raise LLMAuthError(f"Authentication failed: {resp.text}")
        if resp.status_code >= 400:
            raise LLMError(f"API error ({resp.status_code}): {resp.text}")

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            raise LLMError(f"No choices returned from {self.endpoint}")

        msg = choices[0].get("message", {})
        text = msg.get("content", "") or ""
        usage = data.get("usage", {})
        tokens = usage.get("completion_tokens", max(1, len(text.split())))
        stop_reason = choices[0].get("finish_reason", "stop")

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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if stop:
            payload["stop"] = stop

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                with client.stream("POST", self.endpoint, headers=self._headers(), json=payload) as resp:
                    if resp.status_code == 401:
                        raise LLMAuthError(f"Authentication failed: {resp.text}")
                    if resp.status_code >= 400:
                        raise LLMError(f"Streaming error ({resp.status_code})")

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

                        choices = evt.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            text_piece = delta.get("content", "")
                            if text_piece:
                                yield text_piece
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Stream timed out after {self.timeout_seconds}s") from exc
        except httpx.RequestError as exc:
            raise LLMError(f"Streaming error: {exc}") from exc
