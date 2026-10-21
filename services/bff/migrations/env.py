"""Alembic 环境：异步引擎（asyncpg）。"""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from contexture_bff.adapters.sessions import metadata

target_metadata = metadata


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    url = context.config.get_main_option("sqlalchemy.url")
    assert url  # noqa: S101
    engine = create_async_engine(url)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


asyncio.run(_run_async())
