"""Alembic env: use SQLModel metadata from shared package."""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

# Add repo root (hypeon) so "packages.shared" resolves
repo_root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from sqlmodel import SQLModel
from packages.shared.src import models  # noqa: F401
from packages.shared.src.db import get_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = SQLModel.metadata


def get_url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/hypeon")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    conf = config.get_section(config.config_ini_section, {}) or {}
    conf["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        conf,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
