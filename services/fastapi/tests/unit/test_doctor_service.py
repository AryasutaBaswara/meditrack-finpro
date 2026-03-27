from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.core.exceptions import DoctorNotFoundException
from app.db.models.doctor import Doctor
from app.db.models.user import Profile, User
from app.models.common import PaginationParams
from app.models.doctor import DoctorCreate, DoctorUpdate
from app.services.doctor_service import DoctorService


def build_service() -> tuple[DoctorService, Mock]:
    db = Mock()
    db.add = Mock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return DoctorService(db=db), db


def build_doctor() -> Doctor:
    user = User(
        id=uuid4(),
        keycloak_sub="kc-doctor-1",
        email="doctor@example.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    user.profile = Profile(
        id=uuid4(),
        user_id=user.id,
        full_name="Dr. Arya",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    doctor = Doctor(
        id=uuid4(),
        user_id=user.id,
        clinic_id=uuid4(),
        sip_number="SIP-001",
        specialization="Internal Medicine",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    doctor.user = user
    return doctor


@pytest.mark.asyncio
async def test_get_by_id_raises_when_doctor_missing():
    service, db = build_service()
    db.execute.return_value = Mock(scalar_one_or_none=Mock(return_value=None))

    with pytest.raises(DoctorNotFoundException):
        await service.get_by_id(uuid4())


@pytest.mark.asyncio
async def test_list_returns_rows_and_total():
    service, db = build_service()
    doctor = build_doctor()
    db.execute.side_effect = [
        Mock(scalar_one=Mock(return_value=1)),
        Mock(scalars=Mock(return_value=Mock(all=Mock(return_value=[doctor])))),
    ]

    doctors, total = await service.list(
        PaginationParams(page=1, per_page=20), clinic_id=None
    )

    assert doctors == [doctor]
    assert total == 1


@pytest.mark.asyncio
async def test_create_persists_doctor():
    service, db = build_service()

    async def refresh_side_effect(instance):
        instance.id = instance.id or uuid4()
        instance.created_at = instance.created_at or datetime.now(timezone.utc)

    db.refresh.side_effect = refresh_side_effect

    doctor = await service.create(
        DoctorCreate(
            user_id=uuid4(),
            clinic_id=uuid4(),
            sip_number="SIP-001",
            specialization="Internal Medicine",
        )
    )

    assert doctor.sip_number == "SIP-001"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_update_applies_changes(monkeypatch):
    service, _db = build_service()
    doctor = build_doctor()

    async def fake_get_by_id(_doctor_id):
        return doctor

    monkeypatch.setattr(service, "get_by_id", fake_get_by_id)

    updated = await service.update(
        doctor.id,
        DoctorUpdate(specialization="Cardiology"),
    )

    assert updated.specialization == "Cardiology"


def test_to_with_profile_maps_related_user_and_profile():
    service, _db = build_service()
    doctor = build_doctor()

    result = service.to_with_profile(doctor)

    assert result.full_name == "Dr. Arya"
    assert result.email == "doctor@example.com"
