"""Tests for LLM status endpoint, CORS preflight, per-document rate limiting, and SSE protocol."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from clauseguard.api.ask_routes import (
    _DOC_RATE_LIMITS,
    _stream_ask_generator,
    check_document_rate_limit,
)
from clauseguard.api.main import app
from clauseguard.config import get_settings


@pytest.fixture(autouse=True)
def clear_rate_limits():
    _DOC_RATE_LIMITS.clear()
    yield
    _DOC_RATE_LIMITS.clear()


def test_llm_status_fields_and_no_secrets_exposed():
    """Verify /v1/llm/status returns assistant_name, consent_required, consent_text, disclaimer and no secrets."""
    client = TestClient(app)
    response = client.get("/v1/llm/status")
    assert response.status_code == 200
    data = response.json()

    # Required fields per specification
    assert data["assistant_name"] == "Aeqi"
    assert "consent_required" in data
    assert isinstance(data["consent_required"], bool)
    assert "consent_text" in data and len(data["consent_text"]) > 10
    assert "disclaimer" in data and "legal advice" in data["disclaimer"].lower()
    assert data["persona"] == "Aeqi"
    assert "provider" in data
    assert "model" in data

    # Verify API key or secrets are NEVER exposed in the response
    raw_text = response.text.lower()
    assert "api_key" not in raw_text
    assert "llm_api_key" not in raw_text
    assert "secret" not in raw_text
    assert "gsk_" not in raw_text


def test_cors_preflight_allowed_origin():
    """Verify CORS preflight returns 200 with Allow-Origin header for configured origins."""
    client = TestClient(app)
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/v1/documents/00000000-0000-0000-0000-000000000000/ask", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_preflight_disallowed_origin():
    """Verify CORS preflight rejects or does not allow unlisted origins."""
    client = TestClient(app)
    headers = {
        "Origin": "http://malicious-phishing-site.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    response = client.options("/v1/documents/00000000-0000-0000-0000-000000000000/ask", headers=headers)
    assert response.headers.get("access-control-allow-origin") != "http://malicious-phishing-site.com"


def test_per_document_rate_limiting():
    """Verify rapid repeated calls for the same document trigger HTTP 429 with Retry-After header."""
    doc_id = uuid.uuid4()

    # 3 requests allowed under max_per_min=3
    for _ in range(3):
        check_document_rate_limit(doc_id, max_per_min=3)

    # 4th request must trigger HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        check_document_rate_limit(doc_id, max_per_min=3)

    assert exc_info.value.status_code == 429
    assert "rate limit exceeded" in exc_info.value.detail.lower()
    assert exc_info.value.headers.get("Retry-After") == "60"

    # Distinct document is not affected by other document's limit
    other_doc_id = uuid.uuid4()
    check_document_rate_limit(other_doc_id, max_per_min=3)


@pytest.mark.anyio
async def test_streaming_disconnect_cancellation():
    """Verify that provider streaming stops when the client disconnects."""
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)

    cfg = get_settings()
    doc_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    with patch("clauseguard.api.ask_routes.get_session") as mock_session_ctx:
        mock_session = MagicMock()
        mock_session_ctx.return_value.__enter__.return_value = mock_session

        with patch("clauseguard.api.ask_routes.retrieve_evidence") as mock_retrieval:
            mock_retrieval.return_value = MagicMock(
                has_sufficient_evidence=True,
                chunks=[MagicMock(chunk_id="c1", clause_id="1", heading="Term", page_start=1, text="Test text")],
                overview_block=None,
            )
            with patch("clauseguard.api.ask_routes.get_provider") as mock_gp:
                mock_prov = MagicMock()
                mock_prov.stream.return_value = iter(["token1", "token2"])
                mock_gp.return_value = mock_prov

                events = []
                async for event in _stream_ask_generator(
                    document_id=doc_id,
                    conversation_id=conv_id,
                    question="What is the governing law?",
                    request=mock_request,
                    cfg=cfg,
                    last_user_query=None,
                    last_assistant_heading=None,
                    hidden_findings=[],
                ):
                    events.append(event)

                event_str = "".join(events)
                assert "event: metadata" in event_str
                assert ": keep-alive" in event_str
                # Disconnect was detected, so streaming broke immediately
                assert "token1" not in event_str


@pytest.mark.anyio
async def test_sse_keepalive_comment():
    """Verify the SSE stream emits ': keep-alive' to maintain persistent proxy connections."""
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=False)

    cfg = get_settings()
    doc_id = uuid.uuid4()
    conv_id = uuid.uuid4()

    with patch("clauseguard.api.ask_routes.get_session") as mock_session_ctx:
        mock_session = MagicMock()
        mock_session_ctx.return_value.__enter__.return_value = mock_session

        with patch("clauseguard.api.ask_routes.retrieve_evidence") as mock_retrieval:
            mock_retrieval.return_value = MagicMock(
                has_sufficient_evidence=False,
                chunks=[],
                overview_block=None,
            )

            events = []
            async for event in _stream_ask_generator(
                document_id=doc_id,
                conversation_id=conv_id,
                question="What is this contract about?",
                request=mock_request,
                cfg=cfg,
                last_user_query=None,
                last_assistant_heading=None,
                hidden_findings=[],
            ):
                events.append(event)

            event_str = "".join(events)
            assert ": keep-alive\n\n" in event_str
            assert "insufficient_evidence" in event_str
