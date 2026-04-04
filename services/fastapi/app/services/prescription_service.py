from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    DoctorNotFoundException,
    DrugNotFoundException,
    PatientNotFoundException,
    PrescriptionNotFoundException,
    UnauthorizedException,
)
from app.db.models.doctor import Doctor
from app.db.models.drug import Drug
from app.db.models.patient import Patient
from app.db.models.prescription import (
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.db.models.user import User
from app.models.auth import TokenData
from app.models.common import PaginationParams
from app.models.prescription import (
    InteractionCheckResponse,
    PrescriptionCreate,
    PrescriptionItemCreate,
    StockCheckItemResponse,
    StockCheckResult,
)
from app.services.ai_service import AIService
from app.services.cache_service import CacheService


class PrescriptionService:
    def __init__(self, db: AsyncSession, ai: AIService, cache: CacheService):
        self.db = db
        self.ai = ai
        self.cache = cache

    async def create(
        self, data: PrescriptionCreate, current_user: TokenData
    ) -> Prescription:
        user = await self._get_user_by_sub(current_user.sub)
        doctor = await self._get_doctor_for_user(user.id)
        patient = await self._get_patient(data.patient_id)
        drugs, stock_check_result = await self._get_drugs_for_items(data.items)
        drug_names = [drug.name for drug in drugs]
        interaction_result = await self.ai.check_drug_interactions(drug_names)

        prescription = Prescription(
            doctor_id=doctor.id,
            patient_id=patient.id,
            status=PrescriptionStatus.DRAFT,
            notes=data.notes,
            interaction_check_result=interaction_result.model_dump(mode="json"),
            stock_check_result=stock_check_result.model_dump(mode="json"),
        )
        self.db.add(prescription)
        await self.db.flush()

        items = [
            PrescriptionItem(
                prescription_id=prescription.id,
                drug_id=item.drug_id,
                dosage=item.dosage,
                frequency=item.frequency,
                duration=item.duration,
                quantity=item.quantity,
            )
            for item in data.items
        ]
        self.db.add_all(items)
        await self.db.flush()

        if (
            interaction_result.severity != "severe"
            and not stock_check_result.has_issues
        ):
            prescription.status = PrescriptionStatus.VALIDATED

        await self.db.flush()
        await self.db.refresh(prescription)
        await self._invalidate_cache()
        return await self._get_prescription_with_items(prescription.id)

    async def get_by_id(
        self, prescription_id: UUID, current_user: TokenData
    ) -> Prescription:
        prescription = await self._get_prescription_with_items(prescription_id)
        await self._authorize_prescription_access(prescription, current_user)
        return prescription

    async def list(
        self, pagination: PaginationParams, current_user: TokenData
    ) -> tuple[list[Prescription], int]:
        filters = await self._build_role_filters(current_user)

        count_query = (
            select(func.count())
            .select_from(Prescription)
            .where(Prescription.deleted_at.is_(None), *filters)
        )
        total = int((await self.db.execute(count_query)).scalar_one())

        sort_column = self._resolve_sort_column(pagination.sort_by)
        order_by = (
            sort_column.asc() if pagination.sort_order == "asc" else sort_column.desc()
        )
        query = (
            self._base_query()
            .where(*filters)
            .order_by(order_by)
            .offset(pagination.offset)
            .limit(pagination.per_page)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def cancel(
        self, prescription_id: UUID, current_user: TokenData
    ) -> Prescription:
        prescription = await self.get_by_id(prescription_id, current_user)
        if "admin" not in current_user.roles and "doctor" in current_user.roles:
            user = await self._get_user_by_sub(current_user.sub)
            doctor = await self._get_doctor_for_user(user.id)
            if prescription.doctor_id != doctor.id:
                raise UnauthorizedException(
                    "Cannot cancel another doctor's prescription"
                )

        prescription.status = PrescriptionStatus.CANCELLED
        await self.db.flush()
        await self.db.refresh(prescription)
        await self._invalidate_cache()
        return await self._get_prescription_with_items(prescription.id)

    async def check_interactions(
        self, drug_ids: list[UUID]
    ) -> InteractionCheckResponse:
        drugs = await self._get_drugs_by_ids(drug_ids)
        drug_names = [drug.name for drug in drugs]
        return await self.ai.check_drug_interactions(drug_names)

    def _base_query(self) -> Select[tuple[Prescription]]:
        return (
            select(Prescription)
            .options(
                selectinload(Prescription.items).selectinload(PrescriptionItem.drug)
            )
            .where(Prescription.deleted_at.is_(None))
        )

    async def _get_user_by_sub(self, keycloak_sub: str) -> User:
        result = await self.db.execute(
            select(User).where(
                User.keycloak_sub == keycloak_sub,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise UnauthorizedException("Authenticated user was not found")
        return user

    async def _get_doctor_for_user(self, user_id: UUID) -> Doctor:
        result = await self.db.execute(
            select(Doctor).where(
                Doctor.user_id == user_id,
                Doctor.deleted_at.is_(None),
            )
        )
        doctor = result.scalar_one_or_none()
        if doctor is None:
            raise DoctorNotFoundException(user_id)
        return doctor

    async def _get_patient_for_user(self, user_id: UUID) -> Patient:
        result = await self.db.execute(
            select(Patient).where(
                Patient.user_id == user_id,
                Patient.deleted_at.is_(None),
            )
        )
        patient = result.scalar_one_or_none()
        if patient is None:
            raise PatientNotFoundException(user_id)
        return patient

    async def _get_patient(self, patient_id: UUID) -> Patient:
        result = await self.db.execute(
            select(Patient).where(
                Patient.id == patient_id,
                Patient.deleted_at.is_(None),
            )
        )
        patient = result.scalar_one_or_none()
        if patient is None:
            raise PatientNotFoundException(patient_id)
        return patient

    async def _get_drugs_for_items(
        self, items: list[PrescriptionItemCreate]
    ) -> tuple[list[Drug], StockCheckResult]:
        requested_quantities = Counter()
        for item in items:
            requested_quantities[item.drug_id] += item.quantity

        drugs = await self._get_drugs_by_ids(list(requested_quantities.keys()))
        stock_issue_items: list[StockCheckItemResponse] = []
        issue_messages: list[str] = []

        for drug in drugs:
            requested_quantity = requested_quantities[drug.id]
            if drug.stock <= 0:
                stock_issue_items.append(
                    StockCheckItemResponse(
                        drug_id=drug.id,
                        drug_name=drug.name,
                        requested_quantity=requested_quantity,
                        available_stock=drug.stock,
                        status="out_of_stock",
                    )
                )
                issue_messages.append(f"{drug.name} is out of stock")
                continue

            if requested_quantity > drug.stock:
                stock_issue_items.append(
                    StockCheckItemResponse(
                        drug_id=drug.id,
                        drug_name=drug.name,
                        requested_quantity=requested_quantity,
                        available_stock=drug.stock,
                        status="insufficient_stock",
                    )
                )
                issue_messages.append(
                    f"{drug.name} only has {drug.stock} units available for {requested_quantity} requested"
                )

        if stock_issue_items:
            overall_status = (
                "out_of_stock"
                if any(item.status == "out_of_stock" for item in stock_issue_items)
                else "insufficient_stock"
            )
            return drugs, StockCheckResult(
                has_issues=True,
                status=overall_status,
                details="; ".join(issue_messages),
                items=stock_issue_items,
            )

        return drugs, StockCheckResult(
            has_issues=False,
            status="ok",
            details="All requested drugs are available in stock.",
            items=[],
        )

    async def _get_drugs_by_ids(self, drug_ids: list[UUID]) -> list[Drug]:
        if not drug_ids:
            return []

        result = await self.db.execute(
            select(Drug).where(
                Drug.id.in_(drug_ids),
                Drug.deleted_at.is_(None),
            )
        )
        drugs = list(result.scalars().all())
        if len(drugs) != len(set(drug_ids)):
            found_ids = {drug.id for drug in drugs}
            missing_id = next(
                drug_id for drug_id in drug_ids if drug_id not in found_ids
            )
            raise DrugNotFoundException(missing_id)
        return drugs

    async def _get_prescription_with_items(self, prescription_id: UUID) -> Prescription:
        result = await self.db.execute(
            self._base_query().where(Prescription.id == prescription_id)
        )
        prescription = result.scalar_one_or_none()
        if prescription is None:
            raise PrescriptionNotFoundException(prescription_id)
        return prescription

    async def _authorize_prescription_access(
        self, prescription: Prescription, current_user: TokenData
    ) -> None:
        if "admin" in current_user.roles or "pharmacist" in current_user.roles:
            return

        user = await self._get_user_by_sub(current_user.sub)

        if "doctor" in current_user.roles:
            doctor = await self._get_doctor_for_user(user.id)
            if prescription.doctor_id != doctor.id:
                raise UnauthorizedException(
                    "Cannot access another doctor's prescription"
                )
            return

        if "patient" in current_user.roles:
            patient = await self._get_patient_for_user(user.id)
            if prescription.patient_id != patient.id:
                raise UnauthorizedException(
                    "Cannot access another patient's prescription"
                )
            return

        raise UnauthorizedException("Insufficient permissions")

    async def _build_role_filters(self, current_user: TokenData) -> list[Any]:
        # 1. Apoteker / Admin langsung lolos (tanpa filter)
        if "admin" in current_user.roles or "pharmacist" in current_user.roles:
            return []

        # 2. Gunakan Scalar Subquery untuk Dokter (Tidak ada lagi await ke DB di sini!)
        if "doctor" in current_user.roles:
            doctor_subq = (
                select(Doctor.id)
                .join(User, User.id == Doctor.user_id)
                .where(User.keycloak_sub == current_user.sub)  # <--- GANTI DI SINI
                .scalar_subquery()
            )
            return [Prescription.doctor_id == doctor_subq]

        # 3. Gunakan Scalar Subquery untuk Pasien
        if "patient" in current_user.roles:
            patient_subq = (
                select(Patient.id)
                .join(User, User.id == Patient.user_id)
                .where(User.keycloak_sub == current_user.sub)  # <--- GANTI DI SINI
                .scalar_subquery()
            )
            return [Prescription.patient_id == patient_subq]

        raise UnauthorizedException("Insufficient permissions")

    def _resolve_sort_column(self, sort_by: str):
        allowed_columns = {
            "created_at": Prescription.created_at,
            "updated_at": Prescription.updated_at,
            "status": Prescription.status,
        }
        return allowed_columns.get(sort_by, Prescription.created_at)

    async def _invalidate_cache(self) -> None:
        await self.cache.delete_pattern("prescriptions:*")
