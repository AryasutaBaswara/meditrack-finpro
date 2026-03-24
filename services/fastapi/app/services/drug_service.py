from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import DrugNotFoundException
from app.db.models.drug import Drug
from app.models.common import PaginationParams
from app.models.drug import DrugCreate, DrugSearchResult, DrugUpdate
from app.services.cache_service import CacheService
from app.services.search_service import SearchService


class DrugService:
    def __init__(
        self,
        db: AsyncSession,
        cache: CacheService,
        search: SearchService,
    ):
        self.db = db
        self.cache = cache
        self.search = search

    async def get_by_id(self, drug_id: UUID) -> Drug:
        result = await self.db.execute(self._base_query().where(Drug.id == drug_id))
        drug = result.scalar_one_or_none()
        if drug is None:
            raise DrugNotFoundException(drug_id)
        return drug

    async def list(
        self,
        pagination: PaginationParams,
        category: str | None,
        search: str | None,
    ) -> tuple[list[Drug], int]:
        cache_key = self._build_list_cache_key(pagination, category, search)
        cached = await self.cache.get(cache_key)
        if isinstance(cached, dict):
            ids = cached.get("ids", [])
            total = cached.get("total", 0)
            if isinstance(ids, list) and ids:
                drugs = await self._get_drugs_by_ids([UUID(drug_id) for drug_id in ids])
                return drugs, int(total)
            if isinstance(total, int):
                return [], total

        if search:
            search_hits = await self.search.search_drugs(
                query=search, size=pagination.per_page
            )
            ids = [UUID(hit["id"]) for hit in search_hits if hit.get("id")]
            drugs = await self._get_drugs_by_ids(ids)
            total = len(ids)
        else:
            filters: list[Any] = []
            if category:
                filters.append(Drug.category == category)

            count_query = (
                select(func.count())
                .select_from(Drug)
                .where(Drug.deleted_at.is_(None), *filters)
            )
            total = int((await self.db.execute(count_query)).scalar_one())

            sort_column = self._resolve_sort_column(pagination.sort_by)
            order_by = (
                sort_column.asc()
                if pagination.sort_order == "asc"
                else sort_column.desc()
            )
            query = (
                self._base_query()
                .where(*filters)
                .order_by(order_by)
                .offset(pagination.offset)
                .limit(pagination.per_page)
            )
            drugs = list((await self.db.execute(query)).scalars().all())
            ids = [drug.id for drug in drugs]

        await self.cache.set(
            cache_key,
            {"ids": [str(drug_id) for drug_id in ids], "total": total},
            ttl=settings.redis_ttl_drug_list,
        )
        return drugs, total

    async def create(self, data: DrugCreate) -> Drug:
        drug = Drug(**data.model_dump())
        self.db.add(drug)
        await self.db.flush()
        await self.db.refresh(drug)
        await self.search.index_drug(drug)
        await self._invalidate_list_cache()
        return drug

    async def update(self, drug_id: UUID, data: DrugUpdate) -> Drug:
        drug = await self.get_by_id(drug_id)
        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(drug, field_name, value)

        await self.db.flush()
        await self.db.refresh(drug)
        await self.search.index_drug(drug)
        await self._invalidate_list_cache()
        return drug

    async def delete(self, drug_id: UUID) -> None:
        drug = await self.get_by_id(drug_id)
        drug.deleted_at = datetime.now(UTC)
        await self.db.flush()
        await self.search.delete_drug(drug_id)
        await self._invalidate_list_cache()

    async def search_autocomplete(self, query: str) -> list[DrugSearchResult]:
        results = await self.search.autocomplete(query)
        return [DrugSearchResult.model_validate(result) for result in results]

    def _base_query(self) -> Select[tuple[Drug]]:
        return select(Drug).where(Drug.deleted_at.is_(None))

    async def _get_drugs_by_ids(self, ids: list[UUID]) -> list[Drug]:
        if not ids:
            return []

        ordering = case(
            {drug_id: index for index, drug_id in enumerate(ids)}, value=Drug.id
        )
        query = self._base_query().where(Drug.id.in_(ids)).order_by(ordering)
        return list((await self.db.execute(query)).scalars().all())

    def _build_list_cache_key(
        self,
        pagination: PaginationParams,
        category: str | None,
        search: str | None,
    ) -> str:
        payload = {
            "page": pagination.page,
            "per_page": pagination.per_page,
            "sort_by": pagination.sort_by,
            "sort_order": pagination.sort_order,
            "category": category,
            "search": search,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return f"drugs:list:{digest}"

    def _resolve_sort_column(self, sort_by: str):
        allowed_columns = {
            "created_at": Drug.created_at,
            "updated_at": Drug.updated_at,
            "name": Drug.name,
            "category": Drug.category,
            "stock": Drug.stock,
            "price": Drug.price,
        }
        return allowed_columns.get(sort_by, Drug.created_at)

    async def _invalidate_list_cache(self) -> None:
        await self.cache.delete_pattern("drugs:list:*")
