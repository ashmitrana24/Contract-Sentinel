"""Integration tests for Module 6: Ask ClauseGuard API, SSE streaming, and conversation persistence."""

from __future__ import annotations

import json
import uuid

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from clauseguard.config import Settings
from clauseguard.db.models import Conversation, Document, Message
from clauseguard.db.session import _get_engine
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.main import Worker


def _make_test_pdf() -> bytes:
    doc = pymupdf.open()
    p1_text = (
        "MASTER SERVICES AGREEMENT\n\n"
        "1. DEFINITIONS AND INTERPRETATION.\nIn this Agreement, capitalized terms have standard meanings.\n\n"
        "2. TERM AND TERMINATION.\nThis Agreement shall remain in effect for two years. Either party may terminate "
        "this Agreement for convenience upon sixty (60) days prior written notice.\n\n"
        "3. LIMITATION OF LIABILITY.\nIn no event shall either party's aggregate liability under this agreement "
        "exceed $500,000. In no event shall either party be liable for any consequential, indirect, or incidental damages.\n\n"
        "4. GOVERNING LAW.\nThis Agreement shall be governed by and construed in accordance with the laws of the State of Delaware."
    )
    p = doc.new_page(width=595, height=842)
    p.insert_textbox(pymupdf.Rect(50, 50, 500, 750), p1_text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.mark.integration
def test_ask_clauseguard_end_to_end_integration(
    client: TestClient,
    test_cfg: Settings,
    file_store: FileStore,
) -> None:
    pdf_bytes = _make_test_pdf()

    # 1. Upload document and process
    upload_resp = client.post(
        "/v1/documents",
        files={"file": ("master_agreement.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 202
    doc_id = uuid.UUID(upload_resp.json()["document_id"])

    worker = Worker(cfg=test_cfg)
    processed = worker.run_once()
    assert processed >= 1

    # 2. Check LLM status
    status_resp = client.get("/v1/llm/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["persona"] == "Aeqi"
    assert status_data["available"] is True
    assert "api_key" not in status_data

    # 3. Check dynamic suggestions
    sug_resp = client.get(f"/v1/documents/{doc_id}/ask/suggestions")
    assert sug_resp.status_code == 200
    sug_data = sug_resp.json()
    assert 4 <= len(sug_data["suggestions"]) <= 6
    sug_categories = {s["category"] for s in sug_data["suggestions"]}
    assert "key_terms" in sug_categories or "obligations" in sug_categories

    # 4. Ask grounded question (non-streaming)
    ask_payload = {
        "question": "What is the governing law of the State of Delaware?",
        "stream": False,
    }
    ask_resp = client.post(f"/v1/documents/{doc_id}/ask", json=ask_payload)
    assert ask_resp.status_code == 200
    ask_data = ask_resp.json()

    conv_id = uuid.UUID(ask_data["conversation_id"])
    msg_id = uuid.UUID(ask_data["message_id"])
    assert "Delaware" in ask_data["answer"]
    assert ask_data["status"] == "answered"
    assert len(ask_data["citations"]) > 0

    # 5. Follow-up question in same conversation
    followup_payload = {
        "conversation_id": str(conv_id),
        "question": "What is the liability cap under the agreement? It says $500,000.",
        "stream": False,
    }
    followup_resp = client.post(f"/v1/documents/{doc_id}/ask", json=followup_payload)
    assert followup_resp.status_code == 200
    followup_data = followup_resp.json()
    assert followup_data["conversation_id"] == str(conv_id)
    assert "$500,000" in followup_data["answer"]

    # 6. Check conversations list
    conv_list_resp = client.get(f"/v1/documents/{doc_id}/conversations")
    assert conv_list_resp.status_code == 200
    conv_items = conv_list_resp.json()
    assert len(conv_items) == 1
    assert conv_items[0]["id"] == str(conv_id)
    assert conv_items[0]["message_count"] == 4  # 2 user + 2 assistant

    # 7. Check conversation detail
    detail_resp = client.get(f"/v1/conversations/{conv_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert len(detail_data["messages"]) == 4
    assert detail_data["messages"][0]["role"] == "user"
    assert detail_data["messages"][1]["role"] == "assistant"
    assert len(detail_data["messages"][1]["citations"]) > 0

    # 8. Test SSE Streaming mode
    stream_payload = {
        "conversation_id": str(conv_id),
        "question": "What are the termination notice requirements?",
        "stream": True,
    }
    with client.stream("POST", f"/v1/documents/{doc_id}/ask", json=stream_payload) as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers["content-type"]
        events = []
        for line in stream_resp.iter_lines():
            line_str = line.strip()
            if line_str.startswith("event:"):
                events.append(line_str.split("event:")[1].strip())

        assert "metadata" in events
        assert "citation" in events
        assert "delta" in events
        assert "done" in events

    # 9. Test conversation deletion
    del_resp = client.delete(f"/v1/conversations/{conv_id}")
    assert del_resp.status_code == 204

    # Verify conversation is gone
    get_del = client.get(f"/v1/conversations/{conv_id}")
    assert get_del.status_code == 404

    # 10. Test cascade delete from Document
    # Create a fresh conversation
    c_resp = client.post(
        f"/v1/documents/{doc_id}/ask",
        json={"question": "Where are dispute hearings held?", "stream": False},
    )
    assert c_resp.status_code == 200
    new_conv_id = uuid.UUID(c_resp.json()["conversation_id"])

    # Delete parent document
    del_doc = client.delete(f"/v1/documents/{doc_id}")
    assert del_doc.status_code == 204

    # Verify cascade deleted conversation
    get_conv_after = client.get(f"/v1/conversations/{new_conv_id}")
    assert get_conv_after.status_code == 404
