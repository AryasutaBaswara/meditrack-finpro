from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import InsufficientStockException, UnauthorizedException
from app.db.models.doctor import Doctor
from app.db.models.drug import Drug
from app.db.models.patient import Patient
from app.db.models.prescription import Prescription, PrescriptionStatus
from app.db.models.user import User
from app.models.auth import TokenData
from app.models.prescription import (
    InteractionCheckResponse,
    PrescriptionCreate,
    PrescriptionItemCreate,
)
from app.services.prescription_service import PrescriptionService


def build_service() -> tuple[PrescriptionService, Mock, AsyncMock, AsyncMock]:
    db = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()
    ai = AsyncMock()
    cache = AsyncMock()
    return PrescriptionService(db=db, ai=ai, cache=cache), db, ai, cache


def build_current_user(*roles: str) -> TokenData:
    return TokenData(sub="kc-user-1", email="doctor@example.com", roles=list(roles))


def build_prescription_create(patient_id) -> PrescriptionCreate:
    return PrescriptionCreate(
        patient_id=patient_id,
        notes="Take after meals",
        items=[
            PrescriptionItemCreate(
                drug_id=uuid4(),
                dosage="500mg",
                frequency="3x daily",
                duration="7 days",
                quantity=2,
            )
        ],
    )


@pytest.mark.asyncio
async def test_create_keeps_prescription_in_draft_on_severe_interaction(monkeypatch):
    service, db, ai, cache = build_service()
    user = User(id=uuid4(), keycloak_sub="kc-user-1", email="doctor@example.com")
    doctor = Doctor(id=uuid4(), user_id=user.id, sip_number="SIP-001")
    patient = Patient(id=uuid4(), user_id=uuid4())
    drug = Drug(
        id=uuid4(),
        name="Warfarin",
        category="Anticoagulant",
        stock=10,
        price=Decimal("10000.00"),
        unit="tablet",
    )
    returned_prescription = Prescription(
        id=uuid4(),
        doctor_id=doctor.id,
        patient_id=patient.id,
        status=PrescriptionStatus.DRAFT,
    )

    async def fake_get_user_by_sub(_sub):
        return user

    async def fake_get_doctor_for_user(_user_id):
        return doctor

    async def fake_get_patient(_patient_id):
        return patient

    async def fake_get_drugs_for_items(_items):
        return [drug]

    async def fake_get_prescription_with_items(_prescription_id):
        return returned_prescription

    monkeypatch.setattr(service, "_get_user_by_sub", fake_get_user_by_sub)
    monkeypatch.setattr(service, "_get_doctor_for_user", fake_get_doctor_for_user)
    monkeypatch.setattr(service, "_get_patient", fake_get_patient)
    monkeypatch.setattr(service, "_get_drugs_for_items", fake_get_drugs_for_items)
    monkeypatch.setattr(
        service, "_get_prescription_with_items", fake_get_prescription_with_items
    )
    ai.check_drug_interactions.return_value = InteractionCheckResponse(
        has_interactions=True,
        severity="severe",
        details="Severe interaction detected",
        drugs_checked=[drug.name],
    )

    payload = build_prescription_create(patient.id)
    result = await service.create(payload, build_current_user("doctor"))

    created_prescription = db.add.call_args.args[0]
    assert created_prescription.status == PrescriptionStatus.DRAFT
    assert created_prescription.interaction_check_result == {
        "has_interactions": True,
        "severity": "severe",
        "details": "Severe interaction detected",
        "drugs_checked": [drug.name],
    }
    cache.delete_pattern.assert_awaited_once_with("prescriptions:*")
    assert result is returned_prescription


