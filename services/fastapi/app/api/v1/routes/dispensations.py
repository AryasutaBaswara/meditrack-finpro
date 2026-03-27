from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import (
    TokenData,
    get_dispensation_service,
    require_roles,
)
from app.core.responses import ApiResponse, success_response
from app.models.dispensation import DispensationCreate, DispensationResponse
from app.services.dispensation_service import DispensationService

router = APIRouter(prefix="/dispensations", tags=["dispensations"])


@router.post(
    "",
    response_model=ApiResponse[DispensationResponse],
    status_code=status.HTTP_201_CREATED,
)
async def dispense_prescription(
    data: DispensationCreate,
    current_user: TokenData = Depends(require_roles("pharmacist")),
    service: DispensationService = Depends(get_dispensation_service),
) -> dict[str, Any]:
    dispensation = await service.dispense(data, current_user)
    return success_response(data=DispensationResponse.model_validate(dispensation))


@router.get("/{dispensation_id}", response_model=ApiResponse[DispensationResponse])
async def get_dispensation(
    dispensation_id: UUID,
    _current_user: TokenData = Depends(require_roles("pharmacist", "admin")),
    service: DispensationService = Depends(get_dispensation_service),
) -> dict[str, Any]:
    dispensation = await service.get_by_id(dispensation_id)
    return success_response(data=DispensationResponse.model_validate(dispensation))
