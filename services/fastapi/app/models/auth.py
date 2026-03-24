from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EmailField = Annotated[str, Field(min_length=3, max_length=255)]
NameField = Annotated[str, Field(min_length=1, max_length=255)]
NikField = Annotated[str | None, Field(default=None, max_length=50)]
PhoneField = Annotated[str | None, Field(default=None, max_length=50)]
AddressField = Annotated[str | None, Field(default=None, max_length=500)]


class TokenData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sub: str = Field(min_length=1, max_length=255)
    email: EmailField
    roles: list[str] = Field(default_factory=list)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    is_active: bool
    created_at: datetime


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    full_name: NameField
    nik: NikField = None
    phone: PhoneField = None
    address: AddressField = None
