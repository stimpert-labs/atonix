# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, Field, model_validator

from atonix.object_models.common import BaseAtonixModel
from atonix.object_models.processdata import Tag

logger = logging.getLogger(__name__)


def _restructure_tag_fields(data: Any) -> Any:
    """Normalize flat TagId/TagName fields into a nested Tag dict expected by the Tag model."""
    if isinstance(data, dict) and "Tag" not in data and ("TagId" in data or "TagName" in data):
        data = data.copy()
        data["Tag"] = {"Id": data.get("TagId"), "Name": data.get("TagName")}
    return data


class AlertState(BaseAtonixModel):
    """
    Current alert state for a model.
    Represents the 'State' use case.
    """

    active: bool = Field(alias="Active")
    active_alerts: list[str] = Field(default_factory=list, alias="ActiveAlerts")
    evaluation_time: datetime = Field(alias="EvaluationTime")

    actual: float | None = Field(default=None, alias="Actual")
    expected: float | None = Field(default=None, alias="Expected")
    lower: float | None = Field(default=None, alias="Lower")
    upper: float | None = Field(default=None, alias="Upper")

    diagnose: bool = Field(default=False, alias="Diagnose")
    issue: bool = Field(default=False, alias="Issue")
    model_maintenance: bool = Field(default=False, alias="ModelMaintenance")
    watch: bool = Field(default=False, alias="Watch")

    # Flattened identification (populated in "ByAsset" endpoint)
    # Keeping these for now as they might be returned by list endpoints
    asset_id: str | None = Field(default=None, alias="AssetId")
    model_id: str | None = Field(default=None, alias="ModelId")


class Action(BaseAtonixModel):
    """
    Action taken on a model.
    Represents the 'Actions' use case.
    """

    action_note: str = Field(alias="ActionNote")
    action_type: str = Field(alias="ActionType")
    change_date: datetime = Field(alias="ChangeDate")
    changed_by: str = Field(alias="ChangedBy")

    actual: float | None = Field(default=None, alias="Actual")
    expected: float | None = Field(default=None, alias="Expected")
    lower: float | None = Field(default=None, alias="Lower")
    upper: float | None = Field(default=None, alias="Upper")
    is_favorite: bool = Field(default=False, alias="IsFavorite")

    # Flattened identification
    asset_id: str | None = Field(default=None, alias="AssetId")
    model_id: str | None = Field(default=None, alias="ModelId")


class ModelPredictiveMethod(BaseAtonixModel):
    is_active: bool = Field(validation_alias=AliasChoices("IsActive", "Active"), serialization_alias="IsActive")
    method_type: str = Field(validation_alias=AliasChoices("MethodType", "Method"), serialization_alias="MethodType")
    score: float | None = Field(default=None, alias="Score")


class TimingParameter(BaseAtonixModel):
    parameter_name: str = Field(
        validation_alias=AliasChoices("ParameterName", "ParameterType"), serialization_alias="ParameterName"
    )
    value: int | str | float | None = Field(default=None, alias="Value")
    temporal_type: str | None = Field(default=None, alias="TemporalType")


class TrainingData(BaseAtonixModel):
    minimum_data_points: int = Field(alias="MinimumDataPoints")
    auto_retrain: bool = Field(alias="AutoRetrain")
    timing_parameters: list[TimingParameter] = Field(alias="TimingParameters")


class ModelInput(BaseAtonixModel):
    tag: Tag = Field(alias="Tag")
    is_tag_selected: bool = Field(alias="IsTagSelected")
    is_tag_required: bool = Field(alias="IsTagRequired")

    @model_validator(mode="before")
    @classmethod
    def restructure_tag_v2(cls, data: Any) -> Any:
        return _restructure_tag_fields(data)


class AnomalyThresholds(BaseAtonixModel):
    upper: float | None = Field(default=None, alias="Upper")
    lower: float | None = Field(default=None, alias="Lower")


