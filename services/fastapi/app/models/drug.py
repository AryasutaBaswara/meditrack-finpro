from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NameField = Annotated[str, Field(min_length=1, max_length=255)]
CategoryField = Annotated[str, Field(min_length=1, max_length=100)]
DescriptionField = Annotated[str | None, Field(default=..., max_length=1000)]
GenericNameField = Annotated[str | None, Field(default=..., max_length=255)]
ManufacturerField = Annotated[str | None, Field(default=..., max_length=255)]
UnitField = Annotated[str, Field(min_length=1, max_length=50)]
StockField = Annotated[int, Field(ge=0)]
PriceField = Annotated[Decimal, Field(ge=0)]


class DrugBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: NameField
    generic_name: GenericNameField
    category: CategoryField
    description: DescriptionField
    stock: StockField
    price: PriceField
    unit: UnitField
    manufacturer: ManufacturerField


class DrugCreate(DrugBase):
    model_config = ConfigDict(from_attributes=True)


class DrugUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: NameField | None = None
    generic_name: Annotated[str | None, Field(max_length=255)] = None
    category: CategoryField | None = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    stock: StockField | None = None
    price: PriceField | None = None
    unit: UnitField | None = None
    manufacturer: Annotated[str | None, Field(max_length=255)] = None


class DrugResponse(DrugBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class DrugSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    generic_name: str | None = None
    category: str
    price: Decimal
    stock: int
    score: float
