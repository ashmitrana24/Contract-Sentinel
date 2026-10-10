"""Consistency Checks engine (Module 4) for ClauseGuard."""

from clauseguard.consistency.models import (
    CONSISTENCY_MODULE,
    CONSISTENCY_VERSION,
    ConsistencyReport,
    ConsistencySettings,
    DetectorStatus,
)
from clauseguard.consistency.run import analyze

__all__ = [
    "CONSISTENCY_MODULE",
    "CONSISTENCY_VERSION",
    "ConsistencyReport",
    "ConsistencySettings",
    "DetectorStatus",
    "analyze",
]
