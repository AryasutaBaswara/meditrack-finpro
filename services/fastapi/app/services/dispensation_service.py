from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    DispensationNotFoundException,
    DuplicateDispensationException,
    InsufficientStockException,
    InvalidPrescriptionStateException,
    PrescriptionNotFoundException,
    UnauthorizedException,
)
from app.db.models.dispensation import Dispensation, StockLog
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

        self._apply_stock_changes(prescription)
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

    def _apply_stock_changes(self, prescription: Prescription) -> None:
        for item in prescription.items:
            drug = item.drug
            if drug is None:
                continue
            if drug.stock < item.quantity:
                raise InsufficientStockException(drug.name)

            stock_before = drug.stock
            stock_after = stock_before - item.quantity
            drug.stock = stock_after
            self.db.add(
                StockLog(
                    drug_id=drug.id,
                    change_amount=-item.quantity,
                    reason="dispensation",
                    reference_id=prescription.id,
                    stock_before=stock_before,
                    stock_after=stock_after,
                )
            )

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
