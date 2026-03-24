from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

FileNameField = Annotated[str, Field(min_length=1, max_length=255)]
FileUrlField = Annotated[str, Field(min_length=1, max_length=1000)]
MimeTypeField = Annotated[str | None, Field(default=None, max_length=255)]


class StorageFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prescription_id: UUID | None = None
    file_name: FileNameField
    file_url: FileUrlField
    file_size: int | None = Field(default=None, ge=0)
    mime_type: MimeTypeField = None
    created_at: datetime


class StorageUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_url: FileUrlField
    signed_url: FileUrlField
    file_id: UUID
