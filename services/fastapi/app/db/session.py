from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

ASYNC_PGBOUNCER_CONNECT_ARGS = {
    "prepared_statement_cache_size": 0,
}


def create_database_engine(
    database_url: str | None = None, **kwargs: Any
) -> AsyncEngine:
    connect_args = dict(ASYNC_PGBOUNCER_CONNECT_ARGS)
    user_connect_args = kwargs.pop("connect_args", None)
    if user_connect_args:
        connect_args.update(user_connect_args)

    return create_async_engine(
        database_url or settings.database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
        **kwargs,
    )


engine: AsyncEngine = create_database_engine(
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def close_db() -> None:
    await engine.dispose()
