from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

BloodTypeField = Annotated[str | None, Field(default=None, max_length=5)]
AllergiesField = Annotated[str | None, Field(default=None, max_length=1000)]
EmergencyContactField = Annotated[str | None, Field(default=None, max_length=255)]
PhoneField = Annotated[str | None, Field(default=None, max_length=50)]
NameField = Annotated[str, Field(min_length=1, max_length=255)]
EmailField = Annotated[str, Field(min_length=3, max_length=255)]


class PatientCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    blood_type: BloodTypeField = None
    allergies: AllergiesField = None
    emergency_contact: EmergencyContactField = None


class PatientUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    blood_type: BloodTypeField = None
    allergies: AllergiesField = None
    emergency_contact: EmergencyContactField = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    blood_type: str | None = None
    allergies: str | None = None
    emergency_contact: str | None = None
    created_at: datetime


class PatientWithProfile(PatientResponse):
    model_config = ConfigDict(from_attributes=True)

    full_name: NameField
    email: EmailField
    phone: PhoneField = None
