from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.dependencies import (
    TokenData,
    get_patient_service,
    require_roles,
)
from app.core.responses import ApiResponse, paginated_response, success_response
from app.models.common import PaginationParams
from app.models.patient import (
    PatientCreate,
    PatientResponse,
    PatientWithProfile,
    PatientUpdate,
)
from app.models.prescription import PrescriptionResponse
from app.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=ApiResponse[list[PatientWithProfile]])
async def list_patients(
    pagination: PaginationParams = Depends(),
    search: str | None = Query(default=None),
    _current_user: TokenData = Depends(require_roles("admin", "doctor", "pharmacist")),
    service: PatientService = Depends(get_patient_service),
) -> dict[str, Any]:
    patients, total = await service.list(pagination=pagination, search=search)
    payload = [service.to_with_profile(patient) for patient in patients]
    return paginated_response(
        data=payload,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@router.get("/{patient_id}", response_model=ApiResponse[PatientWithProfile])
async def get_patient(
    patient_id: UUID,
    _current_user: TokenData = Depends(require_roles("admin", "doctor", "pharmacist")),
    service: PatientService = Depends(get_patient_service),
) -> dict[str, Any]:
    patient = await service.get_with_profile(patient_id)
    return success_response(data=patient)


@router.get(
    "/{patient_id}/prescriptions",
    response_model=ApiResponse[list[PrescriptionResponse]],
)
async def get_patient_prescriptions(
    patient_id: UUID,
    _current_user: TokenData = Depends(require_roles("admin", "doctor", "pharmacist")),
    service: PatientService = Depends(get_patient_service),
) -> dict[str, Any]:
    prescriptions = await service.get_prescription_history(patient_id)
    return success_response(data=prescriptions)


@router.post(
    "",
    response_model=ApiResponse[PatientResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_patient(
    data: PatientCreate,
    _current_user: TokenData = Depends(require_roles("admin")),
    service: PatientService = Depends(get_patient_service),
) -> dict[str, Any]:
    patient = await service.create(data)
    return success_response(data=PatientResponse.model_validate(patient))


@router.put("/{patient_id}", response_model=ApiResponse[PatientResponse])
async def update_patient(
    patient_id: UUID,
    data: PatientUpdate,
    _current_user: TokenData = Depends(require_roles("admin", "doctor")),
    service: PatientService = Depends(get_patient_service),
) -> dict[str, Any]:
    patient = await service.update(patient_id, data)
    return success_response(data=PatientResponse.model_validate(patient))
