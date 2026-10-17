"""Drift verification test ensuring docs/ask-api.md matches actual Pydantic models."""

from __future__ import annotations

import re
from pathlib import Path

from clauseguard.schemas.api import (
    AskAnswerResponse,
    AskRequest,
    AskSuggestion,
    AskSuggestionsResponse,
    Citation,
    ConversationDetailResponse,
    ConversationListItem,
    LLMStatusResponse,
    MessageItem,
)

DOCS_PATH = Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "ask-api.md"


def _extract_ts_interface_fields(doc_content: str, interface_name: str) -> set[str]:
    pattern = rf"export\s+interface\s+{interface_name}\s*\{{([^}}]+)\}}"
    match = re.search(pattern, doc_content)
    assert match, f"Interface {interface_name} not found in docs/ask-api.md"

    body = match.group(1)
    field_lines = [line.strip() for line in body.splitlines() if line.strip() and not line.strip().startswith("//")]

    fields: set[str] = set()
    for line in field_lines:
        m = re.match(r"^([a-zA-Z0-9_]+)\??\s*:", line)
        if m:
            fields.add(m.group(1))
    return fields


def test_docs_exist() -> None:
    assert DOCS_PATH.exists(), f"docs/ask-api.md does not exist at {DOCS_PATH}"


def test_schemas_match_documented_typescript_types() -> None:
    doc_content = DOCS_PATH.read_text(encoding="utf-8")

    models_to_check = [
        (LLMStatusResponse, "LLMStatusResponse"),
        (AskSuggestion, "AskSuggestion"),
        (AskSuggestionsResponse, "AskSuggestionsResponse"),
        (Citation, "Citation"),
        (AskRequest, "AskRequest"),
        (AskAnswerResponse, "AskAnswerResponse"),
        (MessageItem, "MessageItem"),
        (ConversationListItem, "ConversationListItem"),
        (ConversationDetailResponse, "ConversationDetailResponse"),
    ]

    for model_cls, ts_name in models_to_check:
        model_fields = set(model_cls.model_fields.keys())
        doc_fields = _extract_ts_interface_fields(doc_content, ts_name)

        missing_in_doc = model_fields - doc_fields
        extra_in_doc = doc_fields - model_fields

        assert not missing_in_doc, f"Model {model_cls.__name__} has fields not documented in TypeScript type {ts_name}: {missing_in_doc}"
        assert not extra_in_doc, f"TypeScript type {ts_name} in docs documents fields not in model {model_cls.__name__}: {extra_in_doc}"


def test_documented_endpoints_exist_in_router() -> None:
    from clauseguard.api.ask_routes import ask_router

    router_paths = {route.path for route in ask_router.routes}
    doc_content = DOCS_PATH.read_text(encoding="utf-8")

    expected_endpoints = [
        "/v1/llm/status",
        "/v1/documents/{document_id}/ask/suggestions",
        "/v1/documents/{document_id}/ask",
        "/v1/documents/{document_id}/conversations",
        "/v1/conversations/{conversation_id}",
    ]

    for ep in expected_endpoints:
        assert ep in router_paths, f"Documented endpoint {ep} not found in ask_router routes: {router_paths}"
