from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

import httpx
from jose import jwt
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

CURRENT_FILE = Path(__file__).resolve()
FASTAPI_ROOT = CURRENT_FILE.parents[1]
if str(FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(FASTAPI_ROOT))

from app.core.config import settings  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from app.db.models.clinic import Clinic  # noqa: E402
from app.db.models.doctor import Doctor  # noqa: E402
from app.db.models.drug import Drug  # noqa: E402
from app.db.models.patient import Patient  # noqa: E402
from app.db.models.prescription import (  # noqa: E402
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.db.models.role import Role, UserRole  # noqa: E402
from app.db.models.user import Profile, User  # noqa: E402

logger = logging.getLogger("staging_actor_seeder")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEFAULT_ROLE_DESCRIPTIONS = {
    "admin": "System administrator",
    "doctor": "Medical doctor",
    "pharmacist": "Dispensing pharmacist",
    "patient": "Registered patient",
}

DEFAULT_CLINIC = {
    "name": "MediTrack Clinic Staging",
    "address": "Jl. Kesehatan No. 10, Jakarta",
    "phone": "+62-21-555-0100",
    "email": "clinic@meditrack.staging",
}


@dataclass(slots=True)
class ActorSeedSpec:
    username: str
    password: str
    role: str
    full_name: str
    email: str | None = None
    date_of_birth: str | None = None
    phone: str | None = None
    address: str | None = None
    nik: str | None = None
    sip_number: str | None = None
    specialization: str | None = None
    blood_type: str | None = None
    allergies: str | None = None
    emergency_contact: str | None = None


@dataclass(slots=True)
class KeycloakIdentity:
    sub: str
    email: str
    username: str


def load_actor_specs(file_path: Path) -> list[ActorSeedSpec]:
    return load_actor_specs_from_json(file_path.read_text(encoding="utf-8"))


def load_actor_specs_from_json(raw_json: str) -> list[ActorSeedSpec]:
    raw_items = json.loads(raw_json)
    if not isinstance(raw_items, list):
        raise ValueError("Actor seed file must contain a JSON array")

    specs: list[ActorSeedSpec] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ValueError("Each actor seed item must be a JSON object")
        specs.append(ActorSeedSpec(**raw_item))
    return specs


def load_actor_specs_from_base64(payload: str) -> list[ActorSeedSpec]:
    decoded = base64.b64decode(payload).decode("utf-8")
    return load_actor_specs_from_json(decoded)


async def fetch_identity(spec: ActorSeedSpec) -> KeycloakIdentity:
    token_url = (
        f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"
        "/protocol/openid-connect/token"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        token_response = await client.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "username": spec.username,
                "password": spec.password,
            },
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise RuntimeError(
                f"Keycloak did not return access_token for {spec.username}"
            )

    payload = jwt.get_unverified_claims(access_token)

    sub = payload.get("sub")
    email = payload.get("email") or spec.email
    preferred_username = payload.get("preferred_username") or spec.username
    if not isinstance(sub, str) or not sub:
        raise RuntimeError(f"Keycloak userinfo did not contain sub for {spec.username}")
    if not isinstance(email, str) or not email:
        raise RuntimeError(
            f"Access token did not contain email for {spec.username}; add email to actor JSON"
        )

    return KeycloakIdentity(sub=sub, email=email, username=preferred_username)


async def get_or_create_role(session: AsyncSession, role_name: str) -> Role:
    result = await session.execute(select(Role).where(Role.name == role_name))
    role = result.scalar_one_or_none()
    if role is not None:
        role.description = DEFAULT_ROLE_DESCRIPTIONS.get(role_name, role.description)
        await session.flush()
        return role

    role = Role(
        name=role_name,
        description=DEFAULT_ROLE_DESCRIPTIONS.get(
            role_name, f"Seeded role for {role_name}"
        ),
    )
    session.add(role)
    await session.flush()
    return role


async def ensure_default_clinic(session: AsyncSession) -> Clinic:
    result = await session.execute(
        select(Clinic).where(Clinic.name == DEFAULT_CLINIC["name"])
    )
    clinic = result.scalar_one_or_none()
    if clinic is None:
        clinic = Clinic(**DEFAULT_CLINIC)
        session.add(clinic)
        await session.flush()
        logger.info("Created default staging clinic %s", clinic.name)
    else:
        clinic.address = DEFAULT_CLINIC["address"]
        clinic.phone = DEFAULT_CLINIC["phone"]
        clinic.email = DEFAULT_CLINIC["email"]
        await session.flush()
    return clinic


async def ensure_user_role(session: AsyncSession, user_id: UUID, role_id: UUID) -> None:
    result = await session.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role_id)
    )
    if result.scalar_one_or_none() is None:
        session.add(UserRole(user_id=user_id, role_id=role_id))
        await session.flush()


