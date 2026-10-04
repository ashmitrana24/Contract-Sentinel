"""Shared Finding schema used by all analysis modules.

Every later module (forensics, risk scoring, etc.) returns a list of Finding.
This module is unused in Module 2 but fully implemented here so downstream
modules can import it.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    """One risk or integrity finding produced by an analysis module."""

    module: str = Field(description="Name of the module that produced this finding")
    type: str = Field(description="Machine-readable finding type, e.g. 'amount_mismatch'")
    severity: Severity
    page: int | None = Field(default=None, description="1-based page number, if localised")
    clause_ref: str | None = Field(
        default=None, description="Clause ID the finding relates to, e.g. '4.2'"
    )
    bbox: (
        Annotated[
            tuple[float, float, float, float],
            Field(description="Bounding box [x0, y0, x1, y1] in PDF points"),
        ]
        | None
    ) = None
    evidence: str = Field(description="Verbatim text or data that triggered this finding")
    explanation: str = Field(description="Human-readable explanation of why this is a finding")
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model confidence, 0-1 or null if rule-based",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Detector-specific extra data (revision numbers, diffs, etc.)",
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: object) -> object:
        if v is None:
            return v
        f = float(v)  # type: ignore[arg-type]
        return max(0.0, min(1.0, f))

    @model_validator(mode="after")
    def _bbox_length(self) -> Finding:
        if self.bbox is not None and len(self.bbox) != 4:
            raise ValueError("bbox must have exactly 4 floats")
        return self

    def model_dump_json_roundtrip(self) -> Finding:
        """Serialize to JSON and back – useful in tests to verify round-trip."""
        raw = self.model_dump_json()
        return Finding.model_validate_json(raw)

    @classmethod
    def from_json(cls, data: str | bytes) -> Finding:
        """Deserialise from a JSON string."""
        return cls.model_validate(json.loads(data))
