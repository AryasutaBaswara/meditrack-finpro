from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

SipNumberField = Annotated[str, Field(min_length=1, max_length=100)]
SpecializationField = Annotated[str | None, Field(default=None, max_length=255)]
NameField = Annotated[str, Field(min_length=1, max_length=255)]
EmailField = Annotated[str, Field(min_length=3, max_length=255)]


class DoctorCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    clinic_id: UUID | None = None
    sip_number: SipNumberField
    specialization: SpecializationField = None


class DoctorUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID | None = None
    clinic_id: UUID | None = None
    sip_number: SipNumberField | None = None
    specialization: SpecializationField = None


class DoctorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    clinic_id: UUID | None = None
    sip_number: str
    specialization: str | None = None
    created_at: datetime


class DoctorWithProfile(DoctorResponse):
    model_config = ConfigDict(from_attributes=True)

    full_name: NameField
    email: EmailField
