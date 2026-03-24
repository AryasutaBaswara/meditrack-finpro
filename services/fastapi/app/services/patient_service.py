from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PatientNotFoundException
from app.db.models.patient import Patient
from app.db.models.user import Profile, User
from app.models.common import PaginationParams
from app.models.patient import PatientCreate, PatientUpdate, PatientWithProfile
from app.models.prescription import PrescriptionResponse


class PatientService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, patient_id: UUID) -> Patient:
        result = await self.db.execute(
            self._base_query().where(Patient.id == patient_id)
        )
        patient = result.scalar_one_or_none()
        if patient is None:
            raise PatientNotFoundException(patient_id)
        return patient

    async def list(
        self,
        pagination: PaginationParams,
        search: str | None,
    ) -> tuple[list[Patient], int]:
        query = self._base_query()
        count_query = (
            select(func.count())
            .select_from(Patient)
            .join(User, Patient.user_id == User.id)
            .join(Profile, Profile.user_id == User.id)
            .where(Patient.deleted_at.is_(None))
        )

        if search:
            search_term = f"%{search}%"
            search_filter = or_(
                Profile.full_name.ilike(search_term),
                Profile.nik.ilike(search_term),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        sort_column = self._resolve_sort_column(pagination.sort_by)
        order_by = (
            sort_column.asc() if pagination.sort_order == "asc" else sort_column.desc()
        )

        total = int((await self.db.execute(count_query)).scalar_one())
        result = await self.db.execute(
            query.order_by(order_by)
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        return list(result.scalars().all()), total

    async def create(self, data: PatientCreate) -> Patient:
        patient = Patient(**data.model_dump())
        self.db.add(patient)
        await self.db.flush()
        await self.db.refresh(patient)
        return patient

    async def update(self, patient_id: UUID, data: PatientUpdate) -> Patient:
        patient = await self.get_by_id(patient_id)
        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(patient, field_name, value)

        await self.db.flush()
        await self.db.refresh(patient)
        return patient

    async def get_with_profile(self, patient_id: UUID) -> PatientWithProfile:
        patient = await self.get_by_id(patient_id)
        return self.to_with_profile(patient)

    async def get_prescription_history(
        self,
        patient_id: UUID,
    ) -> list[PrescriptionResponse]:
        await self.get_by_id(patient_id)
        result = await self.db.execute(
            text(
                """
                SELECT
                    id,
                    doctor_id,
                    patient_id,
                    status,
                    notes,
                    interaction_check_result,
                    created_at
                FROM get_patient_prescription_history(:patient_id)
                ORDER BY created_at DESC
                """
            ),
            {"patient_id": str(patient_id)},
        )
        rows = result.mappings().all()
        return [PrescriptionResponse.model_validate(dict(row)) for row in rows]

    def _base_query(self) -> Select[tuple[Patient]]:
        return (
            select(Patient)
            .join(User, Patient.user_id == User.id)
            .join(Profile, Profile.user_id == User.id)
            .where(Patient.deleted_at.is_(None))
        )

    def _resolve_sort_column(self, sort_by: str):
        allowed_columns = {
            "created_at": Patient.created_at,
            "full_name": Profile.full_name,
            "nik": Profile.nik,
        }
        return allowed_columns.get(sort_by, Patient.created_at)

    def to_with_profile(self, patient: Patient) -> PatientWithProfile:
        profile = patient.user.profile
        return PatientWithProfile.model_validate(
            {
                "id": patient.id,
                "user_id": patient.user_id,
                "blood_type": patient.blood_type,
                "allergies": patient.allergies,
                "emergency_contact": patient.emergency_contact,
                "created_at": patient.created_at,
                "full_name": profile.full_name,
                "email": patient.user.email,
                "phone": profile.phone,
            }
        )
