from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from app.core.config import get_settings
from app.db.database import Base

# ==========================================================
# IMPORT SQLALCHEMY MODELS
#
# Alembic autogenerate detects only tables registered
# inside Base.metadata, so models must be imported here.
# ==========================================================

from app.models.deployment import Deployment  # noqa: F401
from app.models.model_request import ModelRequest  # noqa: F401
from app.models.user import User  # noqa: F401


# ==========================================================
# ALEMBIC CONFIGURATION
# ==========================================================

config = context.config


# ==========================================================
# LOGGING
# ==========================================================

if config.config_file_name is not None:
    fileConfig(
        config.config_file_name
    )


# ==========================================================
# DATABASE URL
# ==========================================================

settings = get_settings()

config.set_main_option(
    "sqlalchemy.url",
    settings.database_url,
)


# ==========================================================
# SQLALCHEMY METADATA
# ==========================================================

target_metadata = Base.metadata


# ==========================================================
# OFFLINE MIGRATIONS
# ==========================================================

def run_migrations_offline() -> None:
    """
    Run migrations without opening a live database
    connection.
    """

    url = config.get_main_option(
        "sqlalchemy.url"
    )

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named"
        },
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ==========================================================
# ONLINE MIGRATIONS
# ==========================================================

def run_migrations_online() -> None:
    """
    Run migrations using a live database connection.
    """

    configuration = config.get_section(
        config.config_ini_section,
        {},
    )

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# ==========================================================
# ENTRYPOINT
# ==========================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
