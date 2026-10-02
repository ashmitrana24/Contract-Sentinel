"""Abstract base class for all tamper operations.

Every tamper returns a (modified_artifact, TamperDetail) tuple.
- Content tampers operate on a Contract model (pre-render).
- File-level tampers operate on a PDF bytes / path (post-render).

If a tamper cannot be applied (e.g. no suitable clause exists),
it must raise TamperNotApplicable instead of silently emitting
a wrong or partial label.
"""

from __future__ import annotations

import abc
import random
from typing import Generic, TypeVar

from datagen.models import Contract, TamperDetail, TamperType

A = TypeVar("A")  # artifact type (Contract or bytes or Path)


class TamperNotApplicable(Exception):
    """Raised when a tamper cannot be applied to the given artifact."""


class Tamper(abc.ABC, Generic[A]):
    """Abstract base for all tamper operations."""

    tamper_type: TamperType  # must be set on subclass

    @abc.abstractmethod
    def apply(self, artifact: A, rng: random.Random) -> tuple[A, TamperDetail]:
        """Apply this tamper to *artifact*.

        Parameters
        ----------
        artifact:
            The object to modify. For content tampers this is a Contract;
            for file-level tampers it is a bytes object.
        rng:
            Seeded random.Random instance for reproducible choices.

        Returns
        -------
        tuple[A, TamperDetail]
            The modified artifact and a filled-in TamperDetail record.

        Raises
        ------
        TamperNotApplicable
            If this tamper cannot be meaningfully applied to the artifact.
        """


class ContentTamper(Tamper[Contract]):
    """Tampers that operate on a Contract model before rendering."""


class FileTamper(Tamper[bytes]):
    """Tampers that operate on already-rendered PDF bytes."""
