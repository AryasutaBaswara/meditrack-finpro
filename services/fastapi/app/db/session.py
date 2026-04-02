from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings

ASYNC_PGBOUNCER_CONNECT_ARGS = {
    "prepared_statement_cache_size": 0,
    "statement_cache_size": 0,
}


def _uses_connection_pooler(database_url: str) -> bool:
    url = make_url(database_url)
    host = (url.host or "").lower()
    port = url.port
    return "pooler.supabase.com" in host or port in {6543, 54329}


def create_database_engine(
    database_url: str | None = None, **kwargs: Any
) -> AsyncEngine:
    resolved_database_url = database_url or settings.database_url
    connect_args = dict(ASYNC_PGBOUNCER_CONNECT_ARGS)
    user_connect_args = kwargs.pop("connect_args", None)
    if user_connect_args:
        connect_args.update(user_connect_args)

    if _uses_connection_pooler(resolved_database_url):
        connect_args.setdefault(
            "prepared_statement_name_func",
            lambda: f"__asyncpg_{uuid4()}__",
        )
        kwargs.pop("pool_size", None)
        kwargs.pop("max_overflow", None)
        kwargs.setdefault("poolclass", NullPool)

    return create_async_engine(
        resolved_database_url,
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
