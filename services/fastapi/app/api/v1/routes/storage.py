from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.v1.dependencies import (
    TokenData,
    get_current_db_user,
    get_prescription_service,
    get_storage_service,
    require_roles,
)
from app.core.responses import ApiResponse, success_response
from app.db.models.user import User
from app.models.storage import StorageFileResponse
from app.services.prescription_service import PrescriptionService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/storage", tags=["storage"])


@router.post(
    "/upload",
    response_model=ApiResponse[StorageFileResponse],
    status_code=status.HTTP_201_CREATED,
)
async def upload_storage_file(
    prescription_id: UUID = Form(...),
    file: UploadFile = File(...),
    current_user: TokenData = Depends(require_roles()),
    current_db_user: User = Depends(get_current_db_user),
    prescription_service: PrescriptionService = Depends(get_prescription_service),
    storage_service: StorageService = Depends(get_storage_service),
) -> dict[str, Any]:
    await prescription_service.get_by_id(prescription_id, current_user)
    storage_file = await storage_service.upload_file(
        file=file,
        prescription_id=prescription_id,
        uploader_id=current_db_user.id,
    )
    return success_response(data=storage_file)


@router.get("/{file_id}/url", response_model=ApiResponse[dict[str, str]])
async def get_storage_file_url(
    file_id: UUID,
    current_user: TokenData = Depends(require_roles()),
    storage_service: StorageService = Depends(get_storage_service),
) -> dict[str, Any]:
    signed_url = await storage_service.get_signed_url(file_id, current_user)
    return success_response(data={"url": signed_url})
