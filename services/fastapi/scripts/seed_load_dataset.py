from __future__ import annotations

import argparse
import asyncio
import logging
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from uuid import UUID

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

CURRENT_FILE = Path(__file__).resolve()
FASTAPI_ROOT = CURRENT_FILE.parents[1]
if str(FASTAPI_ROOT) not in sys.path:
    sys.path.insert(0, str(FASTAPI_ROOT))

from app.db.models.doctor import Doctor  # noqa: E402
from app.db.models.drug import Drug  # noqa: E402
from app.db.models.patient import Patient  # noqa: E402
from app.db.models.prescription import (  # noqa: E402
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.db.models.role import UserRole  # noqa: E402
from app.db.models.user import Profile, User  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from seed_staging_actors import (  # noqa: E402
    ActorSeedSpec,
    ensure_default_clinic,
    ensure_doctor,
    ensure_patient,
    fetch_identity,
    get_or_create_role,
    load_actor_specs,
    load_actor_specs_from_base64,
    upsert_user,
)

logger = logging.getLogger("load_dataset_seeder")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

LOAD_PREFIX = "load-dataset"
PRESCRIPTION_NOTE_PREFIX = "LOAD-DATASET"


@dataclass(slots=True)
class LoadSeedConfig:
    total_doctors: int
    total_patients: int
    total_pharmacists: int
    total_prescriptions: int
    seed: int
    actor_file: Path | None
    actor_json_base64: str | None


def _load_specs(config: LoadSeedConfig) -> list[ActorSeedSpec]:
    if config.actor_file is not None:
        return load_actor_specs(config.actor_file)
    if config.actor_json_base64 is not None:
        return load_actor_specs_from_base64(config.actor_json_base64)
    raise ValueError("Either actor_file or actor_json_base64 must be provided")


def _background_email(role: str, index: int) -> str:
    return f"{LOAD_PREFIX}-{role}-{index:03d}@meditrack.staging"


def _background_sub(role: str, index: int) -> str:
    return f"{LOAD_PREFIX}-{role}-{index:03d}"


def _background_full_name(role: str, index: int) -> str:
    return f"Load {role.capitalize()} {index:03d}"


async def ensure_background_user(
    session,
    *,
    role_name: str,
    index: int,
) -> User:
    email = _background_email(role_name, index)
    sub = _background_sub(role_name, index)
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(keycloak_sub=sub, email=email, is_active=True)
        session.add(user)
        await session.flush()
        logger.info("Created background %s user %s", role_name, email)
    else:
        user.keycloak_sub = sub
        user.is_active = True
        user.deleted_at = None
        await session.flush()

    result = await session.execute(select(Profile).where(Profile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if profile is None:
        profile = Profile(
            user_id=user.id,
            full_name=_background_full_name(role_name, index),
            nik=(
                f"{role_name[:3].upper()}{index:013d}"
                if role_name == "patient"
                else None
            ),
            phone=f"+62-811-{index:04d}-{index:04d}",
            address=f"Synthetic load dataset address for {role_name} {index:03d}",
        )
        session.add(profile)
    else:
        profile.full_name = _background_full_name(role_name, index)
        profile.phone = f"+62-811-{index:04d}-{index:04d}"
        profile.address = f"Synthetic load dataset address for {role_name} {index:03d}"
        if role_name == "patient" and not profile.nik:
            profile.nik = f"{role_name[:3].upper()}{index:013d}"
    await session.flush()

    role = await get_or_create_role(session, role_name)
    role_link_result = await session.execute(
        select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
    )
    if role_link_result.scalar_one_or_none() is None:
        session.add(UserRole(user_id=user.id, role_id=role.id))
        await session.flush()

    return user


async def ensure_background_doctors(session, total_background_doctors: int) -> None:
    clinic = await ensure_default_clinic(session)
    for index in range(1, total_background_doctors + 1):
        user = await ensure_background_user(session, role_name="doctor", index=index)
        spec = ActorSeedSpec(
            username=_background_sub("doctor", index),
            password="not-used",
            role="doctor",
            full_name=_background_full_name("doctor", index),
            email=user.email,
            phone=f"+62-812-10{index:02d}-{index:04d}",
            sip_number=f"SIP-LOAD-{index:03d}",
            specialization=(
                "Internal Medicine" if index % 2 == 0 else "General Medicine"
            ),
        )
        await ensure_doctor(session, user, spec, clinic)


async def ensure_background_patients(session, total_background_patients: int) -> None:
    blood_types = ["A+", "B+", "AB+", "O+", "A-", "B-", "AB-", "O-"]
    for index in range(1, total_background_patients + 1):
        user = await ensure_background_user(session, role_name="patient", index=index)
        spec = ActorSeedSpec(
            username=_background_sub("patient", index),
            password="not-used",
            role="patient",
            full_name=_background_full_name("patient", index),
            email=user.email,
            phone=f"+62-813-20{index:02d}-{index:04d}",
            blood_type=blood_types[(index - 1) % len(blood_types)],
            allergies=("Penicillin" if index % 7 == 0 else "None"),
            emergency_contact=f"Load Patient Contact {index:03d}",
        )
        await ensure_patient(session, user, spec)


async def ensure_background_pharmacists(
    session, total_background_pharmacists: int
) -> None:
    for index in range(1, total_background_pharmacists + 1):
        await ensure_background_user(session, role_name="pharmacist", index=index)


async def seed_login_actors(
    session, specs: Iterable[ActorSeedSpec]
) -> dict[str, list[UUID]]:
    clinic = await ensure_default_clinic(session)
    actor_ids: dict[str, list[UUID]] = {"doctor": [], "patient": [], "pharmacist": []}

    for spec in specs:
        identity = await fetch_identity(spec)
        user = await upsert_user(session, spec, identity)

        if spec.role == "doctor":
            doctor = await ensure_doctor(session, user, spec, clinic)
            actor_ids["doctor"].append(doctor.id)
        elif spec.role == "patient":
            patient = await ensure_patient(session, user, spec)
            actor_ids["patient"].append(patient.id)
        elif spec.role == "pharmacist":
            actor_ids["pharmacist"].append(user.id)

    return actor_ids


async def get_dataset_doctors(session) -> list[Doctor]:
    result = await session.execute(
        select(Doctor)
        .join(User, User.id == Doctor.user_id)
        .where(
            Doctor.deleted_at.is_(None),
            User.deleted_at.is_(None),
            (
                User.email.like(f"{LOAD_PREFIX}-doctor-%")
                | (User.email == "doctor@meditrack.staging")
            ),
        )
        .order_by(User.email.asc())
    )
    return list(result.scalars().all())


async def get_dataset_patients(session) -> list[Patient]:
    result = await session.execute(
        select(Patient)
        .join(User, User.id == Patient.user_id)
        .where(
            Patient.deleted_at.is_(None),
            User.deleted_at.is_(None),
            (
                User.email.like(f"{LOAD_PREFIX}-patient-%")
                | (User.email == "patient@meditrack.staging")
            ),
        )
        .order_by(User.email.asc())
    )
    return list(result.scalars().all())


async def get_seeded_prescription_count(session) -> int:
    count_query = (
        select(func.count())
        .select_from(Prescription)
        .where(
            Prescription.deleted_at.is_(None),
            Prescription.notes.like(f"{PRESCRIPTION_NOTE_PREFIX}:%"),
        )
    )
    return int((await session.execute(count_query)).scalar_one())


def choose_status(rng: random.Random) -> PrescriptionStatus:
    roll = rng.random()
    if roll < 0.35:
        return PrescriptionStatus.VALIDATED
    if roll < 0.65:
        return PrescriptionStatus.DRAFT
    if roll < 0.85:
        return PrescriptionStatus.COMPLETED
    if roll < 0.95:
        return PrescriptionStatus.DISPENSING
    return PrescriptionStatus.CANCELLED


def build_interaction_result(drug_names: list[str]) -> dict[str, object]:
    return {
        "has_interactions": False,
        "severity": "none",
        "details": "Synthetic load dataset uses a benign interaction profile.",
        "drugs_checked": drug_names,
    }


def build_stock_result() -> dict[str, object]:
    return {
        "has_issues": False,
        "status": "ok",
        "details": "Synthetic load dataset stock check passed.",
        "items": [],
    }


async def create_seeded_prescriptions(
    session,
    *,
    config: LoadSeedConfig,
    doctor_ids: list[UUID],
    patient_ids: list[UUID],
    actor_doctor_ids: list[UUID],
    actor_patient_ids: list[UUID],
) -> None:
    if not doctor_ids or not patient_ids:
        raise RuntimeError(
            "Need at least one doctor and one patient to seed prescriptions"
        )

    drug_result = await session.execute(
        select(Drug)
        .where(Drug.deleted_at.is_(None), Drug.stock > 0)
        .order_by(Drug.name.asc())
        .limit(25)
    )
    drugs = list(drug_result.scalars().all())
    if len(drugs) < 3:
        raise RuntimeError(
            "Need at least 3 active drugs with positive stock before seeding load dataset"
        )

    existing_count = await get_seeded_prescription_count(session)
    if existing_count >= config.total_prescriptions:
        logger.info(
            "Load dataset already has %s seeded prescriptions, target %s reached",
            existing_count,
            config.total_prescriptions,
        )
        return

    rng = random.Random(config.seed + existing_count)
    doctor_owned_target = min(40, config.total_prescriptions)
    patient_owned_target = min(20, config.total_prescriptions)

    for index in range(existing_count, config.total_prescriptions):
        if actor_doctor_ids and index < doctor_owned_target:
            doctor_id = actor_doctor_ids[index % len(actor_doctor_ids)]
            patient_id = patient_ids[index % len(patient_ids)]
        elif actor_patient_ids and index < doctor_owned_target + patient_owned_target:
            doctor_id = doctor_ids[index % len(doctor_ids)]
            patient_id = actor_patient_ids[index % len(actor_patient_ids)]
        else:
            doctor_id = doctor_ids[rng.randrange(len(doctor_ids))]
            patient_id = patient_ids[rng.randrange(len(patient_ids))]

        item_count = min(len(drugs), rng.randint(1, 4))
        chosen_drugs = rng.sample(drugs, k=item_count)
        status = choose_status(rng)
        prescription = Prescription(
            doctor_id=doctor_id,
            patient_id=patient_id,
            status=status,
            notes=f"{PRESCRIPTION_NOTE_PREFIX}:seed={config.seed}:row={index:05d}",
            interaction_check_result=build_interaction_result(
                [drug.name for drug in chosen_drugs]
            ),
            stock_check_result=build_stock_result(),
        )
        session.add(prescription)
        await session.flush()

        for drug in chosen_drugs:
            session.add(
                PrescriptionItem(
                    prescription_id=prescription.id,
                    drug_id=drug.id,
                    dosage=("500mg" if rng.random() < 0.5 else "250mg"),
                    frequency=rng.choice(
                        ["once daily", "twice daily", "three times daily"]
                    ),
                    duration=rng.choice(["3 days", "5 days", "7 days", "10 days"]),
                    quantity=rng.randint(1, 3),
                )
            )

        if (index + 1) % 50 == 0:
            logger.info(
                "Seeded %s/%s prescriptions", index + 1, config.total_prescriptions
            )

    await session.flush()


async def seed_load_dataset(config: LoadSeedConfig) -> None:
    specs = _load_specs(config)
    engine = create_database_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            actor_ids = await seed_login_actors(session, specs)

            total_background_doctors = max(
                0, config.total_doctors - len(actor_ids["doctor"])
            )
            total_background_patients = max(
                0, config.total_patients - len(actor_ids["patient"])
            )
            total_background_pharmacists = max(
                0, config.total_pharmacists - len(actor_ids["pharmacist"])
            )

            await ensure_background_doctors(session, total_background_doctors)
            await ensure_background_patients(session, total_background_patients)
            await ensure_background_pharmacists(session, total_background_pharmacists)

            doctors = await get_dataset_doctors(session)
            patients = await get_dataset_patients(session)

            await create_seeded_prescriptions(
                session,
                config=config,
                doctor_ids=[doctor.id for doctor in doctors],
                patient_ids=[patient.id for patient in patients],
                actor_doctor_ids=actor_ids["doctor"],
                actor_patient_ids=actor_ids["patient"],
            )

            await session.commit()
            logger.info(
                "Load dataset seed completed successfully with %s doctors, %s patients, %s pharmacists, target %s prescriptions",
                config.total_doctors,
                config.total_patients,
                config.total_pharmacists,
                config.total_prescriptions,
            )
    finally:
        await engine.dispose()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed a deterministic staging dataset for load testing"
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--actors-file")
    source_group.add_argument("--actors-json-base64")
    parser.add_argument("--total-doctors", type=int, default=5)
    parser.add_argument("--total-patients", type=int, default=50)
    parser.add_argument("--total-pharmacists", type=int, default=3)
    parser.add_argument("--total-prescriptions", type=int, default=400)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = LoadSeedConfig(
        total_doctors=args.total_doctors,
        total_patients=args.total_patients,
        total_pharmacists=args.total_pharmacists,
        total_prescriptions=args.total_prescriptions,
        seed=args.seed,
        actor_file=Path(args.actors_file) if args.actors_file else None,
        actor_json_base64=args.actors_json_base64,
    )
    asyncio.run(seed_load_dataset(config))


if __name__ == "__main__":
    main()
