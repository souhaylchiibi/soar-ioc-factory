"""Alembic environment — bound to the app settings and Base metadata.

Run from `backend/`:
    alembic revision --autogenerate -m "..."
    alembic upgrade head
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable when alembic runs from backend/ (env.py lives in database/migrations/).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.config import settings  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.models import ioc as ioc_models  # noqa: F401,E402  (register tables)
from app.models import account as account_models  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Allow `alembic upgrade head --sql` and tests to override via env var.
# `%` must be doubled: configparser treats it as interpolation syntax.
_db_url = os.environ.get("DATABASE_URL", settings.database_url)
config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL without a live connection."""
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
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
