from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.dependencies import TokenData, get_drug_service, require_roles
from app.core.responses import ApiResponse, paginated_response, success_response
from app.models.common import PaginationParams
from app.models.drug import DrugCreate, DrugResponse, DrugSearchResult, DrugUpdate
from app.services.drug_service import DrugService

router = APIRouter(prefix="/drugs", tags=["drugs"])


@router.get("", response_model=ApiResponse[list[DrugResponse]])
async def list_drugs(
    pagination: PaginationParams = Depends(),
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    _current_user: TokenData = Depends(require_roles()),
    service: DrugService = Depends(get_drug_service),
) -> dict[str, Any]:
    drugs, total = await service.list(
        pagination=pagination, category=category, search=search
    )
    payload = [DrugResponse.model_validate(drug) for drug in drugs]
    return paginated_response(
        data=payload,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get("/search", response_model=ApiResponse[list[DrugSearchResult]])
async def search_drugs(
    q: str = Query(min_length=1),
    _current_user: TokenData = Depends(require_roles()),
    service: DrugService = Depends(get_drug_service),
) -> dict[str, Any]:
    results = await service.search_autocomplete(q)
    return success_response(data=results)


@router.get("/{drug_id}", response_model=ApiResponse[DrugResponse])
async def get_drug(
    drug_id: UUID,
    _current_user: TokenData = Depends(require_roles()),
    service: DrugService = Depends(get_drug_service),
) -> dict[str, Any]:
    drug = await service.get_by_id(drug_id)
    return success_response(data=DrugResponse.model_validate(drug))


@router.post(
    "",
    response_model=ApiResponse[DrugResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_drug(
    data: DrugCreate,
    _current_user: TokenData = Depends(require_roles("admin", "pharmacist")),
    service: DrugService = Depends(get_drug_service),
) -> dict[str, Any]:
    drug = await service.create(data)
    return success_response(data=DrugResponse.model_validate(drug))


@router.put("/{drug_id}", response_model=ApiResponse[DrugResponse])
async def update_drug(
    drug_id: UUID,
    data: DrugUpdate,
    _current_user: TokenData = Depends(require_roles("admin", "pharmacist")),
    service: DrugService = Depends(get_drug_service),
) -> dict[str, Any]:
    drug = await service.update(drug_id, data)
    return success_response(data=DrugResponse.model_validate(drug))


@router.delete("/{drug_id}", response_model=ApiResponse[dict[str, str]])
async def delete_drug(
    drug_id: UUID,
    _current_user: TokenData = Depends(require_roles("admin")),
    service: DrugService = Depends(get_drug_service),
) -> dict[str, Any]:
    await service.delete(drug_id)
    return success_response(data={"status": "deleted"})
