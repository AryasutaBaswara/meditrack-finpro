from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from app.core.config import settings
from app.db.models.drug import Drug


class SearchService:
    def __init__(self, es: AsyncElasticsearch):
        self.es = es
        self.index = settings.elasticsearch_index_drugs

    async def index_drug(self, drug: Drug) -> None:
        await self.es.index(
            index=self.index, id=str(drug.id), document=self._serialize_drug(drug)
        )

    async def search_drugs(self, query: str, size: int = 10) -> list[dict[str, Any]]:
        response = await self.es.search(
            index=self.index,
            size=size,
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "generic_name^2", "category"],
                    "fuzziness": "AUTO",
                }
            },
        )
        return [self._to_search_result(hit) for hit in response["hits"]["hits"]]

    async def autocomplete(self, query: str) -> list[dict[str, Any]]:
        response = await self.es.search(
            index=self.index,
            size=10,
            query={
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "generic_name^2"],
                    "type": "bool_prefix",
                }
            },
        )
        return [self._to_search_result(hit) for hit in response["hits"]["hits"]]

    async def delete_drug(self, drug_id: UUID) -> None:
        await self.es.delete(index=self.index, id=str(drug_id), ignore=[404])

    async def bulk_index_drugs(self, drugs: list[Drug]) -> None:
        if not drugs:
            return

        actions = [
            {
                "_op_type": "index",
                "_index": self.index,
                "_id": str(drug.id),
                "_source": self._serialize_drug(drug),
            }
            for drug in drugs
        ]
        await async_bulk(self.es, actions)

    def _serialize_drug(self, drug: Drug) -> dict[str, Any]:
        return {
            "id": str(drug.id),
            "name": drug.name,
            "generic_name": drug.generic_name,
            "category": drug.category,
            "description": drug.description,
            "stock": drug.stock,
            "price": str(drug.price) if isinstance(drug.price, Decimal) else drug.price,
            "unit": drug.unit,
            "manufacturer": drug.manufacturer,
        }

    def _to_search_result(self, hit: dict[str, Any]) -> dict[str, Any]:
        source = hit.get("_source", {})
        return {
            "id": source.get("id") or hit.get("_id"),
            "name": source.get("name"),
            "generic_name": source.get("generic_name"),
            "category": source.get("category"),
            "price": source.get("price"),
            "stock": source.get("stock", 0),
            "score": float(hit.get("_score", 0.0)),
        }
