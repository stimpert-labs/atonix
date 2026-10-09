# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from datetime import datetime

from pydantic import Field

from atonix.object_models.common import BaseAtonixModel


class Asset(BaseAtonixModel):
    """Atonix Asset definition."""

    id: str = Field(alias="Id")
    abbrev: str = Field(alias="Abbrev")
    desc: str = Field(alias="Desc")
    parent_id: str | None = Field(default=None, alias="ParentId")
    asset_type_name: str = Field(alias="AssetTypeName")
    create_date: datetime | None = Field(default=None, alias="CreateDate")
    change_date: datetime | None = Field(default=None, alias="ChangeDate")
