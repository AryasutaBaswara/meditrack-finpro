from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.dependencies import TokenData, get_doctor_service, require_roles
from app.core.responses import ApiResponse, paginated_response, success_response
from app.models.common import PaginationParams
from app.models.doctor import (
    DoctorCreate,
    DoctorResponse,
    DoctorWithProfile,
    DoctorUpdate,
)
from app.services.doctor_service import DoctorService

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=ApiResponse[list[DoctorWithProfile]])
async def list_doctors(
    pagination: PaginationParams = Depends(),
    clinic_id: UUID | None = Query(default=None),
    _current_user: TokenData = Depends(require_roles("admin")),
    service: DoctorService = Depends(get_doctor_service),
) -> dict[str, Any]:
    doctors, total = await service.list(pagination=pagination, clinic_id=clinic_id)
    payload = [service.to_with_profile(doctor) for doctor in doctors]
    return paginated_response(
        data=payload,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get("/{doctor_id}", response_model=ApiResponse[DoctorWithProfile])
async def get_doctor(
    doctor_id: UUID,
    _current_user: TokenData = Depends(require_roles("admin", "doctor")),
    service: DoctorService = Depends(get_doctor_service),
) -> dict[str, Any]:
    doctor = await service.get_with_profile(doctor_id)
    return success_response(data=doctor)


@router.post(
    "",
    response_model=ApiResponse[DoctorResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_doctor(
    data: DoctorCreate,
    _current_user: TokenData = Depends(require_roles("admin")),
    service: DoctorService = Depends(get_doctor_service),
) -> dict[str, Any]:
    doctor = await service.create(data)
    return success_response(data=DoctorResponse.model_validate(doctor))


@router.put("/{doctor_id}", response_model=ApiResponse[DoctorResponse])
async def update_doctor(
    doctor_id: UUID,
    data: DoctorUpdate,
    _current_user: TokenData = Depends(require_roles("admin")),
    service: DoctorService = Depends(get_doctor_service),
) -> dict[str, Any]:
    doctor = await service.update(doctor_id, data)
    return success_response(data=DoctorResponse.model_validate(doctor))
