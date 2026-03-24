from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Drug(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "drugs"
    __table_args__ = (
        Index("ix_drugs_name", "name"),
        Index("ix_drugs_generic_name", "generic_name"),
        Index("ix_drugs_category", "category"),
    )

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    stock: Mapped[int] = mapped_column(default=0, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"Drug(id={self.id!s}, name={self.name!r}, category={self.category!r})"


class DrugInteraction(Base, TimestampMixin):
    __tablename__ = "drug_interactions"
    __table_args__ = (
        UniqueConstraint(
            "drug_a_id", "drug_b_id", name="uq_drug_interactions_drug_a_id_drug_b_id"
        ),
    )

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    drug_a_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    drug_b_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("drugs.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)

    drug_a: Mapped[Drug] = relationship(
        "Drug",
        foreign_keys=[drug_a_id],
        lazy="selectin",
    )
    drug_b: Mapped[Drug] = relationship(
        "Drug",
        foreign_keys=[drug_b_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"DrugInteraction(id={self.id!s}, drug_a_id={self.drug_a_id!s}, "
            f"drug_b_id={self.drug_b_id!s}, severity={self.severity!r})"
        )
