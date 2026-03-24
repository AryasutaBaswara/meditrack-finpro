from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.drug import Drug
    from app.db.models.prescription import Prescription
    from app.db.models.user import User


class Dispensation(Base, TimestampMixin):
    __tablename__ = "dispensations"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    prescription_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("prescriptions.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    pharmacist_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dispensed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    prescription: Mapped[Prescription] = relationship("Prescription", lazy="selectin")
    pharmacist: Mapped[User] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"Dispensation(id={self.id!s}, prescription_id={self.prescription_id!s}, "
            f"pharmacist_id={self.pharmacist_id!s})"
        )


class StockLog(Base, TimestampMixin):
    __tablename__ = "stock_logs"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    drug_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("drugs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    change_amount: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_id: Mapped[UUID | None] = mapped_column(SqlAlchemyUUID, nullable=True)
    stock_before: Mapped[int] = mapped_column(nullable=False)
    stock_after: Mapped[int] = mapped_column(nullable=False)

    drug: Mapped[Drug] = relationship("Drug", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"StockLog(id={self.id!s}, drug_id={self.drug_id!s}, "
            f"change_amount={self.change_amount!r}, reason={self.reason!r})"
        )
