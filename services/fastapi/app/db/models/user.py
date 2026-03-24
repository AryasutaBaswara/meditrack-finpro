from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy import Uuid as SqlAlchemyUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.role import UserRole


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        SqlAlchemyUUID,
        primary_key=True,
        default=uuid4,
    )
    keycloak_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    profile: Mapped[Profile | None] = relationship(
        "Profile",
        back_populates="user",
        lazy="selectin",
        uselist=False,
    )
    user_roles: Mapped[list[UserRole]] = relationship(
        "UserRole",
        back_populates="user",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"User(id={self.id!s}, email={self.email!r}, "
            f"keycloak_sub={self.keycloak_sub!r}, is_active={self.is_active!r})"
        )


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

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
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    nik: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="profile",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"Profile(id={self.id!s}, user_id={self.user_id!s}, "
            f"full_name={self.full_name!r})"
        )
