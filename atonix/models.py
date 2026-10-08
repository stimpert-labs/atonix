# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any

from atonix.base import AsyncBaseResource, BaseResource, _to_utc_ms_str
from atonix.object_models.common import APIResponse
from atonix.object_models.models import (
    Action,
    AlertState,
    ExternalModelConfiguration,
    Model,
    ModelConfiguration,
)

logger = logging.getLogger(__name__)


class Models(BaseResource):
    """Interface for the Atonix Models (Monitoring) API."""

    def get_models(
        self, asset_id: str, include_descendants: bool = False, skip: int = 0, take: int = 500
    ) -> Iterator[Model]:
        """
        List models for a specific asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            include_descendants: Whether to include models from child assets.
            skip: Number of models to skip for initial offset.
            take: Number of models to retrieve per API page (max 500).

        Yields:
            Model objects one by one.
        """
        params = {
            "assetId": asset_id,
            "includeDescendants": str(include_descendants).lower(),
        }
        return self._get_paginated("/v1/models", Model, params=params, skip=skip, take=take)

    def get_model_state(self, model_id: str) -> AlertState:
        """
        Get the current alert and value state for a model.

        Args:
            model_id: The unique identifier (GUID) of the model.

        Returns:
            An AlertState object.
        """
        return self._get_single(f"/v1/models/{model_id}/state", AlertState)

    def get_model_actions(
        self,
        model_id: str,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        skip: int = 0,
        take: int = 500,
    ) -> Iterator[Action]:
        """
        Get action items/events for a specific model.

        Args:
            model_id: The unique identifier (GUID) of the model.
            changed_after: Filter actions modified after this date.
            changed_before: Filter actions modified before this date.
            skip: Number of actions to skip.
            take: Number of actions to retrieve per page.

        Yields:
            Action objects one by one.
        """
        params: dict[str, Any] = {}
        if changed_after:
            params["changedAfter"] = _to_utc_ms_str(changed_after)
        if changed_before:
            params["changedBefore"] = _to_utc_ms_str(changed_before)

        return self._get_paginated(f"/v1/models/{model_id}/actions", Action, params=params, skip=skip, take=take)

    def get_model_config(self, model_id: str) -> ModelConfiguration | ExternalModelConfiguration:
        """
        Get the configuration for a model.

        Automatically detects if the model is a standard Atonix model or an
        External (API-based) model and returns the appropriate configuration object.

        Args:
            model_id: The unique identifier (GUID) of the model.

        Returns:
            ModelConfiguration or ExternalModelConfiguration.
        """
        response_data = self._client.get(f"/v1/models/{model_id}/config")
        # Check type to decide which model to use
        raw_type = response_data.get("Type", "ModelConfiguration")
        if raw_type == "ExternalModelConfiguration":
            external_response = APIResponse[ExternalModelConfiguration](**response_data)
            return external_response.results[0]
        else:
            standard_response = APIResponse[ModelConfiguration](**response_data)
            return standard_response.results[0]

    def get_model_states_by_asset(
        self,
        asset_id: str,
        include_descendants: bool = False,
        include_inactive: bool = False,
        skip: int = 0,
        take: int = 500,
    ) -> Iterator[AlertState]:
        """
        List states for all models under an asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            include_descendants: Whether to include models from child assets.
            include_inactive: Whether to include models that are not currently running/active.
            skip: Offset for pagination.
            take: Results per page.

        Yields:
            AlertState objects one by one.
        """
        params = {
            "assetId": asset_id,
            "includeDescendants": str(include_descendants).lower(),
            "includeInactive": str(include_inactive).lower(),
        }
        return self._get_paginated("/v1/models/state", AlertState, params=params, skip=skip, take=take)

    def get_model_actions_by_asset(
        self,
        asset_id: str,
        changed_after: datetime,
        changed_before: datetime,
        favorite: bool = False,
        include_descendants: bool = False,
        skip: int = 0,
        take: int = 500,
    ) -> Iterator[Action]:
        """
        Get all action items for an asset's models within a date range.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            changed_after: Start date for the window.
            changed_before: End date for the window.
            favorite: Filter for only 'favorite' or starred actions.
            include_descendants: Whether to include models from child assets.
            skip: Offset for pagination.
            take: Results per page.

        Yields:
            Action objects one by one.
        """
        params = {
            "assetId": asset_id,
            "changedAfter": _to_utc_ms_str(changed_after),
            "changedBefore": _to_utc_ms_str(changed_before),
        }

        if favorite:
            params["favorite"] = "true"
        if include_descendants:
            params["includeDescendants"] = "true"
        return self._get_paginated("/v1/models/actions", Action, params=params, skip=skip, take=take)

    def get_model(
        self,
        model: str | Model,
        include_config: bool = False,
        include_state: bool = False,
        include_actions: bool = False,
        actions_changed_after: datetime | None = None,
        actions_changed_before: datetime | None = None,
    ) -> Model:
        """
        Get a Model object, optionally including configuration, state, and actions.

        Args:
            model: Either a Model ID (str) or a Model object (which must have an ID).
            include_config: Whether to fetch and include the model configuration.
            include_state: Whether to fetch and include the current alert state.
            include_actions: Whether to fetch and include recent actions.
            actions_changed_after: Filter actions modified after this date (only used if include_actions=True).
            actions_changed_before: Filter actions modified before this date (only used if include_actions=True).

        Returns:
            A Model object with the requested information populated.
        """
        if isinstance(model, Model):
            model_id = model.model_id
            result_model = model.model_copy()
        else:
            model_id = model
            result_model = Model(model_id=model_id)

        if include_config:
            try:
                result_model.config = self.get_model_config(model_id)
            except Exception as e:
                logger.warning("Failed to fetch config for model %s: %s", model_id, e)

        if include_state:
            try:
                result_model.alert_state = self.get_model_state(model_id)
            except Exception as e:
                logger.warning("Failed to fetch state for model %s: %s", model_id, e)

        if include_actions:
            try:
                result_model.actions = list(
                    self.get_model_actions(
                        model_id,
                        changed_after=actions_changed_after,
                        changed_before=actions_changed_before,
                    )
                )
            except Exception as e:
                logger.warning("Failed to fetch actions for model %s: %s", model_id, e)

        return result_model


