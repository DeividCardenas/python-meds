from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel

# Import pricing models so their metadata is registered
from app.models import pricing  # noqa: F401


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv(
    "DB_PRICING_URL",
    config.get_main_option("sqlalchemy.url"),
)
config.set_main_option("sqlalchemy.url", database_url)

# Only include pricing-related tables in this migration environment
_PRICING_TABLES = {
    "proveedores",
    "proveedor_aliases",
    "proveedor_archivos",
    "staging_precios_proveedor",
}

target_metadata = SQLModel.metadata


def include_object(object, name, type_, reflected, compare_to):  # noqa: A002
    if type_ == "table":
        return name in _PRICING_TABLES
    return True


def run_migrations_offline() -> None:
    url = database_url.replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio

    asyncio.run(run_migrations_online())
