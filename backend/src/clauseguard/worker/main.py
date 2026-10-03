"""Worker entrypoint and main loop.

Runs reliable worker processing Redis Streams messages for ClauseGuard:
- Auto-claims idle messages from dead consumers (XAUTOCLAIM).
- Reads own pending messages (XREADGROUP with '0').
- Reads new messages (XREADGROUP with '>').
- Runs background sweeper periodically.
- Survives transient Redis and Postgres disconnects with backoff.
- Handles SIGTERM / SIGINT gracefully.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
import uuid
from typing import Any

from clauseguard.config import Settings, get_settings
from clauseguard.db.session import check_connection as check_db_connection
from clauseguard.logging_setup import configure_logging
from clauseguard.queue import streams as qs
from clauseguard.storage.file_store import FileStore
from clauseguard.worker.processor import process_job_message
from clauseguard.worker.sweeper import sweep_stuck_jobs

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        cfg: Settings | None = None,
        consumer_id: str | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.cfg = cfg or get_settings()
        self.consumer_id = consumer_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.stop_event = stop_event or threading.Event()
        self.store = FileStore(self.cfg.storage_dir)
        self.redis_client: Any = None
        self._last_sweep = 0.0

    def request_stop(self) -> None:
        """Signal the worker loop to stop gracefully."""
        self.stop_event.set()

    def _init_connections(self) -> None:
        """Connect to Redis and ensure consumer group exists. Retries with backoff."""
        attempt = 0
        while not self.stop_event.is_set():
            attempt += 1
            db_ok = check_db_connection()
            redis_ok = qs.check_connection(self.cfg.redis_url)

            if db_ok and redis_ok:
                try:
                    self.redis_client = qs._make_client(self.cfg.redis_url)
                    qs.ensure_consumer_group(
                        self.redis_client,
                        self.cfg.redis_stream,
                        self.cfg.redis_consumer_group,
                    )
                    logger.info(
                        "Worker %s initialized successfully (group: %s, stream: %s)",
                        self.consumer_id,
                        self.cfg.redis_consumer_group,
                        self.cfg.redis_stream,
                    )
                    return
                except Exception as exc:
                    logger.warning("Error initializing consumer group (attempt %d): %s", attempt, exc)
            else:
                logger.warning(
                    "Service check failed (attempt %d): DB=%s, Redis=%s. Waiting to retry...",
                    attempt,
                    db_ok,
                    redis_ok,
                )

            # Backoff wait
            sleep_time = min(5.0, 0.5 * (2 ** min(attempt - 1, 4)))
            self.stop_event.wait(timeout=sleep_time)

    def run_once(self) -> int:
        """Process one batch of messages (autoclaim + pending + new) and return processed count."""
        if not self.redis_client:
            self._init_connections()
        if not self.redis_client or self.stop_event.is_set():
            return 0

        processed = 0

        # Run sweeper periodically
        now = time.time()
        if now - self._last_sweep >= self.cfg.sweeper_interval_seconds:
            try:
                sweep_stuck_jobs(self.redis_client, self.cfg)
            except Exception as e:
                logger.warning("Sweeper cycle encountered an error: %s", e)
            self._last_sweep = now

        # 1. Autoclaim messages idle longer than visibility_timeout_ms
        try:
            claimed = qs.autoclaim(
                self.redis_client,
                self.cfg.redis_stream,
                self.cfg.redis_consumer_group,
                self.consumer_id,
                min_idle_ms=self.cfg.visibility_timeout_ms,
                count=10,
            )
            for entry_id, fields in claimed:
                if self.stop_event.is_set():
                    break
                job_id = fields.get("job_id")
                if job_id:
                    process_job_message(job_id, entry_id, self.redis_client, store=self.store, cfg=self.cfg)
                    processed += 1
        except Exception as exc:
            logger.warning("Error in autoclaim: %s", exc)

        # 2. Read own pending messages (ID '0')
        if not self.stop_event.is_set():
            try:
                pending = qs.read_pending(
                    self.redis_client,
                    self.cfg.redis_stream,
                    self.cfg.redis_consumer_group,
                    self.consumer_id,
                    count=10,
                )
                for entry_id, fields in pending:
                    if self.stop_event.is_set():
                        break
                    job_id = fields.get("job_id")
                    if job_id:
                        process_job_message(job_id, entry_id, self.redis_client, store=self.store, cfg=self.cfg)
                        processed += 1
            except Exception as exc:
                logger.warning("Error reading pending messages: %s", exc)

        # 3. Read new messages (ID '>')
        if not self.stop_event.is_set():
            try:
                new_msgs = qs.read_new(
                    self.redis_client,
                    self.cfg.redis_stream,
                    self.cfg.redis_consumer_group,
                    self.consumer_id,
                    count=10,
                    block_ms=1000,
                )
                for entry_id, fields in new_msgs:
                    if self.stop_event.is_set():
                        break
                    job_id = fields.get("job_id")
                    if job_id:
                        process_job_message(job_id, entry_id, self.redis_client, store=self.store, cfg=self.cfg)
                        processed += 1
            except Exception as exc:
                logger.warning("Error reading new messages: %s", exc)

        return processed

    def run(self, max_batches: int | None = None) -> None:
        """Main worker loop."""
        self._init_connections()
        batches = 0
        logger.info("Worker loop started for %s", self.consumer_id)

        while not self.stop_event.is_set():
            try:
                self.run_once()
                batches += 1
                if max_batches is not None and batches >= max_batches:
                    break
            except Exception as exc:
                logger.error("Unhandled error in worker loop: %s", exc, exc_info=True)
                self.stop_event.wait(timeout=1.0)

        logger.info("Worker %s shutting down cleanly", self.consumer_id)


def start_worker(
    cfg: Settings | None = None,
    consumer_id: str | None = None,
    stop_event: threading.Event | None = None,
    max_batches: int | None = None,
) -> None:
    """Run a worker with signal handling."""
    worker = Worker(cfg=cfg, consumer_id=consumer_id, stop_event=stop_event)

    def _sig_handler(signum: int, _frame: Any) -> None:
        logger.info("Received signal %d; requesting stop...", signum)
        worker.request_stop()

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        signal.signal(signal.SIGTERM, _sig_handler)
    except (ValueError, AttributeError):
        pass  # Not in main thread or platform unsupported

    worker.run(max_batches=max_batches)


def main() -> None:
    configure_logging("INFO")
    start_worker()


if __name__ == "__main__":
    main()
