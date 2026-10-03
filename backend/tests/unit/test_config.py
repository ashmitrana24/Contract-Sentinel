"""Unit tests for configuration."""

from __future__ import annotations

import pytest

from clauseguard.config import Settings


@pytest.mark.unit
def test_config_defaults() -> None:
    settings = Settings()
    assert "postgresql+psycopg://" in settings.database_url
    assert "redis://" in settings.redis_url
    assert settings.redis_stream == "cg:jobs"
    assert settings.max_upload_bytes == 25 * 1024 * 1024
    assert settings.max_pages == 500
    assert settings.lease_seconds == 120
    assert settings.visibility_timeout_ms == 60_000
    assert settings.max_attempts == 5


@pytest.mark.unit
def test_config_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAX_PAGES", "100")
    monkeypatch.setenv("LEASE_SECONDS", "45")
    monkeypatch.setenv("REDIS_STREAM", "cg:test_stream")

    settings = Settings()
    assert settings.max_pages == 100
    assert settings.lease_seconds == 45
    assert settings.redis_stream == "cg:test_stream"
