"""Unit tests for Phase 1: LLM provider layer, privacy pipeline, and status endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from clauseguard.api.main import create_app
from clauseguard.ask.privacy import (
    AEQI_SYSTEM_PROMPT,
    redact_sensitive_pii,
    restore_sensitive_pii,
    sanitize_contract_context,
)
from clauseguard.config import Settings
from clauseguard.llm import (
    AnthropicProvider,
    FakeProvider,
    LLMAuthError,
    LLMDisabledError,
    NoneProvider,
    OpenAICompatProvider,
    get_provider,
)


def test_fake_provider_generate_and_stream() -> None:
    provider = FakeProvider(model="test-fake")
    assert provider.is_available() is True
    info = provider.get_model_info()
    assert info.provider == "fake"
    assert info.model == "test-fake"

    # Test keyword matching: governing law
    res = provider.generate("What is the governing law of the State of Delaware?")
    assert "Delaware" in res.content
    assert res.token_count > 0
    assert res.latency_ms >= 0

    # Test keyword matching: liability cap
    res_cap = provider.generate("What is the liability cap under the agreement? It says $500,000.")
    assert "$500,000" in res_cap.content

    # Test streaming
    tokens = list(provider.stream("Tell me about termination notice."))
    full = "".join(tokens)
    assert "terminate" in full.lower() or "written notice" in full.lower()

    # Test scripted queue
    provider.queue_response("Scripted answer 1")
    queued_res = provider.generate("Any question")
    assert queued_res.content == "Scripted answer 1"


def test_none_provider_disabled() -> None:
    provider = NoneProvider()
    assert provider.is_available() is False
    with pytest.raises(LLMDisabledError):
        provider.generate("Hello")
    with pytest.raises(LLMDisabledError):
        list(provider.stream("Hello"))


def test_anthropic_provider_mocked() -> None:
    provider = AnthropicProvider(api_key="test-key", model="claude-3-5-sonnet-20241022")
    assert provider.is_available() is True

    # Test missing API key
    p_nokey = AnthropicProvider(api_key="")
    assert p_nokey.is_available() is False
    with pytest.raises(LLMAuthError):
        p_nokey.generate("test")

    # Mock successful response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "content": [{"type": "text", "text": "This is Claude's grounded answer."}],
        "usage": {"output_tokens": 12},
        "stop_reason": "end_turn",
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.generate("Question", system=AEQI_SYSTEM_PROMPT)
        assert res.content == "This is Claude's grounded answer."
        assert res.token_count == 12


def test_openai_compat_provider_mocked() -> None:
    provider = OpenAICompatProvider(
        api_key="sk-test",
        model="gpt-4o-mini",
        api_base="https://custom.endpoint/v1",
        provider_name="openai",
    )
    assert provider.is_available() is True
    assert provider.endpoint == "https://custom.endpoint/v1/chat/completions"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "OpenAI answer"}, "finish_reason": "stop"}],
        "usage": {"completion_tokens": 8},
    }

    with patch("httpx.Client.post", return_value=mock_resp):
        res = provider.generate("Question")
        assert res.content == "OpenAI answer"
        assert res.token_count == 8


def test_get_provider_factory() -> None:
    cfg = Settings(llm_provider="fake", llm_model="model-f")
    p = get_provider(cfg)
    assert isinstance(p, FakeProvider)

    cfg_none = Settings(llm_provider="none")
    assert isinstance(get_provider(cfg_none), NoneProvider)

    cfg_anthropic = Settings(llm_provider="anthropic", llm_api_key="ak-123")
    assert isinstance(get_provider(cfg_anthropic), AnthropicProvider)

    cfg_ollama = Settings(llm_provider="ollama")
    assert isinstance(get_provider(cfg_ollama), OpenAICompatProvider)


def test_privacy_and_redaction() -> None:
    sample_text = (
        "Contact attorney John Doe at john.doe@lawfirm.com or call 212-555-0199. "
        "The tax ID is 12-3456789. The agreed fee is $1,500,000 payable by January 15, 2027 under New York law."
    )
    redacted, mapping = redact_sensitive_pii(sample_text)

    # Ensure sensitive items redacted
    assert "john.doe@lawfirm.com" not in redacted
    assert "212-555-0199" not in redacted
    # Ensure monetary amounts, dates, and governing law PRESERVED
    assert "$1,500,000" in redacted
    assert "January 15, 2027" in redacted
    assert "New York law" in redacted

    # Test restoration
    restored = restore_sensitive_pii(redacted, mapping)
    assert restored == sample_text


def test_privacy_hidden_text_warning() -> None:
    class DummyFinding:
        module = "pdf_forensics"
        type = "white_on_white"
        evidence = "Secret hidden waiver of all claims"

    chunks = [
        "Normal clause text regarding payment.",
        "Notice of breach: Secret hidden waiver of all claims without recourse.",
    ]

    context = sanitize_contract_context(chunks, hidden_findings=[DummyFinding()])
    assert "<contract_context>" in context
    assert "</contract_context>" in context
    assert "[SECURITY NOTICE: The following text was detected as HIDDEN/OCCLUDED" in context


def test_llm_status_endpoint() -> None:
    app = create_app()
    client = TestClient(app)
    resp = client.get("/v1/llm/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["persona"] == "Aeqi"
    assert "disclaimer" in data
    assert "consent_notice" in data
    assert "provider" in data
    assert "model" in data
    assert "api_key" not in data
    assert "secret" not in data
