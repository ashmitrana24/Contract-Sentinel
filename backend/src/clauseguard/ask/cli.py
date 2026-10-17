"""CLI for Ask ClauseGuard grounded question answering."""

from __future__ import annotations

import argparse
import sys
import uuid

from clauseguard.ask.answer import execute_ask
from clauseguard.ask.privacy import AEQI_SYSTEM_PROMPT
from clauseguard.ask.retrieval import retrieve_evidence
from clauseguard.config import get_settings
from clauseguard.db.models import Document, FindingRow
from clauseguard.db.session import get_session
from clauseguard.llm import get_provider


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask ClauseGuard: Grounded QA over uploaded contracts.")
    parser.add_argument("--document", required=True, help="Document UUID")
    parser.add_argument("question", help="Question to ask about the contract")
    parser.add_argument("--no-stream", action="store_true", help="Disable token streaming")
    parser.add_argument("--verbose", action="store_true", help="Show retrieval debug info and grounding verifications")

    args = parser.parse_args()

    try:
        doc_uuid = uuid.UUID(args.document)
    except ValueError:
        print(f"Error: Invalid document UUID '{args.document}'", file=sys.stderr)
        sys.exit(1)

    cfg = get_settings()

    with get_session() as session:
        doc = session.get(Document, doc_uuid)
        if not doc:
            print(f"Error: Document {doc_uuid} not found in database.", file=sys.stderr)
            sys.exit(1)

        print(f"\nDocument: {doc.original_filename or doc.id} (SHA: {doc.sha256[:8]}...)")
        print(f"Question: {args.question}\n")

        if args.no_stream:
            res = execute_ask(doc_uuid, args.question, session=session, cfg=cfg)
            print(f"Aeqi: {res.answer}\n")
            print(f"[Status: {res.status} | Latency: {res.latency_ms}ms | Tokens: {res.token_count}]")
            if res.citations:
                print("\nCitations:")
                for c in res.citations:
                    heading_str = f" - {c.heading}" if c.heading else ""
                    print(f"  [{c.clause_id}]{heading_str} (p. {c.page}): \"{c.text_snippet}\"")
            if args.verbose and res.verification.warnings:
                print("\nGrounding Warnings:")
                for w in res.verification.warnings:
                    print(f"  * {w}")
        else:
            # Streaming CLI
            provider = get_provider(cfg)
            retrieval = retrieve_evidence(doc_uuid, args.question, session=session, top_k=5)

            if not retrieval.has_sufficient_evidence:
                print("Aeqi: The provided contract excerpts do not contain sufficient information to answer this question.\n")
                sys.exit(0)

            from clauseguard.ask.answer import build_citations, construct_prompt

            hidden_findings = session.query(FindingRow).filter(
                FindingRow.document_id == doc_uuid,
                FindingRow.module == "pdf_forensics",
            ).all()

            prompt = construct_prompt(args.question, retrieval, hidden_findings=hidden_findings)

            print("Aeqi: ", end="", flush=True)
            full_text = []
            for token in provider.stream(prompt, system=AEQI_SYSTEM_PROMPT):
                print(token, end="", flush=True)
                full_text.append(token)
            print("\n")

            citations = build_citations(retrieval.chunks)
            if citations:
                print("Citations:")
                for c in citations:
                    heading_str = f" - {c.heading}" if c.heading else ""
                    print(f"  [{c.clause_id}]{heading_str} (p. {c.page}): \"{c.text_snippet}\"")


if __name__ == "__main__":
    main()
