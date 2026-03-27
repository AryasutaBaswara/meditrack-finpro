from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.db.models.drug import Drug
from app.services.search_service import SearchService


def build_service() -> tuple[SearchService, Mock]:
    es_client = Mock()
    es_client.index = AsyncMock()
    es_client.search = AsyncMock()
    es_client.delete = AsyncMock()
    return SearchService(es=es_client), es_client


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
    )


@pytest.mark.asyncio
async def test_index_drug_sends_serialized_document():
    service, es_client = build_service()
    drug = build_drug()

    await service.index_drug(drug)

    es_client.index.assert_awaited_once()
    kwargs = es_client.index.await_args.kwargs
    assert kwargs["id"] == str(drug.id)
    assert kwargs["document"]["price"] == "15000.00"


@pytest.mark.asyncio
async def test_search_drugs_returns_normalized_results():
    service, es_client = build_service()
    es_client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "drug-1",
                    "_score": 3.5,
                    "_source": {
                        "id": "drug-1",
                        "name": "Amoxicillin",
                        "generic_name": "Amoxicillin",
                        "category": "Antibiotic",
                        "price": "15000.00",
                        "stock": 10,
                    },
                }
            ]
        }
    }

    result = await service.search_drugs("amox")

    assert result == [
        {
            "id": "drug-1",
            "name": "Amoxicillin",
            "generic_name": "Amoxicillin",
            "category": "Antibiotic",
            "price": "15000.00",
            "stock": 10,
            "score": 3.5,
        }
    ]


@pytest.mark.asyncio
async def test_autocomplete_returns_normalized_results():
    service, es_client = build_service()
    es_client.search.return_value = {
        "hits": {
            "hits": [
                {
                    "_id": "drug-1",
                    "_score": 2.1,
                    "_source": {"name": "Amoxicillin", "category": "Antibiotic"},
                }
            ]
        }
    }

    result = await service.autocomplete("amo")

    assert result[0]["id"] == "drug-1"
    assert result[0]["score"] == 2.1


@pytest.mark.asyncio
async def test_delete_drug_uses_ignore_404():
    service, es_client = build_service()
    drug_id = uuid4()

    await service.delete_drug(drug_id)

    es_client.delete.assert_awaited_once_with(
        index=service.index,
        id=str(drug_id),
        ignore=[404],
    )


@pytest.mark.asyncio
async def test_bulk_index_drugs_noops_for_empty_list():
    service, _es_client = build_service()

    with patch("app.services.search_service.async_bulk", new=AsyncMock()) as bulk_mock:
        await service.bulk_index_drugs([])

    bulk_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_bulk_index_drugs_sends_all_actions():
    service, es_client = build_service()
    drugs = [build_drug(), build_drug()]

    with patch("app.services.search_service.async_bulk", new=AsyncMock()) as bulk_mock:
        await service.bulk_index_drugs(drugs)

    bulk_mock.assert_awaited_once()
    args = bulk_mock.await_args.args
    assert args[0] is es_client
    assert len(args[1]) == 2
    assert args[1][0]["_op_type"] == "index"


def test_to_search_result_falls_back_to_hit_id_and_default_score():
    service, _es_client = build_service()

    result = service._to_search_result({"_id": "drug-1", "_source": {"name": "A"}})

    assert result == {
        "id": "drug-1",
        "name": "A",
        "generic_name": None,
        "category": None,
        "price": None,
        "stock": 0,
        "score": 0.0,
    }