class AnomalyCriteria(BaseAtonixModel):
    criticality: dict[str, str] | None = Field(default=None, alias="Criticality")
    mean_absolute_error_multiplier: AnomalyThresholds | None = Field(default=None, alias="MeanAbsoluteErrorMultiplier")
    bias: AnomalyThresholds | None = Field(default=None, alias="Bias")
    fixed_limit: AnomalyThresholds | None = Field(default=None, alias="FixedLimit")


class ModelConfiguration(BaseAtonixModel):
    """
    Full model configuration.
    Represents the 'Config' use case.
    """

    active: bool = Field(alias="Active")
    model_name: str = Field(alias="ModelName")
    model_type: str = Field(alias="ModelType")
    tag: Tag | None = Field(default=None, alias="Tag")
    last_build_time: datetime | None = Field(default=None, alias="LastBuildTime")
    last_save_time: datetime | None = Field(default=None, alias="LastSaveTime")

    method_types: list[ModelPredictiveMethod] = Field(default_factory=list, alias="MethodTypes")
    training_data: TrainingData | None = Field(default=None, alias="TrainingData")
    inputs: list[ModelInput] = Field(default_factory=list, alias="Inputs")
    op_mode_types: list[str] = Field(default_factory=list, alias="OpModeTypes")
    anomaly_criteria: AnomalyCriteria | None = Field(default=None, alias="AnomalyCriteria")

    # Model-specific configs
    forecast: dict | None = Field(default=None, alias="Forecast")
    rate_of_change: dict | None = Field(default=None, alias="RateOfChange")
    moving_average_factors: dict | None = Field(default=None, alias="MovingAverageFactors")

    @model_validator(mode="before")
    @classmethod
    def normalize_null_lists(cls, data: Any) -> Any:
        """Convert null values to empty lists for list fields.

        The API sometimes returns null instead of empty arrays for list fields,
        which causes Pydantic validation errors. This validator ensures those
        fields are always lists.
        """
        if isinstance(data, dict):
            data = data.copy()
            # Convert null list fields to empty lists
            list_fields = ["MethodTypes", "Inputs", "OpModeTypes"]
            for field in list_fields:
                if field in data and data[field] is None:
                    data[field] = []
        return data

    @model_validator(mode="before")
    @classmethod
    def restructure_tag(cls, data: Any) -> Any:
        return _restructure_tag_fields(data)


class ExternalModelConfiguration(BaseAtonixModel):
    """Configuration for an external model."""

    active: bool = Field(alias="Active")
    model_name: str = Field(alias="ModelName")
    model_type: str = Field(alias="ModelType")
    asset_id: str = Field(alias="AssetId")
    diagnostic_drilldown_url: str | None = Field(default=None, alias="DiagnosticDrilldownURL")
    model_configuration_url: str | None = Field(default=None, alias="ModelConfigurationURL")
    anomaly_criteria: AnomalyCriteria | None = Field(default=None, alias="AnomalyCriteria")


class Model(BaseAtonixModel):
    """
    Top-level Model object.

    Serves as the central point for:
    1. Identification (ModelId, AssetId, Name)
    2. Configuration (Config)
    3. State (AlertState)
    4. History (Actions)
    """

    model_id: str = Field(validation_alias=AliasChoices("Id", "ModelId"), serialization_alias="Id")
    name: str | None = Field(default=None, alias="Name")
    asset_id: str | None = Field(default=None, alias="AssetId")

    # Core attributes which might be present in basic list views
    model_type_name: str | None = Field(default=None, alias="ModelTypeName")
    status: str | None = Field(default=None, alias="Status")

    # Nested Objects for detailed use cases
    alert_state: AlertState | None = Field(default=None, alias="AlertState")
    config: ModelConfiguration | ExternalModelConfiguration | None = Field(default=None, alias="Config")
    actions: list[Action] | None = Field(default=None, alias="Actions")
