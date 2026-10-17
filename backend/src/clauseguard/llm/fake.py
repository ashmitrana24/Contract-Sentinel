"""Deterministic fake LLM provider for tests and offline development."""

from __future__ import annotations

import re
import time
from typing import Iterator

from clauseguard.llm.base import LLMProvider, LLMResponse, ModelInfo


class FakeProvider(LLMProvider):
    """Deterministic LLM mock that generates grounded mock responses without network calls."""

    def __init__(
        self,
        model: str = "fake-claude-3-5",
        stream_chunk_delay: float = 0.0,
    ) -> None:
        self.model = model
        self.stream_chunk_delay = stream_chunk_delay
        self._scripted_responses: list[str] = []

    def queue_response(self, text: str) -> None:
        """Queue a predetermined response for the next call."""
        self._scripted_responses.append(text)

    def is_available(self) -> bool:
        return True

    def get_model_info(self) -> ModelInfo:
        return ModelInfo(
            provider="fake",
            model=self.model,
            streaming_supported=True,
            context_window=100000,
        )

    def _generate_text(self, prompt: str) -> str:
        if self._scripted_responses:
            return self._scripted_responses.pop(0)

        p_lower = prompt.lower()
        q_match = re.search(r"USER QUESTION:\s*(.*?)(?:\n\n|\n|$)", prompt, re.IGNORECASE)
        q_lower = q_match.group(1).lower() if q_match else p_lower

        # If overview mode or risk summary
        if "risk" in q_lower and ("overview" in q_lower or "summary" in q_lower or "main" in q_lower):
            return (
                "Based on the analysis of the contract, the primary risks identified include "
                "potential tampering or hidden text findings and contractual notice periods."
            )

        # Liability
        if "liability" in q_lower or "cap" in q_lower:
            m = re.search(r"(\$[0-9,]+)", prompt)
            amt = m.group(1) if m else "the agreed amount"
            return (
                f"Under the Limitation of Liability clause, aggregate liability is capped at {amt}. "
                f'The contract explicitly provides that total aggregate liability shall not exceed {amt}.'
            )

        # Governing law
        if "governing law" in q_lower or "jurisdiction" in q_lower:
            m = re.search(r"(?:laws|law)\s+of\s+(?:the\s+State\s+of\s+|State\s+of\s+|the\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)?)", prompt, re.IGNORECASE)
            jurisdiction = m.group(1).strip() if m else "the specified jurisdiction"
            return (
                f"Under the Governing Law clause, this Agreement is governed by the laws of {jurisdiction}. "
                f'The contract states: "This Agreement shall be governed by and construed in accordance with the laws of {jurisdiction}."'
            )

        # Termination
        if "termination" in q_lower or "terminate" in q_lower or "notice" in q_lower:
            return (
                "Either party may terminate the Agreement for convenience upon written notice as specified in Section 3. "
                'The contract provides for termination upon prior written notice.'
            )

        # General grounded response quoting context if available
        # Find first clause block or excerpt in prompt
        m_quote = re.search(r"\[(?:Clause|c)(\d+)\]\s*(.*?)(?=\n\n|\n\[|<|$)", prompt, re.DOTALL)
        if m_quote:
            c_num = m_quote.group(1)
            snippet = m_quote.group(2).strip().split(".")[0]
            if len(snippet) > 10:
                return (
                    f"According to Clause {c_num}, the contract specifies that {snippet}. "
                    f'Specifically: "{snippet}."'
                )

        return (
            "Based on the retrieved contract clauses, the agreement sets forth the obligations "
            "and conditions agreed upon by the parties."
        )

    def generate(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        t0 = time.perf_counter()
        text = self._generate_text(prompt)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        tokens = max(1, len(text.split()))

        return LLMResponse(
            content=text,
            token_count=tokens,
            latency_ms=elapsed_ms,
            model=self.model,
            stop_reason="end_turn",
        )

    def stream(
        self,
        prompt: str,
        *,
        system: str | None = None,
        stop: list[str] | None = None,
    ) -> Iterator[str]:
        text = self._generate_text(prompt)
        words = text.split(" ")
        # Yield in 2-3 word chunks
        chunk_size = 3
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i : i + chunk_size])
            if i + chunk_size < len(words):
                chunk += " "
            if self.stream_chunk_delay > 0:
                time.sleep(self.stream_chunk_delay)
            yield chunk
