"""Unit tests for contract-level split without leakage."""

from clauseguard.clauses.training.split import partition_contracts


def test_partition_contracts_zero_leakage():
    contracts = [f"Contract_{i}" for i in range(100)]
    split = partition_contracts(contracts, train_ratio=0.60, val_ratio=0.20, test_ratio=0.20, seed=42)

    assert len(split.train_contracts) == 60
    assert len(split.val_contracts) == 20
    assert len(split.test_contracts) == 20
    assert split.total_contracts == 100

    train_set = set(split.train_contracts)
    val_set = set(split.val_contracts)
    test_set = set(split.test_contracts)

    assert train_set.isdisjoint(val_set)
    assert train_set.isdisjoint(test_set)
    assert val_set.isdisjoint(test_set)
    assert train_set | val_set | test_set == set(contracts)


def test_partition_contracts_determinism():
    contracts = [f"Contract_{i}" for i in range(50)]
    s1 = partition_contracts(contracts, seed=123)
    s2 = partition_contracts(contracts, seed=123)
    assert s1.train_contracts == s2.train_contracts
    assert s1.val_contracts == s2.val_contracts
    assert s1.test_contracts == s2.test_contracts


def test_partition_contracts_odd_number():
    contracts = [f"Contract_{i}" for i in range(510)]
    split = partition_contracts(contracts, train_ratio=0.60, val_ratio=0.20, test_ratio=0.20, seed=42)
    assert len(split.train_contracts) == 306
    assert len(split.val_contracts) == 102
    assert len(split.test_contracts) == 102
    assert split.total_contracts == 510


def test_split_get_split():
    contracts = ["A", "B", "C", "D", "E"]
    split = partition_contracts(contracts, train_ratio=0.60, val_ratio=0.20, test_ratio=0.20, seed=42)
    for c in split.train_contracts:
        assert split.get_split(c) == "train"
    for c in split.val_contracts:
        assert split.get_split(c) == "val"
    for c in split.test_contracts:
        assert split.get_split(c) == "test"
    assert split.get_split("NonExistent") == "unknown"
