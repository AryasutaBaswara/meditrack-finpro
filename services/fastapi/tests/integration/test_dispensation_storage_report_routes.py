from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import Mock
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies import (
    get_current_active_user,
    get_current_db_user,
    get_db,
    get_dispensation_service,
    get_pdf_service,
    get_prescription_service,
    get_storage_service,
)
from app.db.models.dispensation import Dispensation
from app.db.models.user import User
from app.main import app
from app.models.auth import TokenData
from app.models.storage import StorageFileResponse


def build_user(*roles: str) -> TokenData:
    return TokenData(
        sub="kc-user-1",
        email="user@example.com",
        roles=list(roles),
    )


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class DispensationServiceStub:
    def __init__(self, dispensation: Dispensation):
        self.dispensation = dispensation

    async def dispense(self, _data, _current_user):
        return self.dispensation

    async def get_by_id(self, _dispensation_id):
        return self.dispensation


class PrescriptionServiceStub:
    def __init__(self, prescription_id):
        self.prescription_id = prescription_id

    async def get_by_id(self, prescription_id, _current_user):
        return {"id": str(prescription_id or self.prescription_id)}


class StorageServiceStub:
    def __init__(self, storage_file: StorageFileResponse, signed_url: str):
        self.storage_file = storage_file
        self.signed_url = signed_url

    async def upload_file(self, file, prescription_id, uploader_id):
        assert file.filename == "lab.pdf"
        assert prescription_id == self.storage_file.prescription_id
        assert uploader_id is not None
        return self.storage_file

    async def get_signed_url(self, _file_id, _current_user):
        return self.signed_url


class PDFServiceStub:
    async def generate_prescription_pdf(self, _prescription_id, _db):
        return b"%PDF-1.4\nmock-pdf"


def override_current_user(*roles: str):
    async def _override() -> TokenData:
        return build_user(*roles)

    return _override


async def override_db() -> AsyncGenerator[Mock, None]:
    yield Mock(name="db-session")


@pytest.mark.asyncio
async def test_post_dispensation_returns_success_envelope(client: AsyncClient):
    prescription_id = uuid4()
    pharmacist_id = uuid4()
    dispensation = Dispensation(
        id=uuid4(),
        prescription_id=prescription_id,
        pharmacist_id=pharmacist_id,
        dispensed_at=datetime.now(timezone.utc),
        notes="Ready for pickup",
    )

    app.dependency_overrides[get_current_active_user] = override_current_user(
        "pharmacist"
    )
    app.dependency_overrides[get_dispensation_service] = (
        lambda: DispensationServiceStub(dispensation)
    )

    response = await client.post(
        "/api/v1/dispensations",
        json={"prescription_id": str(prescription_id), "notes": "Ready for pickup"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["meta"] is None
    assert body["data"]["prescription_id"] == str(prescription_id)
    assert body["data"]["pharmacist_id"] == str(pharmacist_id)


@pytest.mark.asyncio
async def test_post_dispensation_rejects_non_pharmacist(client: AsyncClient):
    app.dependency_overrides[get_current_active_user] = override_current_user("patient")

    response = await client.post(
        "/api/v1/dispensations",
        json={"prescription_id": str(uuid4()), "notes": None},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_get_dispensation_returns_success_envelope(client: AsyncClient):
    dispensation_id = uuid4()
    dispensation = Dispensation(
        id=dispensation_id,
        prescription_id=uuid4(),
        pharmacist_id=uuid4(),
        dispensed_at=datetime.now(timezone.utc),
        notes=None,
    )

    app.dependency_overrides[get_current_active_user] = override_current_user("admin")
    app.dependency_overrides[get_dispensation_service] = (
        lambda: DispensationServiceStub(dispensation)
    )

    response = await client.get(f"/api/v1/dispensations/{dispensation_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["id"] == str(dispensation_id)


@pytest.mark.asyncio
async def test_post_storage_upload_returns_success_envelope(client: AsyncClient):
    prescription_id = uuid4()
    uploader_id = uuid4()
    storage_file = StorageFileResponse(
        id=uuid4(),
        prescription_id=prescription_id,
        file_name="lab.pdf",
        file_url="https://example.com/storage/lab.pdf",
        file_size=12,
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_current_db_user] = lambda: User(
        id=uploader_id,
        keycloak_sub="kc-user-1",
        email="user@example.com",
    )
    app.dependency_overrides[get_prescription_service] = (
        lambda: PrescriptionServiceStub(prescription_id)
    )
    app.dependency_overrides[get_storage_service] = lambda: StorageServiceStub(
        storage_file,
        "https://signed.example.com/file",
    )

    response = await client.post(
        "/api/v1/storage/upload",
        data={"prescription_id": str(prescription_id)},
        files={"file": ("lab.pdf", BytesIO(b"fake-pdf"), "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["error"] is None
    assert body["data"]["prescription_id"] == str(prescription_id)
    assert body["data"]["file_name"] == "lab.pdf"


@pytest.mark.asyncio
async def test_get_storage_signed_url_returns_success_envelope(client: AsyncClient):
    file_id = uuid4()
    prescription_id = uuid4()
    storage_file = StorageFileResponse(
        id=file_id,
        prescription_id=prescription_id,
        file_name="lab.pdf",
        file_url="https://example.com/storage/lab.pdf",
        file_size=12,
        mime_type="application/pdf",
        created_at=datetime.now(timezone.utc),
    )

    app.dependency_overrides[get_current_active_user] = override_current_user("patient")
    app.dependency_overrides[get_storage_service] = lambda: StorageServiceStub(
        storage_file,
        "https://signed.example.com/file",
    )

    response = await client.get(f"/api/v1/storage/{file_id}/url")

    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert body["data"]["url"] == "https://signed.example.com/file"


@pytest.mark.asyncio
async def test_get_report_returns_pdf_stream(client: AsyncClient):
    prescription_id = uuid4()

    app.dependency_overrides[get_current_active_user] = override_current_user("doctor")
    app.dependency_overrides[get_prescription_service] = (
        lambda: PrescriptionServiceStub(prescription_id)
    )
    app.dependency_overrides[get_pdf_service] = lambda: PDFServiceStub()
    app.dependency_overrides[get_db] = override_db

    response = await client.get(f"/api/v1/reports/prescription/{prescription_id}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert (
        'attachment; filename="prescription-' in response.headers["content-disposition"]
    )
    assert response.content.startswith(b"%PDF")
