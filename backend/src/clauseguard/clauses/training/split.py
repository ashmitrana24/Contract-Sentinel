"""Contract-level train/validation/test dataset splitting.

Ensures:
- 60% Train / 20% Val / 20% Test partition.
- Partition is strictly at the contract level (zero contract leakage between splits).
- Deterministic permutation using a fixed seed (default 42).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetSplit:
    """Represents disjoint sets of contracts across splits."""

    train_contracts: tuple[str, ...]
    val_contracts: tuple[str, ...]
    test_contracts: tuple[str, ...]

    def __post_init__(self) -> None:
        train_s = set(self.train_contracts)
        val_s = set(self.val_contracts)
        test_s = set(self.test_contracts)

        assert train_s.isdisjoint(val_s), "Leakage detected: Train and Val overlap!"
        assert train_s.isdisjoint(test_s), "Leakage detected: Train and Test overlap!"
        assert val_s.isdisjoint(test_s), "Leakage detected: Val and Test overlap!"

    @property
    def total_contracts(self) -> int:
        return len(self.train_contracts) + len(self.val_contracts) + len(self.test_contracts)

    def get_split(self, contract_name: str) -> str:
        """Return 'train', 'val', or 'test' for contract_name, or 'unknown'."""
        if contract_name in self.train_contracts:
            return "train"
        if contract_name in self.val_contracts:
            return "val"
        if contract_name in self.test_contracts:
            return "test"
        return "unknown"


def partition_contracts(
    contracts: list[str],
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
    test_ratio: float = 0.20,
    seed: int = 42,
) -> DatasetSplit:
    """Partition a list of unique contract titles into Train, Val, and Test sets.

    Sorting first guarantees that permutation is independent of input order.
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "Ratios must sum to 1.0"

    unique_contracts = sorted(set(contracts))
    n = len(unique_contracts)
    if n == 0:
        return DatasetSplit(train_contracts=(), val_contracts=(), test_contracts=())

    # Deterministic shuffle
    rng = random.Random(seed)
    shuffled = list(unique_contracts)
    rng.shuffle(shuffled)

    n_train = round(n * train_ratio)
    n_val = round(n * val_ratio)

    train_set = tuple(shuffled[:n_train])
    val_set = tuple(shuffled[n_train : n_train + n_val])
    test_set = tuple(shuffled[n_train + n_val :])

    return DatasetSplit(
        train_contracts=train_set,
        val_contracts=val_set,
        test_contracts=test_set,
    )
