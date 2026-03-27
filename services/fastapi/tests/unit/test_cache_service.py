from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from app.services.cache_service import CacheService


class SampleModel(BaseModel):
    id: str
    name: str


def build_service() -> tuple[CacheService, Mock]:
    redis_client = Mock()
    redis_client.get = AsyncMock()
    redis_client.setex = AsyncMock()
    redis_client.delete = AsyncMock()
    redis_client.scan = AsyncMock()
    return CacheService(redis=redis_client), redis_client


@pytest.mark.asyncio
async def test_get_returns_none_when_cache_miss():
    service, redis_client = build_service()
    redis_client.get.return_value = None

    result = await service.get("missing")

    assert result is None


@pytest.mark.asyncio
async def test_get_deserializes_cached_json():
    service, redis_client = build_service()
    redis_client.get.return_value = '{"status":"ok","count":1}'

    result = await service.get("cached")

    assert result == {"status": "ok", "count": 1}


@pytest.mark.asyncio
async def test_set_serializes_supported_types():
    service, redis_client = build_service()
    model = SampleModel(id=str(uuid4()), name="Sample")
    payload = {
        "model": model,
        "uuid": uuid4(),
        "price": Decimal("10.50"),
        "created_at": datetime(2026, 3, 27, tzinfo=timezone.utc),
    }

    await service.set("cache-key", payload, ttl=600)

    redis_client.setex.assert_awaited_once()
    args = redis_client.setex.await_args.args
    assert args[0] == "cache-key"
    assert args[1] == 600
    assert '"name": "Sample"' in args[2]
    assert '"price": "10.50"' in args[2]


@pytest.mark.asyncio
async def test_delete_removes_single_key():
    service, redis_client = build_service()

    await service.delete("cache-key")

    redis_client.delete.assert_awaited_once_with("cache-key")


@pytest.mark.asyncio
async def test_delete_pattern_removes_all_scanned_keys():
    service, redis_client = build_service()
    redis_client.scan.side_effect = [
        (1, ["a", "b"]),
        (0, ["c"]),
    ]

    await service.delete_pattern("prescriptions:*")

    assert redis_client.scan.await_count == 2
    redis_client.delete.assert_awaited_once_with("a", "b", "c")


@pytest.mark.asyncio
async def test_delete_pattern_skips_delete_when_no_keys_found():
    service, redis_client = build_service()
    redis_client.scan.return_value = (0, [])

    await service.delete_pattern("prescriptions:*")

    redis_client.delete.assert_not_awaited()
