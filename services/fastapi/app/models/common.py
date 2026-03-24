from __future__ import annotations

from math import ceil
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

PositivePage = int
PositivePerPage = int


class PaginationParams(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    page: PositivePage = Field(default=1, ge=1)
    per_page: PositivePerPage = Field(default=20, ge=1, le=100)
    sort_by: str = Field(default="created_at", min_length=1, max_length=100)
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


class PaginationMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total: int = Field(ge=0)
    page: int = Field(ge=1)
    per_page: int = Field(ge=1)
    total_pages: int = Field(ge=0)

    @classmethod
    def from_pagination(cls, total: int, page: int, per_page: int) -> "PaginationMeta":
        total_pages = ceil(total / per_page) if total > 0 else 0
        return cls(total=total, page=page, per_page=per_page, total_pages=total_pages)


class ErrorDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)


class ApiResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)

    data: T | None = None
    error: ErrorDetail | None = None
    meta: PaginationMeta | None = None
