"""Ask ClauseGuard API routes (Module 6).

Endpoints:
- GET    /v1/llm/status                     – Provider status & persona info
- GET    /v1/documents/{id}/ask/suggestions  – Document-specific question suggestions
- POST   /v1/documents/{id}/ask              – Grounded QA with optional SSE streaming
- GET    /v1/documents/{id}/conversations    – List conversations for document
- GET    /v1/conversations/{id}              – Get conversation detail with messages
- DELETE /v1/conversations/{id}             – Delete conversation
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clauseguard.api.deps import get_cfg, get_db
from clauseguard.ask.answer import (
    build_citations,
    construct_prompt,
    execute_ask,
    is_abstention_answer,
    verify_grounding,
)
from clauseguard.ask.privacy import (
    AEQI_SYSTEM_PROMPT,
    redact_sensitive_pii,
    restore_sensitive_pii,
)
from clauseguard.ask.retrieval import retrieve_evidence
from clauseguard.ask.suggestions import generate_document_suggestions
from clauseguard.config import Settings
from clauseguard.db.models import (
    Conversation,
    Document,
    FindingRow,
    Message,
)
from clauseguard.db.session import get_session
from clauseguard.llm import get_provider
from clauseguard.schemas.api import (
    AskAnswerResponse,
    AskRequest,
    AskSuggestionsResponse,
    Citation,
    ConversationDetailResponse,
    ConversationListItem,
    ErrorResponse,
    LLMStatusResponse,
    MessageItem,
)

logger = logging.getLogger(__name__)
ask_router = APIRouter(tags=["Ask ClauseGuard"])

# Per-document in-memory rate limiter (sliding window of timestamps)
_DOC_RATE_LIMITS: dict[uuid.UUID, list[float]] = {}


def check_document_rate_limit(document_id: uuid.UUID, max_per_min: int = 20) -> None:
    """Enforce a sliding window per-document request rate limit."""
    now = time.time()
    timestamps = _DOC_RATE_LIMITS.setdefault(document_id, [])
    # Retain only timestamps from the last 60 seconds
    valid_timestamps = [t for t in timestamps if now - t < 60.0]
    _DOC_RATE_LIMITS[document_id] = valid_timestamps

    if len(valid_timestamps) >= max_per_min:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded for this document. Please wait before asking another question.",
            headers={"Retry-After": "60"},
        )
    _DOC_RATE_LIMITS[document_id].append(now)


@ask_router.get("/v1/llm/status", response_model=LLMStatusResponse)
def get_llm_status(cfg: Annotated[Settings, Depends(get_cfg)]) -> LLMStatusResponse:
    """Return LLM provider availability, model name, and Aeqi persona info without secrets."""
    provider = get_provider(cfg)
    info = provider.get_model_info()
    is_external = not getattr(cfg, "llm_is_local", False) and info.provider not in ("fake", "none")

    return LLMStatusResponse(
        provider=info.provider,
        model=info.model,
        available=provider.is_available(),
        streaming=info.streaming_supported and cfg.ask_streaming_enabled,
        assistant_name="Aeqi",
        persona="Aeqi",
        consent_required=is_external,
        consent_text="Contract excerpts are processed by the configured AI provider strictly to answer your questions. No contract data is used for model training.",
        consent_notice="Contract excerpts are processed by the configured AI provider strictly to answer your questions. No contract data is used for model training.",
        disclaimer="Aeqi provides automated contract analysis for informational purposes only and does not provide legal advice.",
    )


@ask_router.get(
    "/v1/documents/{document_id}/ask/suggestions",
    response_model=AskSuggestionsResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_ask_suggestions(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> AskSuggestionsResponse:
    """Return tailored question suggestions for the specified document."""
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return generate_document_suggestions(document_id, db)


@ask_router.post(
    "/v1/documents/{document_id}/ask",
    response_model=AskAnswerResponse,
    responses={
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def ask_clauseguard(
    document_id: uuid.UUID,
    req_body: AskRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    cfg: Annotated[Settings, Depends(get_cfg)],
) -> Any:
    """Grounded question answering over an uploaded contract with verified citations and SSE support."""
    # 1. Enforce per-document rate limit
    check_document_rate_limit(document_id, max_per_min=cfg.ask_rate_limit_per_minute)

    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Resolve or create conversation
    conv_id = req_body.conversation_id
    if conv_id is not None:
        conv = db.get(Conversation, conv_id)
        if not conv or conv.document_id != document_id:
            raise HTTPException(status_code=404, detail="Conversation not found for this document")
    else:
        # Create new conversation
        title = req_body.question.strip()[:60]
        conv = Conversation(document_id=document_id, title=title)
        db.add(conv)
        db.flush()
        conv_id = conv.id

    # Retrieve prior conversation context for short follow-up expansion
    prior_messages = db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.desc())
        .limit(2)
    ).scalars().all()

    last_user_query = None
    last_assistant_heading = None
    for pm in prior_messages:
        if pm.role == "user" and not last_user_query:
            last_user_query = pm.content
        elif pm.role == "assistant" and not last_assistant_heading:
            if pm.citations and isinstance(pm.citations, list) and len(pm.citations) > 0:
                first_cite = pm.citations[0]
                if isinstance(first_cite, dict):
                    last_assistant_heading = first_cite.get("heading")

    # Record user message in DB
    user_msg = Message(
        conversation_id=conv_id,
        role="user",
        content=req_body.question.strip(),
    )
    db.add(user_msg)
    db.commit()

    # Load forensics findings for hidden-text protection
    hidden_findings = db.execute(
        select(FindingRow).where(
            (FindingRow.document_id == document_id) & (FindingRow.module == "pdf_forensics")
        )
    ).scalars().all()

    # Non-streaming mode
    if not req_body.stream or not cfg.ask_streaming_enabled:
        exec_res = execute_ask(
            document_id,
            req_body.question,
            session=db,
            cfg=cfg,
            last_user_query=last_user_query,
            last_assistant_heading=last_assistant_heading,
            hidden_findings=hidden_findings,
        )

        assistant_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=exec_res.answer,
            citations=[c.model_dump() for c in exec_res.citations],
            token_count=exec_res.token_count,
            latency_ms=exec_res.latency_ms,
        )
        db.add(assistant_msg)
        db.commit()

        return AskAnswerResponse(
            conversation_id=conv_id,
            message_id=assistant_msg.id,
            question=req_body.question,
            answer=exec_res.answer,
            citations=exec_res.citations,
            status=exec_res.status,
            token_count=exec_res.token_count,
            latency_ms=exec_res.latency_ms,
            hidden_text_excluded=exec_res.hidden_text_excluded,
            verification_kind=exec_res.verification.kind,
        )

    # SSE Streaming mode
    return StreamingResponse(
        _stream_ask_generator(
            document_id=document_id,
            conversation_id=conv_id,
            question=req_body.question,
            request=request,
            cfg=cfg,
            last_user_query=last_user_query,
            last_assistant_heading=last_assistant_heading,
            hidden_findings=hidden_findings,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_ask_generator(
    document_id: uuid.UUID,
    conversation_id: uuid.UUID,
    question: str,
    request: Request,
    cfg: Settings,
    last_user_query: str | None,
    last_assistant_heading: str | None,
    hidden_findings: list[FindingRow],
) -> AsyncIterator[str]:
    """Asynchronous SSE generator with disconnect detection, keep-alive, and message persistence."""
    t0 = time.perf_counter()
    assistant_msg_id = uuid.uuid4()

    # Yield initial metadata event
    meta_payload = {
        "conversation_id": str(conversation_id),
        "message_id": str(assistant_msg_id),
    }
    yield f"event: metadata\ndata: {json.dumps(meta_payload)}\n\n"

    # Yield SSE keep-alive comment so intermediate proxies maintain connection
    yield ": keep-alive\n\n"

    # Separate DB session for background streaming
    with get_session() as session:
        retrieval = retrieve_evidence(
            document_id,
            question,
            session=session,
            top_k=5,
            last_user_query=last_user_query,
            last_assistant_heading=last_assistant_heading,
        )

        citations = build_citations(retrieval.chunks)

        # Yield citation events
        for cit in citations:
            yield f"event: citation\ndata: {json.dumps(cit.model_dump())}\n\n"

        # Check sufficient evidence
        if not retrieval.has_sufficient_evidence or (not retrieval.chunks and not retrieval.overview_block):
            topic = question.rstrip("?").strip()
            no_info_text = f"The contract does not say what is specified regarding {topic}."
            yield f"event: delta\ndata: {json.dumps({'text': no_info_text})}\n\n"
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            done_payload = {
                "status": "insufficient_evidence",
                "token_count": 0,
                "latency_ms": elapsed_ms,
                "hidden_text_excluded": False,
                "verification_kind": "abstention",
            }
            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

            # Persist assistant message
            asst_msg = Message(
                id=assistant_msg_id,
                conversation_id=conversation_id,
                role="assistant",
                content=no_info_text,
                citations=[],
                token_count=0,
                latency_ms=elapsed_ms,
            )
            session.add(asst_msg)
            session.commit()
            return

        # Build prompt with hidden text exclusion and PII protection
        provider = get_provider(cfg)
        prompt, hidden_excluded = construct_prompt(question, retrieval, hidden_findings=hidden_findings)
        redacted_prompt, pii_mapping = redact_sensitive_pii(prompt)

        full_content: list[str] = []
        status = "answered"

        try:
            for token_chunk in provider.stream(redacted_prompt, system=AEQI_SYSTEM_PROMPT):
                if await request.is_disconnected():
                    logger.info("Client disconnected during Ask SSE stream.")
                    return

                full_content.append(token_chunk)
                yield f"event: delta\ndata: {json.dumps({'text': token_chunk})}\n\n"
        except Exception as exc:
            logger.error("Error during streaming generation: %s", exc)
            status = "retrieve_only"
            err_msg = f"\n[Generation halted: {exc}]"
            yield f"event: delta\ndata: {json.dumps({'text': err_msg})}\n\n"
            full_content.append(err_msg)

        raw_complete_text = "".join(full_content)
        # Restore any redacted PII in the final assistant answer
        complete_text = restore_sensitive_pii(raw_complete_text, pii_mapping)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        token_count = max(1, len(complete_text.split()))

        # Yield done event with hidden_text_excluded flag and verification_kind
        v_kind = "abstention" if is_abstention_answer(complete_text) else "answered"
        done_payload = {
            "status": status,
            "token_count": token_count,
            "latency_ms": elapsed_ms,
            "hidden_text_excluded": hidden_excluded,
            "verification_kind": v_kind,
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

        # Persist assistant message
        asst_msg = Message(
            id=assistant_msg_id,
            conversation_id=conversation_id,
            role="assistant",
            content=complete_text,
            citations=[c.model_dump() for c in citations],
            token_count=token_count,
            latency_ms=elapsed_ms,
        )
        session.add(asst_msg)
        session.commit()


@ask_router.get(
    "/v1/documents/{document_id}/conversations",
    response_model=list[ConversationListItem],
    responses={404: {"model": ErrorResponse}},
)
def list_document_conversations(
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> list[ConversationListItem]:
    """List all conversation threads associated with a document."""
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    convs = db.execute(
        select(Conversation)
        .where(Conversation.document_id == document_id)
        .order_by(Conversation.created_at.desc())
    ).scalars().all()

    items: list[ConversationListItem] = []
    for c in convs:
        msg_count = db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == c.id)
        ).scalar_one()
        items.append(
            ConversationListItem(
                id=c.id,
                title=c.title,
                message_count=msg_count,
                created_at=c.created_at.isoformat(),
            )
        )
    return items


@ask_router.get(
    "/v1/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_conversation_detail(
    conversation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> ConversationDetailResponse:
    """Retrieve full transcript of a conversation."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    ).scalars().all()

    message_items: list[MessageItem] = []
    for m in msgs:
        cites: list[Citation] | None = None
        if m.citations and isinstance(m.citations, list):
            cites = [Citation(**c) for c in m.citations if isinstance(c, dict)]
        message_items.append(
            MessageItem(
                id=m.id,
                role=m.role,
                content=m.content,
                citations=cites,
                token_count=m.token_count,
                latency_ms=m.latency_ms,
                created_at=m.created_at.isoformat(),
            )
        )

    return ConversationDetailResponse(
        id=conv.id,
        document_id=conv.document_id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        messages=message_items,
    )


@ask_router.delete(
    "/v1/conversations/{conversation_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
def delete_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Delete a conversation and all its messages."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conv)
    db.commit()
    return Response(status_code=204)
