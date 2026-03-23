from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class Patient(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "patients"

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
    blood_type: Mapped[str | None] = mapped_column(String(5), nullable=True)
    allergies: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"Patient(id={self.id!s}, user_id={self.user_id!s}, blood_type={self.blood_type!r})"