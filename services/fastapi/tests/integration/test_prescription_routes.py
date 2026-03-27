from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import get_current_active_user, get_prescription_service
from app.db.models.drug import Drug
from app.db.models.prescription import (
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.main import app
from app.models.auth import TokenData


def build_user(*roles: str) -> TokenData:
    return TokenData(
        sub="kc-user-1",
        email="user@example.com",
        roles=list(roles),
    )


def build_prescription() -> Prescription:
    prescription = Prescription(
        id=uuid4(),
        doctor_id=uuid4(),
        patient_id=uuid4(),
        status=PrescriptionStatus.VALIDATED,
        notes="Take after meals",
        interaction_check_result={
            "has_interactions": False,
            "severity": "none",
            "details": "No interaction found.",
            "drugs_checked": ["Amoxicillin"],
        },
        stock_check_result={
            "has_issues": False,
            "status": "ok",
            "details": "All requested drugs are available in stock.",
            "items": [],
        },
        created_at=datetime.now(timezone.utc),
    )
    drug = Drug(
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
    item = PrescriptionItem(
        id=uuid4(),
        prescription_id=prescription.id,
        drug_id=drug.id,
        dosage="500mg",
        frequency="3x daily",
        duration="5 days",
        quantity=2,
    )
    item.drug = drug
    prescription.items = [item]
    return prescription


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class PrescriptionServiceStub:
    def __init__(self, prescription: Prescription):
        self.prescription = prescription

    async def create(self, _data, _current_user):
        return self.prescription

    async def list(self, _pagination, _current_user):
        return [self.prescription], 1

    async def get_by_id(self, _prescription_id, _current_user):
        return self.prescription

    async def cancel(self, _prescription_id, _current_user):
        cancelled = build_prescription()
        cancelled.status = PrescriptionStatus.CANCELLED
        return cancelled


def override_current_user(*roles: str):
    async def _override() -> TokenData:
        return build_user(*roles)

    return _override


@pytest.mark.asyncio
async def test_create_prescription_returns_success_envelope(client: AsyncClient):
    prescription = build_prescription()
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_prescription_service] = (
        lambda: PrescriptionServiceStub(prescription)
    )

    response = await client.post(
        "/api/v1/prescriptions",
        json={
            "patient_id": str(prescription.patient_id),
            "notes": "Take after meals",
            "items": [
                {
                    "drug_id": str(prescription.items[0].drug_id),
                    "dosage": "500mg",
                    "frequency": "3x daily",
                    "duration": "5 days",
                    "quantity": 2,
                }
            ],
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == str(prescription.id)
    assert body["data"]["status"] == PrescriptionStatus.VALIDATED.value


@pytest.mark.asyncio
async def test_create_prescription_rejects_non_doctor(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_current_user("patient")

    response = await client.post(
        "/api/v1/prescriptions",
        json={
            "patient_id": str(uuid4()),
            "notes": None,
            "items": [
                {
                    "drug_id": str(uuid4()),
                    "dosage": "500mg",
                    "frequency": "3x daily",
                    "duration": "5 days",
                    "quantity": 2,
                }
            ],
        },
    )

    assert response.status_code == 403
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_list_prescriptions_returns_paginated_envelope(client: AsyncClient):
    prescription = build_prescription()
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_prescription_service] = (
        lambda: PrescriptionServiceStub(prescription)
    )

    response = await client.get("/api/v1/prescriptions?page=1&per_page=20")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["meta"] == {"total": 1, "page": 1, "per_page": 20}
    assert len(body["data"]) == 1
    assert body["data"][0]["id"] == str(prescription.id)


@pytest.mark.asyncio
async def test_get_prescription_returns_success_envelope(client: AsyncClient):
    prescription = build_prescription()
    app.dependency_overrides[get_current_active_user] = override_current_user("patient")
    app.dependency_overrides[get_prescription_service] = (
        lambda: PrescriptionServiceStub(prescription)
    )

    response = await client.get(f"/api/v1/prescriptions/{prescription.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == str(prescription.id)


@pytest.mark.asyncio
async def test_cancel_prescription_returns_success_envelope(client: AsyncClient):
    prescription = build_prescription()
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_prescription_service] = (
        lambda: PrescriptionServiceStub(prescription)
    )

    response = await client.post(f"/api/v1/prescriptions/{prescription.id}/cancel")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["status"] == PrescriptionStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_create_prescription_returns_validation_error_for_empty_items(
    client: AsyncClient,
):
    prescription = build_prescription()
    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_prescription_service] = (
        lambda: PrescriptionServiceStub(prescription)
    )

    response = await client.post(
        "/api/v1/prescriptions",
        json={
            "patient_id": str(uuid4()),
            "notes": "Take after meals",
            "items": [],
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"
