from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.clinic import Clinic
    from app.db.models.user import User


class Doctor(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "doctors"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    clinic_id: Mapped[UUID | None] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("clinics.id", ondelete="SET NULL"),
        nullable=True,
    )
    sip_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    specialization: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship("User", lazy="selectin")
    clinic: Mapped[Clinic | None] = relationship("Clinic", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"Doctor(id={self.id!s}, user_id={self.user_id!s}, "
            f"sip_number={self.sip_number!r})"
        )
