from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    DispensationNotFoundException,
    DrugNotFoundException,
    DuplicateDispensationException,
    InsufficientStockException,
    InvalidPrescriptionStateException,
    PrescriptionNotFoundException,
    UnauthorizedException,
)
from app.db.models.dispensation import Dispensation
from app.db.models.drug import Drug
from app.db.models.prescription import (
    Prescription,
    PrescriptionItem,
    PrescriptionStatus,
)
from app.db.models.user import User
from app.models.auth import TokenData
from app.models.dispensation import DispensationCreate


class DispensationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def dispense(
        self, data: DispensationCreate, current_user: TokenData
    ) -> Dispensation:
        if "pharmacist" not in current_user.roles:
            raise UnauthorizedException("Only pharmacists can dispense prescriptions")

        prescription = await self._get_prescription(data.prescription_id)
        if prescription.status in (
            PrescriptionStatus.DRAFT,
            PrescriptionStatus.CANCELLED,
        ):
            raise InvalidPrescriptionStateException(
                prescription.id,
                prescription.status.value,
                PrescriptionStatus.VALIDATED.value,
            )
        if prescription.status == PrescriptionStatus.COMPLETED:
            raise DuplicateDispensationException(prescription.id)

        existing = await self.get_by_prescription(prescription.id)
        if existing is not None:
            raise DuplicateDispensationException(prescription.id)

        await self._apply_stock_changes_atomic(prescription)
        pharmacist = await self._get_user_by_sub(current_user.sub)

        prescription.status = PrescriptionStatus.DISPENSING
        dispensation = Dispensation(
            prescription_id=prescription.id,
            pharmacist_id=pharmacist.id,
            notes=data.notes,
        )
        self.db.add(dispensation)
        prescription.status = PrescriptionStatus.COMPLETED

        try:
            await self.db.flush()
        except IntegrityError as exc:
            if self._is_duplicate_dispensation_error(exc):
                raise DuplicateDispensationException(prescription.id) from exc
            raise

        await self.db.refresh(dispensation)
        return await self.get_by_id(dispensation.id)

    async def get_by_prescription(self, prescription_id: UUID) -> Dispensation | None:
        result = await self.db.execute(
            self._base_query().where(Dispensation.prescription_id == prescription_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, dispensation_id: UUID) -> Dispensation:
        result = await self.db.execute(
            self._base_query().where(Dispensation.id == dispensation_id)
        )
        dispensation = result.scalar_one_or_none()
        if dispensation is None:
            raise DispensationNotFoundException(dispensation_id)
        return dispensation

    def _base_query(self):
        return select(Dispensation).options(
            selectinload(Dispensation.prescription),
            selectinload(Dispensation.pharmacist),
        )

    async def _apply_stock_changes_atomic(self, prescription: Prescription) -> None:
        """Decrement stock for each prescription item using atomic UPDATE.

        Each UPDATE is a single round-trip that atomically checks availability
        and decrements in one operation — safe under high concurrency without
        requiring explicit row locks (SELECT FOR UPDATE).

        If the WHERE clause `stock >= quantity` is not satisfied, the UPDATE
        returns 0 rows, which we treat as InsufficientStockException.
        """
        for item in prescription.items:
            if item.drug_id is None:
                continue

            quantity = item.quantity
            # ATOMIC CONTEXT & UPDATE (Jaminan 100% data audit tidak tercecer)
            raw_query = text(
                """
                WITH context AS (
                    SELECT 
                        set_config('app.log_reason', 'dispensation', true),
                        set_config('app.log_reference_id', :ref_id, true)
                )
                UPDATE drugs 
                SET stock = stock - :quantity
                FROM context
                WHERE id = :drug_id 
                  AND stock >= :quantity
                  AND deleted_at IS NULL
                RETURNING drugs.id, drugs.name, drugs.stock;
            """
            )

            result = await self.db.execute(
                raw_query,
                {
                    "ref_id": str(prescription.id),
                    "quantity": quantity,
                    "drug_id": item.drug_id,
                },
            )
            row = result.fetchone()

            if row is None:
                # 0 rows updated → stock insufficient or drug missing
                drug_result = await self.db.execute(
                    select(Drug).where(Drug.id == item.drug_id)
                )
                drug = drug_result.scalar_one_or_none()
                if drug is None:
                    raise DrugNotFoundException(item.drug_id)
                raise InsufficientStockException(drug.name)

    def _is_duplicate_dispensation_error(self, exc: IntegrityError) -> bool:
        message = str(exc).lower()
        return (
            "dispensations" in message
            and "prescription_id" in message
            and ("unique" in message or "duplicate" in message)
        )

    async def _get_prescription(self, prescription_id: UUID) -> Prescription:
        result = await self.db.execute(
            select(Prescription)
            .options(
                selectinload(Prescription.items).selectinload(PrescriptionItem.drug)
            )
            .where(
                Prescription.id == prescription_id,
                Prescription.deleted_at.is_(None),
            )
        )
        prescription = result.scalar_one_or_none()
        if prescription is None:
            raise PrescriptionNotFoundException(prescription_id)
        return prescription

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
