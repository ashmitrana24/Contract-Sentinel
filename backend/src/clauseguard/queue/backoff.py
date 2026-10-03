"""Exponential backoff with jitter.

Pure function – no side effects, injectable jitter source for testability.

Formula: min(cap, base * 2^(attempts - 1)) + jitter
where jitter is uniform in [0, 1) * base (full jitter variant).
"""

from __future__ import annotations

import random as _stdlib_random
from collections.abc import Callable


def compute_backoff(
    attempts: int,
    *,
    base: float = 2.0,
    cap: float = 300.0,
    jitter_fn: Callable[[float], float] | None = None,
) -> float:
    """Return the backoff duration in seconds for the given attempt count.

    Parameters
    ----------
    attempts:
        Number of attempts already made (>= 1).
    base:
        Base duration in seconds.
    cap:
        Maximum duration in seconds.
    jitter_fn:
        A callable that takes the base jitter range and returns a jitter value.
        Defaults to ``lambda x: random.uniform(0, x)``.
        Inject a deterministic function in tests.

    Returns
    -------
    float
        Delay in seconds (>= 0, <= cap + base jitter).
    """

    if attempts < 1:
        attempts = 1
    delay = min(cap, base * (2 ** (attempts - 1)))
    if jitter_fn is None:
        jitter = _stdlib_random.uniform(0.0, base)
    else:
        jitter = jitter_fn(base)
    return delay + jitter
