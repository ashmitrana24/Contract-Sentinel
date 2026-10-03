"""Redis Streams helpers for the ClauseGuard job queue.

Stream layout:
  - cg:jobs          – main job stream
  - cg:jobs:dead     – dead-letter stream

Message payload: {job_id: "<uuid>"}

Consumer group is created with MKSTREAM on first use.
BUSYGROUP errors are silenced (group already exists).

XAUTOCLAIM compatibility: handles both the 2-element (old redis-py < 4.5)
and 3-element (new) return tuple shapes.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import redis as _redis_mod

logger = logging.getLogger(__name__)


def _make_client(redis_url: str) -> _redis_mod.Redis:  # type: ignore[type-arg]
    return _redis_mod.Redis.from_url(redis_url, decode_responses=True)


def ensure_consumer_group(
    client: _redis_mod.Redis,  # type: ignore[type-arg]
    stream: str,
    group: str,
) -> None:
    """Create the consumer group, silencing BUSYGROUP if it already exists."""
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
        logger.info("Created consumer group %r on stream %r", group, stream)
    except _redis_mod.exceptions.ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            logger.debug("Consumer group %r already exists on %r", group, stream)
        else:
            raise


def enqueue(
    client: _redis_mod.Redis,  # type: ignore[type-arg]
    stream: str,
    job_id: uuid.UUID | str,
) -> str:
    """XADD a job_id to *stream*.  Returns the generated stream entry ID."""
    entry_id: str = client.xadd(stream, {"job_id": str(job_id)})  # type: ignore[assignment]
    logger.debug("Enqueued job %s -> entry %s", job_id, entry_id)
    return entry_id


def read_pending(
    client: _redis_mod.Redis,  # type: ignore[type-arg]
    stream: str,
    group: str,
    consumer: str,
    count: int = 10,
) -> list[tuple[str, dict[str, str]]]:
    """Read THIS consumer's own pending messages (id='0').

    Returns list of (entry_id, fields).
    """
    raw = client.xreadgroup(
        group,
        consumer,
        {stream: "0"},
        count=count,
        noack=False,
    )
    return _parse_xreadgroup(raw)


def read_new(
    client: _redis_mod.Redis,  # type: ignore[type-arg]
    stream: str,
    group: str,
    consumer: str,
    count: int = 1,
    block_ms: int = 500,
) -> list[tuple[str, dict[str, str]]]:
    """Read new (undelivered) messages from the stream.

    Returns list of (entry_id, fields).
    """
    raw = client.xreadgroup(
        group,
        consumer,
        {stream: ">"},
        count=count,
        block=block_ms,
        noack=False,
    )
    return _parse_xreadgroup(raw)


def autoclaim(
    client: _redis_mod.Redis,  # type: ignore[type-arg]
    stream: str,
    group: str,
    consumer: str,
    min_idle_ms: int,
    count: int = 10,
    start_id: str = "0-0",
) -> list[tuple[str, dict[str, str]]]:
    """Claim messages idle longer than *min_idle_ms* from dead consumers.

    Handles both 2-element and 3-element return shapes of XAUTOCLAIM
    across redis-py versions.

    Returns list of (entry_id, fields).
    """
    result = client.xautoclaim(
        stream,
        group,
        consumer,
        min_idle_time=min_idle_ms,
        start_id=start_id,
        count=count,
    )
    # redis-py < 4.5 returns (next_id, entries)
    # redis-py >= 4.5 returns (next_id, entries, deleted_ids)
    if isinstance(result, (list, tuple)) and len(result) >= 2:
        entries = result[1]
    else:
        entries = result  # type: ignore[assignment]

    if not entries:
        return []

    # entries is list of [entry_id, {field: value}]
    return [(str(e[0]), dict(e[1])) for e in entries if e]


def ack(
    client: _redis_mod.Redis,  # type: ignore[type-arg]
    stream: str,
    group: str,
    entry_id: str,
) -> None:
    """Acknowledge message *entry_id* in the consumer group."""
    client.xack(stream, group, entry_id)
    logger.debug("ACKed entry %s on %r", entry_id, stream)


def enqueue_dead(
    client: _redis_mod.Redis,  # type: ignore[type-arg]
    dead_stream: str,
    job_id: uuid.UUID | str,
    reason: str,
    error_kind: str,
) -> str:
    """Add a dead job to the dead-letter stream."""
    entry_id: str = client.xadd(  # type: ignore[assignment]
        dead_stream,
        {
            "job_id": str(job_id),
            "reason": reason[:4096],
            "error_kind": error_kind,
        },
    )
    logger.info("Dead-lettered job %s (%s): %s", job_id, error_kind, reason[:200])
    return entry_id


def check_connection(redis_url: str) -> bool:
    """Return True if Redis is reachable."""
    try:
        client = _make_client(redis_url)
        client.ping()
        return True
    except Exception:
        return False


def _parse_xreadgroup(raw: Any) -> list[tuple[str, dict[str, str]]]:
    """Normalise the return value of xreadgroup into (entry_id, fields) pairs."""
    if not raw:
        return []
    result: list[tuple[str, dict[str, str]]] = []
    # raw is list of [stream_name, [(entry_id, {fields})]]
    for _stream_name, entries in raw:
        if not entries:
            continue
        for entry_id, fields in entries:
            result.append((str(entry_id), dict(fields)))
    return result
