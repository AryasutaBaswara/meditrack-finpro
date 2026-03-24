from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NotesField = Annotated[str | None, Field(default=None, max_length=1000)]


class DispensationCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prescription_id: UUID
    notes: NotesField = None


class DispensationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prescription_id: UUID
    pharmacist_id: UUID
    dispensed_at: datetime
    notes: str | None = None
