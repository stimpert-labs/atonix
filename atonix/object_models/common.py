# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseAtonixModel(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(populate_by_name=True)

    def update_from(self, other: "BaseAtonixModel") -> None:
        """Update fields from another instance of the same model."""
        for field in other.model_fields_set:
            setattr(self, field, getattr(other, field))


class APIResponse(BaseAtonixModel, Generic[T]):
    """Standard Atonix API Response wrapper."""

    success: bool = Field(alias="Success")
    status_code: int = Field(alias="StatusCode")
    count: int | None = Field(default=None, alias="Count")
    type_name: str | None = Field(default=None, alias="Type")
    results: list[T] = Field(default_factory=list, alias="Results")
