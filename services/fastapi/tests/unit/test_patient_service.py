from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import PatientNotFoundException
from app.db.models.patient import Patient
from app.db.models.user import Profile, User
from app.models.common import PaginationParams
from app.models.patient import PatientCreate, PatientUpdate
from app.services.patient_service import PatientService


def build_service() -> tuple[PatientService, Mock]:
    db = Mock()
    db.add = Mock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return PatientService(db=db), db


def build_patient() -> Patient:
    user = User(
        id=uuid4(),
        keycloak_sub="kc-patient-1",
        email="patient@example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    user.profile = Profile(
        id=uuid4(),
        user_id=user.id,
        full_name="Budi Santoso",
        phone="08123",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    patient = Patient(
        id=uuid4(),
        user_id=user.id,
        blood_type="O+",
        allergies="Penicillin",
        emergency_contact="08111",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    patient.user = user
    return patient


@pytest.mark.asyncio
async def test_get_by_id_raises_when_patient_missing():
    service, db = build_service()
    db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=None))

    with pytest.raises(PatientNotFoundException):
        await service.get_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_returns_rows_and_total():
    service, db = build_service()
    patient = build_patient()
    db.execute.side_effect = [
        Mock(scalar_one=Mock(return_value=1)),
        Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[patient])))),
    ]

    patients, total = await service.list(
        PaginationParams(page=1, per_page=20), search=None
    )

    assert patients == [patient]
    assert total == 1


@pytest.mark.asyncio
async def test_create_persists_patient():
    service, db = build_service()

    async def refresh_side_effect(instance):
        instance.id = instance.id or uuid4()
        instance.created_at = instance.created_at or datetime.now(timezone.utc)

    db.refresh.side_effect = refresh_side_effect

    patient = await service.create(
        PatientCreate(
            user_id=uuid4(),
            blood_type="O+",
            allergies="Penicillin",
            emergency_contact="08111",
        )
    )

    assert patient.blood_type == "O+"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_update_applies_changes(monkeypatch):
    service, _db = build_service()
    patient = build_patient()

    async def fake_get_by_id(_patient_id):
        return patient

    monkeypatch.setattr(service, "get_by_id", fake_get_by_id)

    updated = await service.update(
        patient.id,
        PatientUpdate(blood_type="A+", emergency_contact="08999"),
    )

    assert updated.blood_type == "A+"
    assert updated.emergency_contact == "08999"


def test_to_with_profile_maps_related_user_and_profile():
    service, _db = build_service()
    patient = build_patient()

    result = service.to_with_profile(patient)

    assert result.full_name == "Budi Santoso"
    assert result.email == "patient@example.com"
    assert result.phone == "08123"


@pytest.mark.asyncio
async def test_get_prescription_history_maps_rows(monkeypatch):
    service, db = build_service()
    patient = build_patient()
    row = {
        "id": uuid4(),
        "doctor_id": uuid4(),
        "patient_id": patient.id,
        "status": "validated",
        "notes": "Take after meals",
        "interaction_check_result": None,
        "created_at": datetime.now(timezone.utc),
        "stock_check_result": None,
        "items": [],
    }

    async def fake_get_by_id(_patient_id):
        return patient

    monkeypatch.setattr(service, "get_by_id", fake_get_by_id)
    db.execute.return_value = Mock(
        mappings=Mock(return_value=Mock(all=Mock(return_value=[row])))
    )

    history = await service.get_prescription_history(patient.id)

    assert len(history) == 1
    assert history[0].patient_id == patient.id