async def upsert_user(
    session: AsyncSession,
    spec: ActorSeedSpec,
    identity: KeycloakIdentity,
) -> User:
    result = await session.execute(
        select(User).where(
            or_(
                User.keycloak_sub == identity.sub,
                User.email == identity.email,
            )
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(keycloak_sub=identity.sub, email=identity.email, is_active=True)
        session.add(user)
        await session.flush()
        logger.info("Created user for %s", spec.username)
    else:
        if user.keycloak_sub != identity.sub:
            logger.info(
                "Updating keycloak_sub for %s from %s to %s",
                spec.username,
                user.keycloak_sub,
                identity.sub,
            )
        user.keycloak_sub = identity.sub
        user.email = identity.email
        user.is_active = True
        user.deleted_at = None
        await session.flush()

    result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = Profile(
            user_id=user.id,
            full_name=spec.full_name,
            nik=spec.nik,
            phone=spec.phone,
            address=spec.address,
            date_of_birth=(
                date.fromisoformat(spec.date_of_birth) if spec.date_of_birth else None
            ),
        )
        session.add(profile)
        await session.flush()
    else:
        profile.full_name = spec.full_name
        profile.nik = spec.nik
        profile.phone = spec.phone
        profile.address = spec.address
        profile.date_of_birth = (
            date.fromisoformat(spec.date_of_birth) if spec.date_of_birth else None
        )
        await session.flush()

    role = await get_or_create_role(session, spec.role)
    await ensure_user_role(session, user.id, role.id)
    return user


async def ensure_doctor(
    session: AsyncSession,
    user: User,
    spec: ActorSeedSpec,
    clinic: Clinic,
) -> Doctor:
    result = await session.execute(select(Doctor).where(Doctor.user_id == user.id))
    doctor = result.scalar_one_or_none()
    sip_number = spec.sip_number or f"SIP-{spec.username.upper()}"
    if doctor is None:
        doctor = Doctor(
            user_id=user.id,
            clinic_id=clinic.id,
            sip_number=sip_number,
            specialization=spec.specialization,
        )
        session.add(doctor)
        await session.flush()
        logger.info("Created doctor row for %s", spec.username)
    else:
        doctor.clinic_id = clinic.id
        doctor.sip_number = sip_number
        doctor.specialization = spec.specialization
        await session.flush()
    return doctor


async def ensure_patient(
    session: AsyncSession, user: User, spec: ActorSeedSpec
) -> Patient:
    result = await session.execute(select(Patient).where(Patient.user_id == user.id))
    patient = result.scalar_one_or_none()
    if patient is None:
        patient = Patient(
            user_id=user.id,
            blood_type=spec.blood_type,
            allergies=spec.allergies,
            emergency_contact=spec.emergency_contact,
        )
        session.add(patient)
        await session.flush()
        logger.info("Created patient row for %s", spec.username)
    else:
        patient.blood_type = spec.blood_type
        patient.allergies = spec.allergies
        patient.emergency_contact = spec.emergency_contact
        await session.flush()
    return patient


async def ensure_sample_prescription(
    session: AsyncSession,
    doctor: Doctor,
    patient: Patient,
) -> None:
    result = await session.execute(
        select(Prescription)
        .where(
            Prescription.doctor_id == doctor.id,
            Prescription.patient_id == patient.id,
            Prescription.deleted_at.is_(None),
        )
        .order_by(Prescription.created_at.desc())
        .limit(1)
    )
    existing = result.scalars().first()
    if existing is not None:
        logger.info(
            "Sample prescription already exists for doctor %s and patient %s",
            doctor.id,
            patient.id,
        )
        return

    drug_rows = await session.execute(
        select(Drug)
        .where(Drug.deleted_at.is_(None))
        .order_by(Drug.created_at.asc())
        .limit(2)
    )
    drugs = list(drug_rows.scalars().all())
    if len(drugs) < 2:
        raise RuntimeError(
            "Need at least 2 drugs in staging DB before creating sample prescription"
        )

    prescription = Prescription(
        doctor_id=doctor.id,
        patient_id=patient.id,
        status=PrescriptionStatus.VALIDATED,
        notes="Seeded staging prescription for automation smoke tests",
        interaction_check_result={
            "has_interactions": False,
            "severity": "none",
            "details": "Seeded sample has no known interactions.",
            "drugs_checked": [drug.name for drug in drugs],
        },
        stock_check_result={
            "has_issues": False,
            "status": "ok",
            "details": "Seeded sample stock check passed.",
            "items": [],
        },
    )
    session.add(prescription)
    await session.flush()

    for drug in drugs:
        session.add(
            PrescriptionItem(
                prescription_id=prescription.id,
                drug_id=drug.id,
                dosage="500mg",
                frequency="twice daily",
                duration="5 days",
                quantity=1,
            )
        )
    await session.flush()
    logger.info("Created sample prescription %s", prescription.id)


async def seed_actors(
    actor_file: Path | None,
    actor_json_base64: str | None,
    create_sample_prescription: bool,
) -> None:
    if actor_file is not None:
        specs = load_actor_specs(actor_file)
    elif actor_json_base64 is not None:
        specs = load_actor_specs_from_base64(actor_json_base64)
    else:
        raise ValueError("Either actor_file or actor_json_base64 must be provided")

    engine = create_database_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    doctor_row: Doctor | None = None
    patient_row: Patient | None = None

    try:
        async with session_factory() as session:
            clinic = await ensure_default_clinic(session)

            for spec in specs:
                identity = await fetch_identity(spec)
                user = await upsert_user(session, spec, identity)

                if spec.role == "doctor":
                    doctor_row = await ensure_doctor(session, user, spec, clinic)
                elif spec.role == "patient":
                    patient_row = await ensure_patient(session, user, spec)

            if create_sample_prescription and doctor_row and patient_row:
                await ensure_sample_prescription(session, doctor_row, patient_row)

            await session.commit()
            logger.info("Staging actor seed completed successfully")
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed staging DB rows that match existing Keycloak users"
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--actors-file",
        help="Path to JSON file describing staging actors and credentials",
    )
    source_group.add_argument(
        "--actors-json-base64",
        help="Base64-encoded JSON payload describing staging actors and credentials",
    )
    parser.add_argument(
        "--no-sample-prescription",
        action="store_true",
        help="Skip creating a sample prescription that links the seeded doctor and patient",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(
        seed_actors(
            actor_file=Path(args.actors_file) if args.actors_file else None,
            actor_json_base64=args.actors_json_base64,
            create_sample_prescription=not args.no_sample_prescription,
        )
    )


if __name__ == "__main__":
    main()
