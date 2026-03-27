from __future__ import annotations

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    DispensationNotFoundException,
    DuplicateDispensationException,
    InsufficientStockException,
    InvalidPrescriptionStateException,
    UnauthorizedException,
)
from app.db.models.dispensation import Dispensation
from app.db.models.drug import Drug
from app.db.models.prescription import Prescription, PrescriptionStatus
from app.db.models.prescription import PrescriptionItem
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
    drug = Drug(
        id=uuid4(),
        name="Paracetamol",
        category="Analgesic",
        stock=10,
        price=5000,
        unit="tablet",
    )
    prescription.items = [
        PrescriptionItem(
            id=uuid4(),
            prescription_id=prescription.id,
            drug_id=drug.id,
            dosage="500mg",
            frequency="3x daily",
            duration="5 days",
            quantity=4,
        )
    ]
    prescription.items[0].drug = drug
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
    assert drug.stock == 6
    assert prescription.status == PrescriptionStatus.COMPLETED
    stock_logs = [call.args[0] for call in db.add.call_args_list if call.args]
    assert any(log.__class__.__name__ == "StockLog" for log in stock_logs)
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


@pytest.mark.asyncio
async def test_dispense_rejects_insufficient_stock(monkeypatch):
    service, _db = build_service()
    drug = Drug(
        id=uuid4(),
        name="Amoxicillin",
        category="Antibiotic",
        stock=1,
        price=12000,
        unit="capsule",
    )
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
    )
    prescription.items = [
        PrescriptionItem(
            id=uuid4(),
            prescription_id=prescription.id,
            drug_id=drug.id,
            dosage="500mg",
            frequency="3x daily",
            duration="5 days",
            quantity=2,
        )
    ]
    prescription.items[0].drug = drug

    async def fake_get_prescription(_prescription_id):
        return prescription

    async def fake_get_by_prescription(_prescription_id):
        return None

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)
    monkeypatch.setattr(service, "get_by_prescription", fake_get_by_prescription)

    with pytest.raises(InsufficientStockException):
        await service.dispense(
            DispensationCreate(prescription_id=prescription.id, notes=None),
            build_user("pharmacist"),
        )


@pytest.mark.asyncio
async def test_dispense_maps_unique_constraint_to_duplicate_exception(monkeypatch):
    service, db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
    )
    drug = Drug(
        id=uuid4(),
        name="Ibuprofen",
        category="NSAID",
        stock=5,
        price=9000,
        unit="tablet",
    )
    prescription.items = [
        PrescriptionItem(
            id=uuid4(),
            prescription_id=prescription.id,
            drug_id=drug.id,
            dosage="400mg",
            frequency="2x daily",
            duration="3 days",
            quantity=1,
        )
    ]
    prescription.items[0].drug = drug
    pharmacist = User(
        id=uuid4(),
        keycloak_sub="kc-pharmacist-1",
        email="pharmacist@example.com",
    )

    async def fake_get_prescription(_prescription_id):
        return prescription

    async def fake_get_user_by_sub(_sub):
        return pharmacist

    async def fake_get_by_prescription(_prescription_id):
        return None

    db.flush.side_effect = IntegrityError(
        "duplicate key value violates unique constraint on dispensations prescription_id",
        params=None,
        orig=Exception("duplicate"),
    )

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)
    monkeypatch.setattr(service, "_get_user_by_sub", fake_get_user_by_sub)
    monkeypatch.setattr(service, "get_by_prescription", fake_get_by_prescription)

    with pytest.raises(DuplicateDispensationException):
        await service.dispense(
            DispensationCreate(prescription_id=prescription.id, notes=None),
            build_user("pharmacist"),
        )


@pytest.mark.asyncio
async def test_dispense_rejects_cancelled_prescription(monkeypatch):
    service, _db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.CANCELLED,
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
async def test_dispense_rejects_completed_prescription_as_duplicate(monkeypatch):
    service, _db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.COMPLETED,
    )

    async def fake_get_prescription(_prescription_id):
        return prescription

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)

    with pytest.raises(DuplicateDispensationException):
        await service.dispense(
            DispensationCreate(prescription_id=prescription.id, notes=None),
            build_user("pharmacist"),
        )


@pytest.mark.asyncio
async def test_dispense_reraises_non_duplicate_integrity_error(monkeypatch):
    service, db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
    )
    prescription.items = []
    pharmacist = User(
        id=uuid4(),
        keycloak_sub="kc-pharmacist-1",
        email="pharmacist@example.com",
    )

    async def fake_get_prescription(_prescription_id):
        return prescription

    async def fake_get_user_by_sub(_sub):
        return pharmacist

    async def fake_get_by_prescription(_prescription_id):
        return None

    db.flush.side_effect = IntegrityError(
        "foreign key constraint violation",
        params=None,
        orig=Exception("fk"),
    )

    monkeypatch.setattr(service, "_get_prescription", fake_get_prescription)
    monkeypatch.setattr(service, "_get_user_by_sub", fake_get_user_by_sub)
    monkeypatch.setattr(service, "get_by_prescription", fake_get_by_prescription)

    with pytest.raises(IntegrityError):
        await service.dispense(
            DispensationCreate(prescription_id=prescription.id, notes=None),
            build_user("pharmacist"),
        )


@pytest.mark.asyncio
async def test_get_by_id_raises_when_dispensation_missing():
    service, db = build_service()
    db.execute = AsyncMock(
        return_value=Mock(scalar_one_or_none=Mock(return_value=None))
    )

    with pytest.raises(DispensationNotFoundException):
        await service.get_by_id(uuid4())


@pytest.mark.asyncio
async def test_get_user_by_sub_raises_when_user_missing():
    service, db = build_service()
    db.execute = AsyncMock(
        return_value=Mock(scalar_one_or_none=Mock(return_value=None))
    )

    with pytest.raises(UnauthorizedException):
        await service._get_user_by_sub("missing-user")


def test_apply_stock_changes_skips_items_without_drug():
    service, db = build_service()
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
    )
    prescription.items = [
        PrescriptionItem(
            id=uuid4(),
            prescription_id=prescription.id,
            drug_id=uuid4(),
            dosage="500mg",
            frequency="3x daily",
            duration="5 days",
            quantity=1,
        )
    ]
    prescription.items[0].drug = None

    service._apply_stock_changes(prescription)

    db.add.assert_not_called()
