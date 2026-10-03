"""Unit tests for FileStore."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from clauseguard.storage.file_store import FileStore


@pytest.mark.unit
def test_file_store_atomic_write_and_read(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    data = b"%PDF-1.4 test document content"
    digest = hashlib.sha256(data).hexdigest()

    key = store.save(data, digest)
    assert key == digest
    assert store.exists(key)
    assert store.read(key) == data
    assert store.open(key) == data


@pytest.mark.unit
def test_file_store_idempotent_save(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    data = b"%PDF-1.4 idempotent test content"
    digest = hashlib.sha256(data).hexdigest()

    # First write
    k1 = store.save(data, digest)
    file_path = store.root / digest[:2] / f"{digest}.pdf"
    mtime1 = file_path.stat().st_mtime_ns

    # Second write with same digest
    k2 = store.save(data, digest)
    assert k1 == k2
    mtime2 = file_path.stat().st_mtime_ns

    # File should not have been re-written
    assert mtime1 == mtime2


@pytest.mark.unit
def test_file_store_key_derived_from_hash_only(tmp_path: Path) -> None:
    """Verify that storage path is determined solely by the sha256 hash."""
    store = FileStore(tmp_path)
    data = b"Arbitrary bytes"
    digest = hashlib.sha256(data).hexdigest()
    store.save(data, digest)

    expected_path = tmp_path / digest[:2] / f"{digest}.pdf"
    assert expected_path.exists()
    assert expected_path.read_bytes() == data


@pytest.mark.unit
def test_file_store_missing_key_raises(tmp_path: Path) -> None:
    store = FileStore(tmp_path)
    with pytest.raises(FileNotFoundError):
        store.read("nonexistent_key_1234567890abcdef")