@pytest.mark.asyncio
async def test_create_validates_prescription_on_non_severe_interaction(monkeypatch):
    service, db, ai, _cache = build_service()
    user = User(id=uuid4(), keycloak_sub="kc-user-1", email="doctor@example.com")
    doctor = Doctor(id=uuid4(), user_id=user.id, sip_number="SIP-001")
    patient = Patient(id=uuid4(), user_id=uuid4())
    drug = Drug(
        id=uuid4(),
        name="Amoxicillin",
        category="Antibiotic",
        stock=10,
        price=Decimal("15000.00"),
        unit="capsule",
    )

    async def fake_get_user_by_sub(_sub):
        return user

    async def fake_get_doctor_for_user(_user_id):
        return doctor

    async def fake_get_patient(_patient_id):
        return patient

    async def fake_get_drugs_for_items(_items):
        return [drug]

    async def fake_get_prescription_with_items(_prescription_id):
        return Prescription(
            id=uuid4(),
            doctor_id=doctor.id,
            patient_id=patient.id,
            status=PrescriptionStatus.VALIDATED,
        )

    monkeypatch.setattr(service, "_get_user_by_sub", fake_get_user_by_sub)
    monkeypatch.setattr(service, "_get_doctor_for_user", fake_get_doctor_for_user)
    monkeypatch.setattr(service, "_get_patient", fake_get_patient)
    monkeypatch.setattr(service, "_get_drugs_for_items", fake_get_drugs_for_items)
    monkeypatch.setattr(
        service, "_get_prescription_with_items", fake_get_prescription_with_items
    )
    ai.check_drug_interactions.return_value = InteractionCheckResponse(
        has_interactions=True,
        severity="moderate",
        details="Monitor the patient",
        drugs_checked=[drug.name],
    )

    payload = build_prescription_create(patient.id)
    await service.create(payload, build_current_user("doctor"))

    created_prescription = db.add.call_args.args[0]
    assert created_prescription.status == PrescriptionStatus.VALIDATED


@pytest.mark.asyncio
async def test_get_drugs_for_items_raises_when_stock_is_insufficient(monkeypatch):
    service, _db, _ai, _cache = build_service()
    drug_id = uuid4()
    items = [
        PrescriptionItemCreate(
            drug_id=drug_id,
            dosage="10mg",
            frequency="1x daily",
            duration="5 days",
            quantity=3,
        )
    ]
    drug = Drug(
        id=drug_id,
        name="Aspirin",
        category="Pain Relief",
        stock=1,
        price=Decimal("5000.00"),
        unit="tablet",
    )

    async def fake_get_drugs_by_ids(_drug_ids):
        return [drug]

    monkeypatch.setattr(service, "_get_drugs_by_ids", fake_get_drugs_by_ids)

    with pytest.raises(InsufficientStockException):
        await service._get_drugs_for_items(items)


@pytest.mark.asyncio
async def test_get_by_id_rejects_access_to_other_doctors_prescription(monkeypatch):
    service, _db, _ai, _cache = build_service()
    current_user = build_current_user("doctor")
    current_db_user = User(
        id=uuid4(), keycloak_sub=current_user.sub, email=current_user.email
    )
    current_doctor = Doctor(
        id=uuid4(), user_id=current_db_user.id, sip_number="SIP-SELF"
    )
    other_prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.DRAFT,
    )

    async def fake_get_prescription_with_items(_prescription_id):
        return other_prescription

    async def fake_get_user_by_sub(_sub):
        return current_db_user

    async def fake_get_doctor_for_user(_user_id):
        return current_doctor

    monkeypatch.setattr(
        service, "_get_prescription_with_items", fake_get_prescription_with_items
    )
    monkeypatch.setattr(service, "_get_user_by_sub", fake_get_user_by_sub)
    monkeypatch.setattr(service, "_get_doctor_for_user", fake_get_doctor_for_user)

    with pytest.raises(UnauthorizedException):
        await service.get_by_id(other_prescription.id, current_user)


@pytest.mark.asyncio
async def test_get_by_id_rejects_access_to_other_patients_prescription(monkeypatch):
    service, _db, _ai, _cache = build_service()
    current_user = build_current_user("patient")
    current_db_user = User(
        id=uuid4(), keycloak_sub=current_user.sub, email=current_user.email
    )
    current_patient = Patient(id=uuid4(), user_id=current_db_user.id)
    other_prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.DRAFT,
    )

    async def fake_get_prescription_with_items(_prescription_id):
        return other_prescription

    async def fake_get_user_by_sub(_sub):
        return current_db_user

    async def fake_get_patient_for_user(_user_id):
        return current_patient

    monkeypatch.setattr(
        service, "_get_prescription_with_items", fake_get_prescription_with_items
    )
    monkeypatch.setattr(service, "_get_user_by_sub", fake_get_user_by_sub)
    monkeypatch.setattr(service, "_get_patient_for_user", fake_get_patient_for_user)

    with pytest.raises(UnauthorizedException):
        await service.get_by_id(other_prescription.id, current_user)
