from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import (
    TokenData,
    get_prescription_service,
    require_roles,
)
from app.core.responses import ApiResponse, paginated_response, success_response
from app.models.common import PaginationParams
from app.models.prescription import PrescriptionCreate, PrescriptionResponse
from app.services.prescription_service import PrescriptionService

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


@router.post(
    "",
    response_model=ApiResponse[PrescriptionResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_prescription(
    data: PrescriptionCreate,
    current_user: TokenData = Depends(require_roles("doctor")),
    service: PrescriptionService = Depends(get_prescription_service),
) -> dict[str, Any]:
    prescription = await service.create(data, current_user)
    return success_response(data=PrescriptionResponse.model_validate(prescription))


@router.get("", response_model=ApiResponse[list[PrescriptionResponse]])
async def list_prescriptions(
    pagination: PaginationParams = Depends(),
    current_user: TokenData = Depends(require_roles()),
    service: PrescriptionService = Depends(get_prescription_service),
) -> dict[str, Any]:
    prescriptions, total = await service.list(pagination, current_user)
    payload = [PrescriptionResponse.model_validate(item) for item in prescriptions]
    return paginated_response(
        data=payload,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get("/{prescription_id}", response_model=ApiResponse[PrescriptionResponse])
async def get_prescription(
    prescription_id: UUID,
    current_user: TokenData = Depends(require_roles()),
    service: PrescriptionService = Depends(get_prescription_service),
) -> dict[str, Any]:
    prescription = await service.get_by_id(prescription_id, current_user)
    return success_response(data=PrescriptionResponse.model_validate(prescription))


@router.post(
    "/{prescription_id}/cancel",
    response_model=ApiResponse[PrescriptionResponse],
)
async def cancel_prescription(
    prescription_id: UUID,
    current_user: TokenData = Depends(require_roles("doctor", "admin")),
    service: PrescriptionService = Depends(get_prescription_service),
) -> dict[str, Any]:
    prescription = await service.cancel(prescription_id, current_user)
    return success_response(data=PrescriptionResponse.model_validate(prescription))
