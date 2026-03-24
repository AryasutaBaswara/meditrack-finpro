from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import Enum as SqlAlchemyEnum
from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.doctor import Doctor
    from app.db.models.drug import Drug
    from app.db.models.patient import Patient


class PrescriptionStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    DISPENSING = "dispensing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Prescription(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "prescriptions"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    doctor_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("doctors.id", ondelete="RESTRICT"),
        nullable=False,
    )
    patient_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[PrescriptionStatus] = mapped_column(
        SqlAlchemyEnum(PrescriptionStatus),
        default=PrescriptionStatus.DRAFT,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    interaction_check_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    doctor: Mapped[Doctor] = relationship("Doctor", lazy="selectin")
    patient: Mapped[Patient] = relationship("Patient", lazy="selectin")
    items: Mapped[list[PrescriptionItem]] = relationship(
        "PrescriptionItem",
        back_populates="prescription",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"Prescription(id={self.id!s}, doctor_id={self.doctor_id!s}, "
            f"patient_id={self.patient_id!s}, status={self.status.value!r})"
        )


class PrescriptionItem(Base, TimestampMixin):
    __tablename__ = "prescription_items"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    prescription_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("prescriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    drug_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("drugs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    duration: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(default=1, nullable=False)

    prescription: Mapped[Prescription] = relationship(
        "Prescription",
        back_populates="items",
        lazy="selectin",
    )
    drug: Mapped[Drug] = relationship("Drug", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"PrescriptionItem(id={self.id!s}, prescription_id={self.prescription_id!s}, "
            f"drug_id={self.drug_id!s}, dosage={self.dosage!r})"
        )
