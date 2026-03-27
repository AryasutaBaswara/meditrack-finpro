from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import (
    get_current_active_user,
    get_doctor_service,
    get_drug_service,
    get_patient_service,
)
from app.db.models.doctor import Doctor
from app.db.models.drug import Drug
from app.db.models.patient import Patient
from app.db.models.user import Profile, User
from app.main import app
from app.models.auth import TokenData


def build_user(*roles: str) -> TokenData:
    return TokenData(
        sub="kc-user-1",
        email="user@example.com",
        roles=list(roles),
    )


def build_drug() -> Drug:
    return Drug(
        id=uuid4(),
        name="Amoxicillin",
        generic_name="Amoxicillin",
        category="Antibiotic",
        description="Antibiotic capsule",
        stock=10,
        price=Decimal("15000.00"),
        unit="capsule",
        manufacturer="MediTrack Pharma",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


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


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class DrugServiceStub:
    def __init__(self, drug: Drug):
        self.drug = drug

    async def list(self, pagination=None, category=None, search=None):
        return [self.drug], 1

    async def search_autocomplete(self, _query):
        return [
            {
                "id": str(self.drug.id),
                "name": self.drug.name,
                "generic_name": self.drug.generic_name,
                "category": self.drug.category,
                "price": self.drug.price,
                "stock": self.drug.stock,
                "score": 1.0,
            }
        ]

    async def get_by_id(self, _drug_id):
        return self.drug

    async def create(self, _data):
        return self.drug

    async def update(self, _drug_id, _data):
        return self.drug

    async def delete(self, _drug_id):
        return None


class PatientServiceStub:
    def __init__(self, patient: Patient):
        self.patient = patient

    async def list(self, pagination=None, search=None):
        return [self.patient], 1

    def to_with_profile(self, patient: Patient):
        return {
            "id": patient.id,
            "user_id": patient.user_id,
            "blood_type": patient.blood_type,
            "allergies": patient.allergies,
            "emergency_contact": patient.emergency_contact,
            "created_at": patient.created_at,
            "full_name": patient.user.profile.full_name,
            "email": patient.user.email,
            "phone": patient.user.profile.phone,
        }

    async def get_with_profile(self, _patient_id):
        return self.to_with_profile(self.patient)

    async def get_prescription_history(self, _patient_id):
        return []

    async def create(self, _data):
        return self.patient

    async def update(self, _patient_id, _data):
        return self.patient


class DoctorServiceStub:
    def __init__(self, doctor: Doctor):
        self.doctor = doctor

    async def list(self, pagination=None, clinic_id=None):
        return [self.doctor], 1

    def to_with_profile(self, doctor: Doctor):
        return {
            "id": doctor.id,
            "user_id": doctor.user_id,
            "clinic_id": doctor.clinic_id,
            "sip_number": doctor.sip_number,
            "specialization": doctor.specialization,
            "created_at": doctor.created_at,
            "full_name": doctor.user.profile.full_name,
            "email": doctor.user.email,
        }

    async def get_with_profile(self, _doctor_id):
        return self.to_with_profile(self.doctor)

    async def create(self, _data):
        return self.doctor

    async def update(self, _doctor_id, _data):
        return self.doctor


def override_current_user(*roles: str):
    async def _override() -> TokenData:
        return build_user(*roles)

    return _override


@pytest.mark.asyncio
async def test_list_drugs_returns_paginated_envelope(client: AsyncClient):
    drug = build_drug()
    app.dependency_overrides[get_current_active_user] = override_current_user(
        "pharmacist"
    )
    app.dependency_overrides[get_drug_service] = lambda: DrugServiceStub(drug)

    response = await client.get("/api/v1/drugs?page=1&per_page=20")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["meta"] == {"total": 1, "page": 1, "per_page": 20}
    assert body["data"][0]["id"] == str(drug.id)


@pytest.mark.asyncio
async def test_create_drug_requires_admin_or_pharmacist(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_current_user("patient")

    response = await client.post(
        "/api/v1/drugs",
        json={
            "name": "Amoxicillin",
            "generic_name": "Amoxicillin",
            "category": "Antibiotic",
            "description": "Antibiotic capsule",
            "stock": 10,
            "price": "15000.00",
            "unit": "capsule",
            "manufacturer": "MediTrack Pharma",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_search_drugs_returns_success_envelope(client: AsyncClient):
    drug = build_drug()
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_drug_service] = lambda: DrugServiceStub(drug)

    response = await client.get("/api/v1/drugs/search?q=amox")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"][0]["name"] == "Amoxicillin"


@pytest.mark.asyncio
async def test_list_patients_returns_paginated_envelope(client: AsyncClient):
    patient = build_patient()
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_patient_service] = lambda: PatientServiceStub(patient)

    response = await client.get("/api/v1/patients?page=1&per_page=20")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["meta"] == {"total": 1, "page": 1, "per_page": 20}
    assert body["data"][0]["full_name"] == "Budi Santoso"


@pytest.mark.asyncio
async def test_create_patient_requires_admin(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")

    response = await client.post(
        "/api/v1/patients",
        json={
            "user_id": str(uuid4()),
            "blood_type": "O+",
            "allergies": "Penicillin",
            "emergency_contact": "08111",
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_patient_prescriptions_returns_success_envelope(client: AsyncClient):
    patient = build_patient()
    app.dependency_overrides[get_current_active_user] = override_current_user(
        "pharmacist"
    )
    app.dependency_overrides[get_patient_service] = lambda: PatientServiceStub(patient)

    response = await client.get(f"/api/v1/patients/{patient.id}/prescriptions")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"] == []


@pytest.mark.asyncio
async def test_list_doctors_requires_admin(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")

    response = await client.get("/api/v1/doctors?page=1&per_page=20")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_list_doctors_returns_paginated_envelope_for_admin(client: AsyncClient):
    doctor = build_doctor()
    app.dependency_overrides[get_current_active_user] = override_current_user("admin")
    app.dependency_overrides[get_doctor_service] = lambda: DoctorServiceStub(doctor)

    response = await client.get("/api/v1/doctors?page=1&per_page=20")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["meta"] == {"total": 1, "page": 1, "per_page": 20}
    assert body["data"][0]["full_name"] == "Dr. Arya"


@pytest.mark.asyncio
async def test_get_doctor_allows_doctor_role(client: AsyncClient):
    doctor = build_doctor()
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_doctor_service] = lambda: DoctorServiceStub(doctor)

    response = await client.get(f"/api/v1/doctors/{doctor.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["sip_number"] == "SIP-001"
