from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.prescription import PrescriptionStatus
from app.models.drug import DrugResponse

DosageField = Annotated[str, Field(min_length=1, max_length=100)]
FrequencyField = Annotated[str, Field(min_length=1, max_length=100)]
DurationField = Annotated[str, Field(min_length=1, max_length=100)]
NotesField = Annotated[str | None, Field(default=None, max_length=1000)]
QuantityField = Annotated[int, Field(ge=1)]
DrugNamesField = Annotated[list[str], Field(min_length=1)]


class PrescriptionItemCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    drug_id: UUID
    dosage: DosageField
    frequency: FrequencyField
    duration: DurationField
    quantity: QuantityField


class PrescriptionItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    drug_id: UUID
    dosage: str
    frequency: str
    duration: str
    quantity: int
    drug: DrugResponse | None = None


class PrescriptionCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: UUID
    notes: NotesField = None
    items: Annotated[list[PrescriptionItemCreate], Field(min_length=1)]


class PrescriptionUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notes: NotesField = None
    status: PrescriptionStatus | None = None


class PrescriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    doctor_id: UUID
    patient_id: UUID
    status: PrescriptionStatus
    notes: str | None = None
    interaction_check_result: dict[str, Any] | None = None
    items: list[PrescriptionItemResponse] = Field(default_factory=list)
    created_at: datetime


class InteractionCheckRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    drug_ids: Annotated[list[UUID], Field(min_length=1)]


class InteractionCheckResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    has_interactions: bool
    severity: str | None = None
    details: str = Field(min_length=1, max_length=2000)
    drugs_checked: DrugNamesField
