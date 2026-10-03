"""Integration tests for the /healthz endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_healthz_healthy(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["postgres"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.integration
def test_healthz_unhealthy_postgres(client: TestClient) -> None:
    with patch("clauseguard.api.routes.pg_check", return_value=False):
        resp = client.get("/healthz")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["postgres"] == "unreachable"
        assert data["redis"] == "ok"


@pytest.mark.integration
def test_healthz_unhealthy_redis(client: TestClient) -> None:
    with patch("clauseguard.queue.streams.check_connection", return_value=False):
        resp = client.get("/healthz")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["postgres"] == "ok"
        assert data["redis"] == "unreachable"
