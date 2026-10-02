"""Pydantic v2 domain models for contracts and ground-truth labels."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Contract domain
# ---------------------------------------------------------------------------


class KeyFactKind(StrEnum):
    AMOUNT = "amount"
    DATE = "date"
    XREF = "xref"


class MonetaryAmount(BaseModel):
    """A monetary amount with both numeric figure and words representation."""

    figure: str = Field(description="E.g. 'Rs. 10,00,000'")
    words: str = Field(description="E.g. 'Rupees Ten Lakh Only'")
    currency_symbol: str = Field(default="Rs.", description="Currency symbol/prefix")

    def __str__(self) -> str:
        return f"{self.figure} ({self.words})"


class KeyFact(BaseModel):
    """One verifiable fact extracted from a contract."""

    kind: KeyFactKind
    clause_id: str | None = None  # e.g. "4.2"
    label: str = ""  # human label, e.g. "service_fee"
    # amount-specific
    amount: MonetaryAmount | None = None
    # date-specific
    date_str: str | None = None  # ISO 8601: "2024-06-01"
    date_label: str | None = None  # e.g. "effective_date"
    # xref-specific
    xref_target: str | None = None  # e.g. "4.2"
    xref_source_clause: str | None = None  # clause containing this xref


class Party(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    role: str = ""  # e.g. "Service Provider", "Client"


class Clause(BaseModel):
    id: str  # e.g. "4.2"
    heading: str
    text: str  # full paragraph text


class Contract(BaseModel):
    """Structured representation of a contract document."""

    id: str  # unique source contract id
    title: str
    contract_type: str = ""  # e.g. "service_agreement"
    parties: list[Party] = Field(default_factory=list)
    effective_date: str = ""  # ISO 8601
    termination_date: str = ""  # ISO 8601
    clauses: list[Clause] = Field(default_factory=list)
    key_facts: list[KeyFact] = Field(default_factory=list)
    # Additional metadata
    governing_law: str = ""
    notice_period_days: int = 30

    def clause_ids(self) -> set[str]:
        return {c.id for c in self.clauses}

    def get_clause(self, cid: str) -> Clause | None:
        for c in self.clauses:
            if c.id == cid:
                return c
        return None

    def xref_facts(self) -> list[KeyFact]:
        return [kf for kf in self.key_facts if kf.kind == KeyFactKind.XREF]

    def amount_facts(self) -> list[KeyFact]:
        return [kf for kf in self.key_facts if kf.kind == KeyFactKind.AMOUNT]

    def date_facts(self) -> list[KeyFact]:
        return [kf for kf in self.key_facts if kf.kind == KeyFactKind.DATE]

    def model_copy_deep(self) -> Contract:
        """Return a fully deep-copied Contract."""
        return self.model_copy(deep=True)


# ---------------------------------------------------------------------------
# Tamper records / labels
# ---------------------------------------------------------------------------


class TamperType(StrEnum):
    AMOUNT_FIGURE_ONLY = "amount_figure_only"
    AMOUNT_BOTH = "amount_both"
    DATE_SHIFT = "date_shift"
    PARTY_SWAP = "party_swap"
    CLAUSE_DELETE = "clause_delete"
    CLAUSE_INSERT = "clause_insert"
    XREF_BREAK = "xref_break"
    INCREMENTAL_EDIT = "incremental_edit"
    HIDDEN_TEXT = "hidden_text"


class TamperClass(StrEnum):
    CONTENT = "content"
    FILE = "file"


CONTENT_TAMPERS: set[TamperType] = {
    TamperType.AMOUNT_FIGURE_ONLY,
    TamperType.AMOUNT_BOTH,
    TamperType.DATE_SHIFT,
    TamperType.PARTY_SWAP,
    TamperType.CLAUSE_DELETE,
    TamperType.CLAUSE_INSERT,
    TamperType.XREF_BREAK,
}

FILE_TAMPERS: set[TamperType] = {
    TamperType.INCREMENTAL_EDIT,
    TamperType.HIDDEN_TEXT,
}


class TamperDetail(BaseModel):
    """Details of one applied tamper operation."""

    tamper_type: TamperType
    page: int | None = None  # 0-indexed page number (if known)
    clause_id: str | None = None
    original_value: str | None = None
    tampered_value: str | None = None
    subtype: str | None = None  # e.g. "figure_words_mismatch"
    dangling_xrefs: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class SourceType(StrEnum):
    SYNTHETIC = "synthetic"
    CUAD = "cuad"


class DocLabel(BaseModel):
    """Ground-truth label for one generated document."""

    doc_id: str
    source_id: str
    source_type: SourceType
    is_tampered: bool
    tamper_types: list[TamperType] = Field(default_factory=list)
    tamper_class: TamperClass | None = None
    tamper_details: list[TamperDetail] = Field(default_factory=list)
    seed: int
    generator_version: str
    sha256: str = ""
    split: str = ""  # "train" | "val" | "test"
