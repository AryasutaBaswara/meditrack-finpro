from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DoctorNotFoundException
from app.db.models.doctor import Doctor
from app.db.models.user import Profile, User
from app.models.common import PaginationParams
from app.models.doctor import DoctorCreate, DoctorUpdate, DoctorWithProfile


class DoctorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, doctor_id: UUID) -> Doctor:
        result = await self.db.execute(self._base_query().where(Doctor.id == doctor_id))
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise DoctorNotFoundException(doctor_id)
        return doctor

    async def list(
        self,
        pagination: PaginationParams,
        clinic_id: UUID | None,
    ) -> tuple[list[Doctor], int]:
        query = self._base_query()
        count_query = (
            select(func.count())
            .select_from(Doctor)
            .join(User, Doctor.user_id == User.id)
            .join(Profile, Profile.user_id == User.id)
            .where(Doctor.deleted_at.is_(None))
        )

        if clinic_id:
            query = query.where(Doctor.clinic_id == clinic_id)
            count_query = count_query.where(Doctor.clinic_id == clinic_id)

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

    async def create(self, data: DoctorCreate) -> Doctor:
        doctor = Doctor(**data.model_dump())
        self.db.add(doctor)
        await self.db.flush()
        await self.db.refresh(doctor)
        return doctor

    async def update(self, doctor_id: UUID, data: DoctorUpdate) -> Doctor:
        doctor = await self.get_by_id(doctor_id)
        for field_name, value in data.model_dump(exclude_unset=True).items():
            setattr(doctor, field_name, value)

        await self.db.flush()
        await self.db.refresh(doctor)
        return doctor

    async def get_with_profile(self, doctor_id: UUID) -> DoctorWithProfile:
        doctor = await self.get_by_id(doctor_id)
        return self.to_with_profile(doctor)

    def _base_query(self) -> Select[tuple[Doctor]]:
        return (
            select(Doctor)
            .join(User, Doctor.user_id == User.id)
            .join(Profile, Profile.user_id == User.id)
            .where(Doctor.deleted_at.is_(None))
        )

    def _resolve_sort_column(self, sort_by: str):
        allowed_columns = {
            "created_at": Doctor.created_at,
            "full_name": Profile.full_name,
            "sip_number": Doctor.sip_number,
            "specialization": Doctor.specialization,
        }
        return allowed_columns.get(sort_by, Doctor.created_at)

    def to_with_profile(self, doctor: Doctor) -> DoctorWithProfile:
        profile = doctor.user.profile
        return DoctorWithProfile.model_validate(
            {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "clinic_id": doctor.clinic_id,
                "sip_number": doctor.sip_number,
                "specialization": doctor.specialization,
                "created_at": doctor.created_at,
                "full_name": profile.full_name,
                "email": doctor.user.email,
            }
        )
