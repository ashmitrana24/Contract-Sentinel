"""Integration test fixtures with database truncation and isolated Redis streams."""

from __future__ import annotations

import uuid
from collections.abc import Generator
from pathlib import Path

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy import text

from clauseguard.api.main import create_app
from clauseguard.config import Settings, get_settings
from clauseguard.db.session import _get_engine
from clauseguard.storage.file_store import FileStore


@pytest.fixture(autouse=True)
def clean_db() -> Generator[None, None, None]:
    """Truncate all application tables before each integration test."""
    engine = _get_engine()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE clauses, pages, jobs, documents CASCADE"))
    yield
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE clauses, pages, jobs, documents CASCADE"))


@pytest.fixture
def test_cfg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Return Settings with unique stream name, consumer group, and tmp storage dir."""
    unique = uuid.uuid4().hex[:8]
    stream_name = f"cg:jobs:test_{unique}"
    group_name = f"cg-workers-test_{unique}"
    dead_stream = f"cg:jobs:dead:test_{unique}"
    storage_dir = str(tmp_path / "storage")

    monkeypatch.setenv("REDIS_STREAM", stream_name)
    monkeypatch.setenv("REDIS_CONSUMER_GROUP", group_name)
    monkeypatch.setenv("REDIS_DEAD_STREAM", dead_stream)
    monkeypatch.setenv("STORAGE_DIR", storage_dir)
    monkeypatch.setenv("REQUEUE_AFTER_SECONDS", "2")
    monkeypatch.setenv("SWEEPER_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("BACKOFF_BASE_SECONDS", "0.05")
    monkeypatch.setenv("BACKOFF_CAP_SECONDS", "1.0")

    from clauseguard.config import reset_settings
    reset_settings()
    cfg = get_settings()
    yield cfg
    reset_settings()


@pytest.fixture
def redis_client(test_cfg: Settings) -> Generator[redis.Redis, None, None]:
    """Provide Redis client and clean up test streams after test."""
    client: redis.Redis = redis.Redis.from_url(test_cfg.redis_url, decode_responses=True)
    yield client
    try:
        client.delete(test_cfg.redis_stream)
        client.delete(test_cfg.redis_dead_stream)
    except Exception:
        pass


@pytest.fixture
def file_store(test_cfg: Settings) -> FileStore:
    return FileStore(test_cfg.storage_dir)


@pytest.fixture
def client(test_cfg: Settings, file_store: FileStore) -> Generator[TestClient, None, None]:
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
