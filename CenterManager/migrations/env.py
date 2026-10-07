# -*- coding: utf-8 -*-
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Thêm src/ vào sys.path để import models
src_path = Path(__file__).resolve().parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Import Base và các models để Alembic biết metadata
from centermanager.database.base import Base
from centermanager.models import *  # noqa

# Alembic Config object
config = context.config

# Logging
# Production migration receives an already-keyed runtime connection from the
# application.  In that path, re-running fileConfig() would replace the root
# handlers installed by centermanager.core.logging and hide every post-migration
# application exception from the rotating log file.  Keep Alembic CLI behavior
# unchanged for standalone/dev migrations.
if (
    config.config_file_name is not None
    and config.attributes.get("connection") is None
):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Production SQLCipher migrations inject an already-keyed SQLAlchemy
    # connection through Config.attributes. This prevents Alembic from opening
    # the encrypted database again with the plain sqlite driver.
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        _run_with_connection(supplied_connection)
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        _run_with_connection(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
