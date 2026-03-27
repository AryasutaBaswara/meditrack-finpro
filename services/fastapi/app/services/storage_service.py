from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from supabase import Client

from app.core.config import settings
from app.core.exceptions import (
    PrescriptionNotFoundException,
    StorageException,
    StorageFileNotFoundException,
    UnauthorizedException,
)
from app.db.models.doctor import Doctor
from app.db.models.patient import Patient
from app.db.models.prescription import Prescription
from app.db.models.storage_file import StorageFile
from app.models.auth import TokenData
from app.models.storage import StorageFileResponse

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, supabase_client: Client, db: AsyncSession):
        self.supabase_client = supabase_client
        self.db = db

    async def upload_file(
        self,
        file: UploadFile,
        prescription_id: UUID,
        uploader_id: UUID,
    ) -> StorageFileResponse:
        await self._get_prescription(prescription_id)
        content = await file.read()
        if not content:
            raise StorageException("Uploaded file is empty")

        object_path = self._build_storage_path(prescription_id, file.filename)
        content_type = file.content_type or "application/octet-stream"

        try:
            await asyncio.to_thread(
                self.supabase_client.storage.from_(
                    settings.storage_bucket_prescriptions
                ).upload,
                object_path,
                content,
                {"content-type": content_type},
            )
            file_url = await asyncio.to_thread(self._get_public_url, object_path)
        except Exception as exc:
            raise StorageException("Failed to upload file to Supabase Storage") from exc

        try:
            storage_file = StorageFile(
                prescription_id=prescription_id,
                uploaded_by=uploader_id,
                file_name=file.filename or Path(object_path).name,
                file_url=file_url,
                file_size=len(content),
                mime_type=file.content_type,
            )
            self.db.add(storage_file)
            await self.db.flush()
            await self.db.refresh(storage_file)
        except Exception as exc:
            await self._cleanup_uploaded_file(object_path)
            raise StorageException("Failed to persist uploaded file metadata") from exc

        return StorageFileResponse.model_validate(storage_file)

    async def get_signed_url(self, file_id: UUID, current_user: TokenData) -> str:
        storage_file = await self._get_storage_file(file_id)
        await self._authorize_access(storage_file, current_user)
        object_path = self._extract_storage_path(storage_file.file_url)

        try:
            signed_url = await asyncio.to_thread(
                self._create_signed_url,
                object_path,
            )
        except Exception as exc:
            raise StorageException("Failed to generate signed URL") from exc

        if not signed_url:
            raise StorageException("Signed URL could not be generated")
        return signed_url

    async def _get_prescription(self, prescription_id: UUID) -> Prescription:
        result = await self.db.execute(
            select(Prescription).where(
                Prescription.id == prescription_id,
                Prescription.deleted_at.is_(None),
            )
        )
        prescription = result.scalar_one_or_none()
        if prescription is None:
            raise PrescriptionNotFoundException(prescription_id)
        return prescription

    async def _get_storage_file(self, file_id: UUID) -> StorageFile:
        result = await self.db.execute(
            select(StorageFile)
            .options(
                selectinload(StorageFile.uploader),
                selectinload(StorageFile.prescription)
                .selectinload(Prescription.doctor)
                .selectinload(Doctor.user),
                selectinload(StorageFile.prescription)
                .selectinload(Prescription.patient)
                .selectinload(Patient.user),
            )
            .where(StorageFile.id == file_id)
        )
        storage_file = result.scalar_one_or_none()
        if storage_file is None:
            raise StorageFileNotFoundException(file_id)
        return storage_file

    async def _authorize_access(
        self, storage_file: StorageFile, current_user: TokenData
    ) -> None:
        if "admin" in current_user.roles or "pharmacist" in current_user.roles:
            return

        prescription = storage_file.prescription
        if prescription is None:
            raise UnauthorizedException("This file is not attached to a prescription")
        if prescription.deleted_at is not None:
            raise UnauthorizedException("This file is no longer accessible")

        if "doctor" in current_user.roles:
            doctor_user = prescription.doctor.user if prescription.doctor else None
            if doctor_user and doctor_user.keycloak_sub == current_user.sub:
                return

        if "patient" in current_user.roles:
            patient_user = prescription.patient.user if prescription.patient else None
            if patient_user and patient_user.keycloak_sub == current_user.sub:
                return

        raise UnauthorizedException("Insufficient permissions to access this file")

    def _build_storage_path(self, prescription_id: UUID, file_name: str | None) -> str:
        normalized_name = self._sanitize_filename(file_name)
        return f"{prescription_id}/{uuid4().hex}-{normalized_name}"

    def _sanitize_filename(self, file_name: str | None) -> str:
        original_name = (file_name or "upload.bin").strip()
        safe_name = Path(original_name).name.replace(" ", "_")
        return safe_name or "upload.bin"

    def _get_public_url(self, object_path: str) -> str:
        response = self.supabase_client.storage.from_(
            settings.storage_bucket_prescriptions
        ).get_public_url(object_path)
        return self._extract_url_value(response)

    def _create_signed_url(self, object_path: str) -> str:
        response = self.supabase_client.storage.from_(
            settings.storage_bucket_prescriptions
        ).create_signed_url(object_path, settings.storage_signed_url_expiry)
        return self._extract_url_value(response)

    async def _cleanup_uploaded_file(self, object_path: str) -> None:
        try:
            await asyncio.to_thread(
                self.supabase_client.storage.from_(
                    settings.storage_bucket_prescriptions
                ).remove,
                [object_path],
            )
        except Exception as cleanup_exc:
            logger.warning(
                "Failed to cleanup uploaded storage object %s: %s",
                object_path,
                cleanup_exc,
            )

    def _extract_url_value(self, response: object) -> str:
        if isinstance(response, str):
            return response

        if isinstance(response, dict):
            direct_keys = ("signedURL", "signedUrl", "publicURL", "publicUrl")
            for key in direct_keys:
                value = response.get(key)
                if isinstance(value, str) and value:
                    return value

            data = response.get("data")
            if isinstance(data, dict):
                for key in direct_keys:
                    value = data.get(key)
                    if isinstance(value, str) and value:
                        return value

        raise StorageException("Unexpected response returned by Supabase Storage")

    def _extract_storage_path(self, file_url: str) -> str:
        parsed = urlparse(file_url)
        candidate = file_url if not parsed.scheme else parsed.path
        bucket_prefixes = (
            f"/storage/v1/object/public/{settings.storage_bucket_prescriptions}/",
            f"/storage/v1/object/sign/{settings.storage_bucket_prescriptions}/",
            f"/storage/v1/object/authenticated/{settings.storage_bucket_prescriptions}/",
            f"{settings.storage_bucket_prescriptions}/",
        )

        for prefix in bucket_prefixes:
            if candidate.startswith(prefix):
                return unquote(candidate[len(prefix) :])

        if parsed.scheme:
            return unquote(parsed.path.rsplit("/", 1)[-1])

        return unquote(candidate.lstrip("/"))
