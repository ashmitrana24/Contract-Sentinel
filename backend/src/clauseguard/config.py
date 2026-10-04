"""Application configuration via pydantic-settings.

All secrets and tunables come from environment variables or a .env file.
No value is hardcoded here except sensible defaults.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg://clauseguard:clauseguard@localhost:5432/clauseguard",
        description="SQLAlchemy sync DSN (postgresql+psycopg://...)",
    )

    # --- Redis ---
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # --- Stream / queue names ---
    redis_stream: str = Field(default="cg:jobs", description="Redis Streams key for job queue")
    redis_consumer_group: str = Field(default="cg-workers", description="Consumer group name")
    redis_dead_stream: str = Field(default="cg:jobs:dead", description="Dead-letter stream key")

    # --- Storage ---
    storage_dir: str = Field(
        default="./storage",
        description="Root directory for uploaded PDF files",
    )

    # --- Upload limits ---
    max_upload_bytes: int = Field(
        default=25 * 1024 * 1024,
        description="Maximum accepted PDF size in bytes (25 MB default)",
    )
    max_pages: int = Field(
        default=500,
        description="Maximum accepted page count per document",
    )

    # --- Worker / job settings ---
    lease_seconds: int = Field(
        default=120,
        description="How long a worker lease on a job lasts before another worker can claim it",
    )
    visibility_timeout_ms: int = Field(
        default=60_000,
        description="XAUTOCLAIM idle threshold in milliseconds",
    )
    max_attempts: int = Field(
        default=5,
        description="Max job attempts before marking dead (transient_exhausted)",
    )
    backoff_base_seconds: float = Field(
        default=2.0,
        description="Base for exponential backoff (seconds)",
    )
    backoff_cap_seconds: float = Field(
        default=300.0,
        description="Maximum backoff delay (seconds)",
    )
    requeue_after_seconds: int = Field(
        default=120,
        description="Sweeper re-enqueues jobs whose enqueued_at is older than this",
    )
    sweeper_interval_seconds: int = Field(
        default=10,
        description="How often the sweeper loop runs inside each worker (seconds)",
    )

    # --- OCR threshold ---
    ocr_chars_per_page_threshold: int = Field(
        default=20,
        description="If avg chars/page falls below this, set needs_ocr=true",
    )

    # --- Forensics ---
    forensics_enabled: bool = Field(
        default=True,
        description="Whether to run PDF forensics analysis after parsing",
    )
    forensics_budget_seconds: float = Field(
        default=20.0,
        description="Per-document time budget for forensics analysis (seconds)",
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance, initializing on first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset cached settings so next get_settings() re-reads environment."""
    global _settings
    _settings = None
