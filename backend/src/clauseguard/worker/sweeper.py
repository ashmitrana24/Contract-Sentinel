"""Background sweeper for stuck and scheduled-retry jobs.

Recovers jobs that were:
1. Committed to DB but failed initial XADD (enqueued_at is NULL or stuck in queued).
2. Placed in retry_wait and their next_attempt_at has arrived.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select

from clauseguard.config import Settings, get_settings
from clauseguard.db.models import Job
from clauseguard.db.session import get_session
from clauseguard.queue import streams as qs

logger = logging.getLogger(__name__)


def sweep_stuck_jobs(
    redis_client: qs._redis_mod.Redis,  # type: ignore[type-arg]
    cfg: Settings | None = None,
) -> int:
    """Find and re-enqueue stuck or ready-to-retry jobs.

    Returns the count of jobs enqueued.
    """
    if cfg is None:
        cfg = get_settings()

    now = datetime.now(UTC)
    stuck_threshold = now - timedelta(seconds=cfg.requeue_after_seconds)

    enqueued_count = 0

    with get_session() as session:
        # 1. Un-enqueued or stuck queued jobs
        # Jobs in 'queued' or 'pending' where enqueued_at is NULL or older than stuck_threshold
        stuck_jobs = session.execute(
            select(Job)
            .where(
                Job.status.in_(["queued", "pending"]),
                or_(
                    Job.enqueued_at.is_(None),
                    Job.enqueued_at < stuck_threshold,
                ),
            )
            .with_for_update(skip_locked=True)
        ).scalars().all()

        for job in stuck_jobs:
            try:
                qs.enqueue(redis_client, cfg.redis_stream, job.id)
                job.enqueued_at = now
                enqueued_count += 1
                logger.info("Sweeper recovered un-enqueued job %s", job.id)
            except Exception as exc:
                logger.error("Sweeper failed to enqueue job %s: %s", job.id, exc)

        # 2. Retry-ready jobs whose backoff has passed
        retry_jobs = session.execute(
            select(Job)
            .where(
                Job.status.in_(["retry_wait", "retry_pending"]),
                Job.next_attempt_at.is_not(None),
                Job.next_attempt_at <= now,
            )
            .with_for_update(skip_locked=True)
        ).scalars().all()

        for job in retry_jobs:
            try:
                qs.enqueue(redis_client, cfg.redis_stream, job.id)
                job.status = "queued"
                job.enqueued_at = now
                enqueued_count += 1
                logger.info("Sweeper re-enqueued retry job %s for attempt %d", job.id, job.attempts + 1)
            except Exception as exc:
                logger.error("Sweeper failed to re-enqueue retry job %s: %s", job.id, exc)

    return enqueued_count
