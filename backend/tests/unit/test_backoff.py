"""Unit tests for exponential backoff function."""

from __future__ import annotations

import pytest

from clauseguard.queue.backoff import compute_backoff


@pytest.mark.unit
def test_backoff_growth() -> None:
    """Test exponential growth without jitter."""
    zero_jitter = lambda _: 0.0  # noqa: E731

    # Base = 2.0 -> attempts 1, 2, 3, 4 -> 2, 4, 8, 16
    assert compute_backoff(1, base=2.0, cap=100.0, jitter_fn=zero_jitter) == 2.0
    assert compute_backoff(2, base=2.0, cap=100.0, jitter_fn=zero_jitter) == 4.0
    assert compute_backoff(3, base=2.0, cap=100.0, jitter_fn=zero_jitter) == 8.0
    assert compute_backoff(4, base=2.0, cap=100.0, jitter_fn=zero_jitter) == 16.0


@pytest.mark.unit
def test_backoff_cap() -> None:
    """Test that exponential delay is bounded by cap."""
    zero_jitter = lambda _: 0.0  # noqa: E731
    assert compute_backoff(10, base=2.0, cap=30.0, jitter_fn=zero_jitter) == 30.0


@pytest.mark.unit
def test_backoff_jitter_bounds() -> None:
    """Test full jitter bounds: delay in [base * 2^(att-1), base * 2^(att-1) + base]."""
    for _ in range(50):
        val = compute_backoff(1, base=2.0, cap=100.0)
        assert 2.0 <= val <= 4.0

    for _ in range(50):
        val = compute_backoff(3, base=2.0, cap=100.0)
        # delay = 8.0, jitter in [0, 2.0]
        assert 8.0 <= val <= 10.0


@pytest.mark.unit
def test_backoff_zero_or_negative_attempts() -> None:
    """Negative or zero attempts are clamped to 1."""
    zero_jitter = lambda _: 0.0  # noqa: E731
    assert compute_backoff(0, base=2.0, cap=100.0, jitter_fn=zero_jitter) == 2.0
    assert compute_backoff(-5, base=2.0, cap=100.0, jitter_fn=zero_jitter) == 2.0
