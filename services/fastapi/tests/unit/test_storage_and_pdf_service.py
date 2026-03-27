from __future__ import annotations

from datetime import date
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import StorageException, UnauthorizedException
from app.db.models.doctor import Doctor
from app.db.models.drug import Drug
from app.db.models.patient import Patient
from app.db.models.prescription import (
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.db.models.storage_file import StorageFile
from app.db.models.user import Profile, User
from app.models.auth import TokenData
from app.services.pdf_service import PDFService
from app.services.storage_service import StorageService


def build_storage_service() -> tuple[StorageService, Mock, Mock]:
    db = Mock()
    db.add = Mock()
    db.flush = AsyncMock()

    async def refresh_side_effect(instance):
        instance.id = instance.id or uuid4()
        instance.created_at = instance.created_at or datetime.now(timezone.utc)

    db.refresh = AsyncMock(side_effect=refresh_side_effect)
    db.execute = AsyncMock()
    supabase_client = Mock()
    return StorageService(supabase_client=supabase_client, db=db), db, supabase_client


def build_current_user(sub: str, *roles: str) -> TokenData:
    return TokenData(sub=sub, email=f"{sub}@example.com", roles=list(roles))


@pytest.mark.asyncio
async def test_upload_file_persists_storage_metadata(monkeypatch):
    service, db, supabase_client = build_storage_service()
    prescription_id = uuid4()
    uploader_id = uuid4()
    bucket = supabase_client.storage.from_.return_value
    bucket.upload = Mock(return_value={"path": "ok"})
    bucket.get_public_url = Mock(return_value="https://example.com/public/file.pdf")

    async def fake_get_prescription(_prescription_id):
        return Prescription(
            id=prescription_id,
            doctor_id=uuid4(),
            patient_id=uuid4(),
            status=PrescriptionStatus.VALIDATED,
        )

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)

    upload = Mock()
    upload.filename = "lab-result.pdf"
    upload.content_type = "application/pdf"
    upload.read = AsyncMock(return_value=b"fake-pdf-bytes")

    result = await service.upload_file(upload, prescription_id, uploader_id)

    saved = db.add.call_args.args[0]
    assert isinstance(saved, StorageFile)
    assert saved.prescription_id == prescription_id
    assert saved.uploaded_by == uploader_id
    assert saved.file_name == "lab-result.pdf"
    assert result.file_url == "https://example.com/public/file.pdf"


@pytest.mark.asyncio
async def test_get_signed_url_allows_prescription_owner_patient(monkeypatch):
    service, _db, supabase_client = build_storage_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.COMPLETED,
    )
    patient_user = User(
        id=uuid4(),
        keycloak_sub="kc-patient-1",
        email="patient@example.com",
    )
    prescription.patient = Patient(id=prescription.patient_id, user_id=patient_user.id)
    prescription.patient.user = patient_user
    storage_file = StorageFile(
        id=uuid4(),
        prescription_id=prescription.id,
        uploaded_by=uuid4(),
        file_name="lab.pdf",
        file_url="https://example.com/storage/v1/object/public/prescription-files/path/to/lab.pdf",
    )
    storage_file.prescription = prescription
    bucket = supabase_client.storage.from_.return_value
    bucket.create_signed_url = Mock(
        return_value={"signedURL": "https://signed.example.com/file"}
    )

    async def fake_get_storage_file(_file_id):
        return storage_file

    monkeypatch.setattr(service, "_get_storage_file", fake_get_storage_file)

    result = await service.get_signed_url(
        storage_file.id,
        build_current_user("kc-patient-1", "patient"),
    )

    assert result == "https://signed.example.com/file"


@pytest.mark.asyncio
async def test_get_signed_url_rejects_unrelated_user(monkeypatch):
    service, _db, _supabase_client = build_storage_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.COMPLETED,
    )
    doctor_user = User(
        id=uuid4(), keycloak_sub="kc-doctor-1", email="doctor@example.com"
    )
    patient_user = User(
        id=uuid4(), keycloak_sub="kc-patient-1", email="patient@example.com"
    )
    prescription.doctor = Doctor(
        id=prescription.doctor_id, user_id=doctor_user.id, sip_number="SIP-001"
    )
    prescription.doctor.user = doctor_user
    prescription.patient = Patient(id=prescription.patient_id, user_id=patient_user.id)
    prescription.patient.user = patient_user
    storage_file = StorageFile(
        id=uuid4(),
        prescription_id=prescription.id,
        uploaded_by=uuid4(),
        file_name="lab.pdf",
        file_url="https://example.com/storage/v1/object/public/prescription-files/path/to/lab.pdf",
    )
    storage_file.prescription = prescription

    async def fake_get_storage_file(_file_id):
        return storage_file

    monkeypatch.setattr(service, "_get_storage_file", fake_get_storage_file)

    with pytest.raises(UnauthorizedException):
        await service.get_signed_url(
            storage_file.id,
            build_current_user("kc-outsider-1", "patient"),
        )


