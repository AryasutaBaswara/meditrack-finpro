from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import DrugNotFoundException
from app.db.models.drug import Drug
from app.models.common import PaginationParams
from app.models.drug import DrugCreate, DrugUpdate
from app.services.drug_service import DrugService


def build_service() -> tuple[DrugService, Mock, AsyncMock, AsyncMock]:
    db = Mock()
    db.add = Mock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    cache = AsyncMock()
    search = AsyncMock()
    return DrugService(db=db, cache=cache, search=search), db, cache, search


def build_drug() -> Drug:
    return Drug(
        id=uuid4(),
        name="Amoxicillin",
        generic_name="Amoxicillin",
        category="Antibiotic",
        description="Antibiotic capsule",
        stock=10,
        price=Decimal("15000.00"),
        unit="capsule",
        manufacturer="MediTrack Pharma",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_get_by_id_raises_when_drug_missing():
    service, db, _cache, _search = build_service()
    db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=None))

    with pytest.raises(DrugNotFoundException):
        await service.get_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_returns_cached_ids_without_search_or_count(monkeypatch):
    service, _db, cache, _search = build_service()
    drug = build_drug()
    pagination = PaginationParams(page=1, per_page=20)
    cache.get.return_value = {"ids": [str(drug.id)], "total": 1}

    async def fake_get_drugs_by_ids(ids):
        assert ids == [drug.id]
        return [drug]

    monkeypatch.setattr(service, "_get_drugs_by_ids", fake_get_drugs_by_ids)

    drugs, total = await service.list(pagination, category=None, search=None)

    assert drugs == [drug]
    assert total == 1


@pytest.mark.asyncio
async def test_list_returns_empty_cached_total_without_db_fetch():
    service, db, cache, _search = build_service()
    pagination = PaginationParams(page=1, per_page=20)
    cache.get.return_value = {"ids": [], "total": 0}

    drugs, total = await service.list(pagination, category=None, search=None)

    assert drugs == []
    assert total == 0
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_uses_search_hits_and_caches_result(monkeypatch):
    service, _db, cache, search = build_service()
    drug = build_drug()
    pagination = PaginationParams(page=1, per_page=20)
    cache.get.return_value = None
    search.search_drugs.return_value = [{"id": str(drug.id)}]

    async def fake_get_drugs_by_ids(ids):
        assert ids == [drug.id]
        return [drug]

    monkeypatch.setattr(service, "_get_drugs_by_ids", fake_get_drugs_by_ids)

    drugs, total = await service.list(pagination, category=None, search="amox")

    assert drugs == [drug]
    assert total == 1
    cache.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_persists_drug_and_invalidates_cache():
    service, db, cache, search = build_service()

    async def refresh_side_effect(instance):
        instance.id = instance.id or uuid4()
        instance.created_at = instance.created_at or datetime.now(timezone.utc)
        instance.updated_at = instance.updated_at or datetime.now(timezone.utc)

    db.refresh.side_effect = refresh_side_effect

    data = DrugCreate(
        name="Amoxicillin",
        generic_name="Amoxicillin",
        category="Antibiotic",
        description="Antibiotic capsule",
        stock=10,
        price=Decimal("15000.00"),
        unit="capsule",
        manufacturer="MediTrack Pharma",
    )

    drug = await service.create(data)

    assert drug.name == "Amoxicillin"
    db.flush.assert_awaited_once()
    cache.delete_pattern.assert_awaited_once_with("drugs:list:*")
    # index_drug is handled by DB triggers, not expected here
    search.index_drug.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_applies_changes_and_invalidates_cache(monkeypatch):
    service, db, cache, search = build_service()
    drug = build_drug()

    async def fake_get_by_id(_drug_id):
        return drug

    monkeypatch.setattr(service, "get_by_id", fake_get_by_id)

    updated = await service.update(
        drug.id, DrugUpdate(stock=3, manufacturer="Updated Pharma")
    )

    assert updated.stock == 3
    assert updated.manufacturer == "Updated Pharma"
    db.flush.assert_awaited_once()
    cache.delete_pattern.assert_awaited_once_with("drugs:list:*")
    # index_drug is handled by DB triggers, not expected here
    search.index_drug.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_soft_deletes_and_invalidates(monkeypatch):
    service, db, cache, search = build_service()
    drug = build_drug()

    async def fake_get_by_id(_drug_id):
        return drug

    monkeypatch.setattr(service, "get_by_id", fake_get_by_id)

    await service.delete(drug.id)

    assert drug.deleted_at is not None
    db.flush.assert_awaited_once()
    cache.delete_pattern.assert_awaited_once_with("drugs:list:*")
    # delete_drug is handled by DB triggers, not expected here
    search.delete_drug.assert_not_awaited()


def test_build_list_cache_key_changes_with_query_inputs():
    service, _db, _cache, _search = build_service()
    pagination = PaginationParams(page=1, per_page=20)

    key_one = service._build_list_cache_key(pagination, category=None, search=None)
    key_two = service._build_list_cache_key(
        pagination, category="Antibiotic", search=None
    )

    assert key_one != key_two
    assert key_one.startswith("drugs:list:")
