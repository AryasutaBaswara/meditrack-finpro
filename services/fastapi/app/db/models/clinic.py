from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import String
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin


class Clinic(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clinics"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"Clinic(id={self.id!s}, name={self.name!r})"