@pytest.mark.asyncio
async def test_upload_file_cleans_up_object_when_metadata_persistence_fails(
    monkeypatch,
):
    service, db, supabase_client = build_storage_service()
    prescription_id = uuid4()
    uploader_id = uuid4()
    bucket = supabase_client.storage.from_.return_value
    bucket.upload = Mock(return_value={"path": "ok"})
    bucket.get_public_url = Mock(return_value="https://example.com/public/file.pdf")
    bucket.remove = Mock(return_value={"data": []})
    db.flush.side_effect = RuntimeError("db flush failed")

    async def fake_get_prescription(_prescription_id):
        return Prescription(
            id=prescription_id,
            doctor_id=uuid4(),
            patient_id=uuid4(),
            status=PrescriptionStatus.VALIDATED,
        )

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)

    upload = Mock()
    upload.filename = "lab-result.pdf"
    upload.content_type = "application/pdf"
    upload.read = AsyncMock(return_value=b"fake-pdf-bytes")

    with pytest.raises(StorageException):
        await service.upload_file(upload, prescription_id, uploader_id)

    assert bucket.remove.call_count == 1


@pytest.mark.asyncio
async def test_get_signed_url_rejects_deleted_prescription(monkeypatch):
    service, _db, _supabase_client = build_storage_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.COMPLETED,
    )
    prescription.deleted_at = datetime.now(timezone.utc)
    patient_user = User(
        id=uuid4(),
        keycloak_sub="kc-patient-1",
        email="patient@example.com",
    )
    prescription.patient = Patient(id=prescription.patient_id, user_id=patient_user.id)
    prescription.patient.user = patient_user
    storage_file = StorageFile(
        id=uuid4(),
        prescription_id=prescription.id,
        uploaded_by=uuid4(),
        file_name="lab.pdf",
        file_url="https://example.com/storage/v1/object/public/prescription-files/path/to/lab.pdf",
    )
    storage_file.prescription = prescription

    async def fake_get_storage_file(_file_id):
        return storage_file

    monkeypatch.setattr(service, "_get_storage_file", fake_get_storage_file)

    with pytest.raises(UnauthorizedException):
        await service.get_signed_url(
            storage_file.id,
            build_current_user("kc-patient-1", "patient"),
        )


@pytest.mark.asyncio
async def test_generate_prescription_pdf_returns_pdf_bytes(monkeypatch):
    service = PDFService()
    doctor_user = User(
        id=uuid4(), keycloak_sub="kc-doctor-1", email="doctor@example.com"
    )
    doctor_user.profile = Profile(
        id=uuid4(),
        user_id=doctor_user.id,
        full_name="Dr. Arya",
    )
    patient_user = User(
        id=uuid4(), keycloak_sub="kc-patient-1", email="patient@example.com"
    )
    patient_user.profile = Profile(
        id=uuid4(),
        user_id=patient_user.id,
        full_name="Budi Santoso",
        date_of_birth=date(1998, 6, 15),
    )
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
        interaction_check_result={
            "has_interactions": False,
            "severity": "none",
            "details": "No interaction found.",
        },
    )
    prescription.doctor = Doctor(
        id=prescription.doctor_id,
        user_id=doctor_user.id,
        sip_number="SIP-777",
        specialization="Internal Medicine",
    )
    prescription.doctor.user = doctor_user
    prescription.patient = Patient(
        id=prescription.patient_id,
        user_id=patient_user.id,
        blood_type="O+",
    )
    prescription.patient.user = patient_user
    prescription.items = [
        PrescriptionItem(
            id=uuid4(),
            prescription_id=prescription.id,
            drug_id=uuid4(),
            dosage="500mg",
            frequency="3x daily",
            duration="5 days",
            quantity=2,
        )
    ]
    prescription.items[0].drug = Drug(
        id=prescription.items[0].drug_id,
        name="Amoxicillin",
        category="Antibiotic",
        stock=20,
        price=Decimal("15000.00"),
        unit="capsule",
    )

    async def fake_get_prescription(_prescription_id, _db):
        return prescription

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)

    result = await service.generate_prescription_pdf(prescription.id, db=Mock())

    assert result.startswith(b"%PDF")
    assert len(result) > 500