class AsyncModels(AsyncBaseResource):
    """Async interface for the Atonix Models (Monitoring) API."""

    def get_models(
        self, asset_id: str, include_descendants: bool = False, skip: int = 0, take: int = 500
    ) -> AsyncIterator[Model]:
        """
        List models for a specific asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            include_descendants: Whether to include models from child assets.
            skip: Number of models to skip for initial offset.
            take: Number of models to retrieve per API page (max 500).

        Returns:
            An async iterator of Model objects.
        """
        params = {
            "assetId": asset_id,
            "includeDescendants": str(include_descendants).lower(),
        }
        return self._get_paginated("/v1/models", Model, params=params, skip=skip, take=take)

    async def get_model_state(self, model_id: str) -> AlertState:
        """
        Get the current alert and value state for a model.

        Args:
            model_id: The unique identifier (GUID) of the model.

        Returns:
            An AlertState object.
        """
        return await self._get_single(f"/v1/models/{model_id}/state", AlertState)

    def get_model_actions(
        self,
        model_id: str,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        skip: int = 0,
        take: int = 500,
    ) -> AsyncIterator[Action]:
        """
        Get action items/events for a specific model.

        Args:
            model_id: The unique identifier (GUID) of the model.
            changed_after: Filter actions modified after this date.
            changed_before: Filter actions modified before this date.
            skip: Number of actions to skip.
            take: Number of actions to retrieve per page.

        Returns:
            An async iterator of Action objects.
        """
        params: dict[str, Any] = {}
        if changed_after:
            params["changedAfter"] = _to_utc_ms_str(changed_after)
        if changed_before:
            params["changedBefore"] = _to_utc_ms_str(changed_before)

        return self._get_paginated(f"/v1/models/{model_id}/actions", Action, params=params, skip=skip, take=take)

    async def get_model_config(self, model_id: str) -> ModelConfiguration | ExternalModelConfiguration:
        """
        Get the configuration for a model.

        Automatically detects if the model is a standard Atonix model or an
        External (API-based) model and returns the appropriate configuration object.

        Args:
            model_id: The unique identifier (GUID) of the model.

        Returns:
            ModelConfiguration or ExternalModelConfiguration.
        """
        response_data = await self._client.get(f"/v1/models/{model_id}/config")
        raw_type = response_data.get("Type", "ModelConfiguration")
        if raw_type == "ExternalModelConfiguration":
            external_response = APIResponse[ExternalModelConfiguration](**response_data)
            return external_response.results[0]
        else:
            standard_response = APIResponse[ModelConfiguration](**response_data)
            return standard_response.results[0]

    def get_model_states_by_asset(
        self,
        asset_id: str,
        include_descendants: bool = False,
        include_inactive: bool = False,
        skip: int = 0,
        take: int = 500,
    ) -> AsyncIterator[AlertState]:
        """
        List states for all models under an asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            include_descendants: Whether to include models from child assets.
            include_inactive: Whether to include models that are not currently running/active.
            skip: Offset for pagination.
            take: Results per page.

        Returns:
            An async iterator of AlertState objects.
        """
        params = {
            "assetId": asset_id,
            "includeDescendants": str(include_descendants).lower(),
            "includeInactive": str(include_inactive).lower(),
        }
        return self._get_paginated("/v1/models/state", AlertState, params=params, skip=skip, take=take)

    def get_model_actions_by_asset(
        self,
        asset_id: str,
        changed_after: datetime,
        changed_before: datetime,
        favorite: bool = False,
        include_descendants: bool = False,
        skip: int = 0,
        take: int = 500,
    ) -> AsyncIterator[Action]:
        """
        Get all action items for an asset's models within a date range.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            changed_after: Start date for the window.
            changed_before: End date for the window.
            favorite: Filter for only 'favorite' or starred actions.
            include_descendants: Whether to include models from child assets.
            skip: Offset for pagination.
            take: Results per page.

        Returns:
            An async iterator of Action objects.
        """
        params = {
            "assetId": asset_id,
            "changedAfter": _to_utc_ms_str(changed_after),
            "changedBefore": _to_utc_ms_str(changed_before),
        }

        if favorite:
            params["favorite"] = "true"
        if include_descendants:
            params["includeDescendants"] = "true"
        return self._get_paginated("/v1/models/actions", Action, params=params, skip=skip, take=take)

    async def get_model(
        self,
        model: str | Model,
        include_config: bool = False,
        include_state: bool = False,
        include_actions: bool = False,
        actions_changed_after: datetime | None = None,
        actions_changed_before: datetime | None = None,
    ) -> Model:
        """
        Get a Model object, optionally including configuration, state, and actions.

        Args:
            model: Either a Model ID (str) or a Model object (which must have an ID).
            include_config: Whether to fetch and include the model configuration.
            include_state: Whether to fetch and include the current alert state.
            include_actions: Whether to fetch and include recent actions.
            actions_changed_after: Filter actions modified after this date (only used if include_actions=True).
            actions_changed_before: Filter actions modified before this date (only used if include_actions=True).

        Returns:
            A Model object with the requested information populated.
        """
        if isinstance(model, Model):
            model_id = model.model_id
            result_model = model.model_copy()
        else:
            model_id = model
            result_model = Model(model_id=model_id)

        if include_config:
            try:
                result_model.config = await self.get_model_config(model_id)
            except Exception as e:
                logger.warning("Failed to fetch config for model %s: %s", model_id, e)

        if include_state:
            try:
                result_model.alert_state = await self.get_model_state(model_id)
            except Exception as e:
                logger.warning("Failed to fetch state for model %s: %s", model_id, e)

        if include_actions:
            try:
                actions = []
                async for action in self.get_model_actions(
                    model_id,
                    changed_after=actions_changed_after,
                    changed_before=actions_changed_before,
                ):
                    actions.append(action)
                result_model.actions = actions
            except Exception as e:
                logger.warning("Failed to fetch actions for model %s: %s", model_id, e)

        return result_model
