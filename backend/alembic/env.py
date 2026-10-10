"""Alembic environment configuration.

Uses the DATABASE_URL env var (or .env file) so the migration URL is never
hardcoded.  Compatible with both CLI (alembic upgrade head) and the
Docker Compose migrate service.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Add the src/ directory to sys.path so we can import clauseguard.
_backend_dir = Path(__file__).parent.parent
_src_dir = _backend_dir / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import clauseguard.db.models  # noqa: E402, F401  # ensure models are registered
from clauseguard.db.base import Base  # noqa: E402

config = context.config

# Override sqlalchemy.url from DATABASE_URL env var if set.
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
