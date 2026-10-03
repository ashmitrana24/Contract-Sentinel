"""Local-disk file store for uploaded PDFs.

Design:
- Storage key is derived ONLY from the sha256 hash (no filename component)
  so there is no path-traversal risk and re-uploading the same bytes is a no-op.
- Writes are atomic: write to a temp file, then os.replace() (POSIX atomic).
- The directory tree is two-level (first 2 chars of sha256) to avoid
  millions of files in one directory.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

from clauseguard.config import get_settings

logger = logging.getLogger(__name__)


def _key_to_path(storage_dir: Path, key: str) -> Path:
    """Convert a storage key (sha256 hex) to a filesystem path.

    Layout: <storage_dir>/<first2>/<sha256>.pdf
    """
    if len(key) < 4:
        raise ValueError(f"Storage key too short: {key!r}")
    return storage_dir / key[:2] / f"{key}.pdf"


class FileStore:
    """Local-disk file store.  Thread-safe for concurrent readers/writers."""

    def __init__(self, storage_dir: Path | str | None = None) -> None:
        if storage_dir is None:
            storage_dir = get_settings().storage_dir
        self._root = Path(storage_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        logger.debug("FileStore initialised at %s", self._root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, data: bytes, sha256: str) -> str:
        """Persist *data* and return its storage key (== sha256).

        Idempotent: if the file already exists the write is skipped.
        """
        key = sha256
        dest = _key_to_path(self._root, key)
        if dest.exists():
            logger.debug("FileStore: skip existing %s (%d bytes)", key, len(data))
            return key
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write via temp file + rename.
        fd, tmp_path = tempfile.mkstemp(dir=dest.parent, prefix=".tmp_")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp_path, dest)
        except Exception:
            # Clean up temp file on error.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        logger.debug("FileStore: saved %s (%d bytes)", key, len(data))
        return key

    def open(self, storage_key: str) -> bytes:
        """Return the raw bytes for *storage_key*.

        Raises FileNotFoundError if the key does not exist.
        """
        path = _key_to_path(self._root, storage_key)
        if not path.exists():
            raise FileNotFoundError(f"Storage key not found: {storage_key}")
        return path.read_bytes()

    def read(self, storage_key: str) -> bytes:
        """Alias for open()."""
        return self.open(storage_key)

    def exists(self, storage_key: str) -> bool:
        """Return True if *storage_key* is present in the store."""
        return _key_to_path(self._root, storage_key).exists()

    @property
    def root(self) -> Path:
        return self._root
