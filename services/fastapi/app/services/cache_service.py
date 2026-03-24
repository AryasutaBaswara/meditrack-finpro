from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from redis.asyncio import Redis


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value)!r} is not JSON serializable")


class CacheService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get(self, key: str) -> dict[str, Any] | list[Any] | None:
        value = await self.redis.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        payload = json.dumps(value, default=_json_default)
        await self.redis.setex(key, ttl, payload)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def delete_pattern(self, pattern: str) -> None:
        cursor = 0
        keys: list[str] = []

        while True:
            cursor, batch = await self.redis.scan(
                cursor=cursor, match=pattern, count=100
            )
            keys.extend(batch)
            if cursor == 0:
                break

        if keys:
            await self.redis.delete(*keys)
