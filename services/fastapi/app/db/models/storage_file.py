from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.prescription import Prescription
    from app.db.models.user import User


class StorageFile(Base, TimestampMixin):
    __tablename__ = "storage_files"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    prescription_id: Mapped[UUID | None] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("prescriptions.id", ondelete="SET NULL"),
        nullable=True,
    )
    uploaded_by: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int | None] = mapped_column(nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)

    prescription: Mapped[Prescription | None] = relationship(
        "Prescription", lazy="selectin"
    )
    uploader: Mapped[User] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"StorageFile(id={self.id!s}, uploaded_by={self.uploaded_by!s}, "
            f"file_name={self.file_name!r})"
        )
