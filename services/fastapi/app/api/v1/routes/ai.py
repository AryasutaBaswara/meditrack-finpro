from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.dependencies import (
    TokenData,
    get_prescription_service,
    require_roles,
)
from app.core.responses import ApiResponse, success_response
from app.models.prescription import InteractionCheckRequest, InteractionCheckResponse
from app.services.prescription_service import PrescriptionService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post(
    "/check-interactions",
    response_model=ApiResponse[InteractionCheckResponse],
)
async def check_interactions(
    data: InteractionCheckRequest,
    _current_user: TokenData = Depends(require_roles("doctor", "pharmacist")),
    service: PrescriptionService = Depends(get_prescription_service),
) -> dict[str, Any]:
    result = await service.check_interactions(data.drug_ids)
    return success_response(data=result)
