from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import (
    DuplicateDispensationException,
    InvalidPrescriptionStateException,
    UnauthorizedException,
)
from app.db.models.dispensation import Dispensation
from app.db.models.prescription import Prescription, PrescriptionStatus
from app.db.models.user import User
from app.models.auth import TokenData
from app.models.dispensation import DispensationCreate
from app.services.dispensation_service import DispensationService


def build_service() -> tuple[DispensationService, Mock]:
    db = Mock()
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    return DispensationService(db=db), db


def build_user(*roles: str) -> TokenData:
    return TokenData(
        sub="kc-pharmacist-1", email="pharmacist@example.com", roles=list(roles)
    )


@pytest.mark.asyncio
async def test_dispense_moves_validated_prescription_to_completed(monkeypatch):
    service, db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
    )
    pharmacist = User(
        id=uuid4(),
        keycloak_sub="kc-pharmacist-1",
        email="pharmacist@example.com",
    )
    returned_dispensation = Dispensation(
        id=uuid4(),
        prescription_id=prescription.id,
        pharmacist_id=pharmacist.id,
        notes="Ready for pickup",
    )

    async def fake_get_prescription(_prescription_id):
        return prescription

    async def fake_get_user_by_sub(_sub):
        return pharmacist

    async def fake_get_by_prescription(_prescription_id):
        return None

    async def fake_get_by_id(_dispensation_id):
        return returned_dispensation

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)
    monkeypatch.setattr(service, "_get_user_by_sub", fake_get_user_by_sub)
    monkeypatch.setattr(service, "get_by_prescription", fake_get_by_prescription)
    monkeypatch.setattr(service, "get_by_id", fake_get_by_id)

    result = await service.dispense(
        DispensationCreate(prescription_id=prescription.id, notes="Ready for pickup"),
        build_user("pharmacist"),
    )

    created = db.add.call_args.args[0]
    assert created.prescription_id == prescription.id
    assert created.pharmacist_id == pharmacist.id
    assert prescription.status == PrescriptionStatus.COMPLETED
    assert result is returned_dispensation


@pytest.mark.asyncio
async def test_dispense_requires_pharmacist_role():
    service, _db = build_service()

    with pytest.raises(UnauthorizedException):
        await service.dispense(
            DispensationCreate(prescription_id=uuid4(), notes=None),
            build_user("doctor"),
        )


@pytest.mark.asyncio
async def test_dispense_rejects_non_validated_prescription(monkeypatch):
    service, _db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.DRAFT,
    )

    async def fake_get_prescription(_prescription_id):
        return prescription

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)

    with pytest.raises(InvalidPrescriptionStateException):
        await service.dispense(
            DispensationCreate(prescription_id=prescription.id, notes=None),
            build_user("pharmacist"),
        )


@pytest.mark.asyncio
async def test_dispense_rejects_duplicate_dispensation(monkeypatch):
    service, _db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
    )

    async def fake_get_prescription(_prescription_id):
        return prescription

    async def fake_get_by_prescription(_prescription_id):
        return Dispensation(
            id=uuid4(),
            prescription_id=prescription.id,
            pharmacist_id=uuid4(),
        )

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)
    monkeypatch.setattr(service, "get_by_prescription", fake_get_by_prescription)

    with pytest.raises(DuplicateDispensationException):
        await service.dispense(
            DispensationCreate(prescription_id=prescription.id, notes=None),
            build_user("pharmacist"),
        )
