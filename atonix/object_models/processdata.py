# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from datetime import datetime

from pydantic import AliasChoices, AliasPath, Field

from atonix.object_models.common import BaseAtonixModel


class Server(BaseAtonixModel):
    """Process Data Server."""

    server_id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    asset_id: str = Field(alias="AssetId")


class Archive(BaseAtonixModel):
    """Process Data Archive."""

    name: str = Field(alias="Name")
    interval: int = Field(alias="Interval")


class Tag(BaseAtonixModel):
    """Tag Definition."""

    tag_id: str | None = Field(default=None, validation_alias=AliasChoices("Id", "TagId"), serialization_alias="Id")
    name: str | None = Field(default=None, validation_alias=AliasChoices("Name", "TagName"), serialization_alias="Name")
    description: str | None = Field(default=None, alias="Description")
    eng_unit: str | None = Field(default=None, alias="EngUnit")
    source: str | None = Field(default=None, alias="Source")
    qualifier: str | None = Field(default=None, alias="Qualifier")
    create_date: datetime | None = Field(default=None, alias="CreateDate")
    change_date: datetime | None = Field(default=None, alias="ChangeDate")


class TagData(BaseAtonixModel):
    """
    Internal model for parsing Atonix query responses.
    Wraps the series with status info.
    """

    tag_id: str = Field(alias="TagId")
    http_code: int | None = Field(default=None, alias="HttpCode")
    error: str | None = Field(default=None, alias="Error")
    timestamps: list[datetime] | None = Field(
        default=None, alias="Timestamps", validation_alias=AliasPath("Data", "Timestamps")
    )
    values: list[float] | None = Field(default=None, alias="Values", validation_alias=AliasPath("Data", "Values"))
    statuses: list[int] | None = Field(default=None, alias="Statuses", validation_alias=AliasPath("Data", "Statuses"))
