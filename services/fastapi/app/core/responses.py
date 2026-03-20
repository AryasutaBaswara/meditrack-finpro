from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel


T = TypeVar("T")


class ErrorDetail(BaseModel):
	code: str
	message: str


class PaginationMeta(BaseModel):
	total: int
	page: int
	per_page: int


class ApiResponse(BaseModel, Generic[T]):
	data: T | None = None
	error: ErrorDetail | None = None
	meta: PaginationMeta | None = None


def success_response(data: Any = None, meta: PaginationMeta | None = None) -> dict[str, Any]:
	return ApiResponse[Any](data=data, meta=meta).model_dump()


def error_response(code: str, message: str) -> dict[str, Any]:
	return ApiResponse[Any](error=ErrorDetail(code=code, message=message)).model_dump()


def paginated_response(
	data: Any,
	total: int,
	page: int,
	per_page: int,
) -> dict[str, Any]:
	meta = PaginationMeta(total=total, page=page, per_page=per_page)
	return ApiResponse[Any](data=data, meta=meta).model_dump()
