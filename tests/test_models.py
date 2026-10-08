# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the Models resource."""

from datetime import datetime, timezone

import respx
from httpx import Response

from atonix.models import Models
from atonix.object_models.models import (
    Action,
    AlertState,
    ExternalModelConfiguration,
    Model,
    ModelConfiguration,
)
from tests.conftest import (
    BASE_URL,
    make_action_items_by_asset,
    make_alert_state,
    make_alert_states_by_asset,
    make_api_response,
    make_external_model_config,
    make_model_config,
    make_models,
)


class TestGetModels:
    """Tests for Models.get_models()."""

    @respx.mock
    def test_get_models_single_page(self, mock_client):
        """get_models should return models when count < take."""
        models_data = make_models(10)
        respx.get(f"{BASE_URL}/v1/models").mock(
            return_value=Response(200, json=make_api_response(models_data, count=10, type_name="Model"))
        )

        models_api = Models(mock_client)
        result = list(models_api.get_models(asset_id="test-asset-id"))

        assert len(result) == 10
        assert all(isinstance(m, Model) for m in result)

    @respx.mock
    def test_get_models_pagination(self, mock_client):
        """get_models should paginate when results exceed max take (500)."""
        # First page
        page1_models = make_models(500, start_index=0)
        respx.get(f"{BASE_URL}/v1/models", params={"skip": 0, "take": 500}).mock(
            return_value=Response(200, json=make_api_response(page1_models, count=500, type_name="Model"))
        )

        # Second page
        page2_models = make_models(250, start_index=500)
        respx.get(f"{BASE_URL}/v1/models", params={"skip": 500, "take": 500}).mock(
            return_value=Response(200, json=make_api_response(page2_models, count=250, type_name="Model"))
        )

        models_api = Models(mock_client)
        result = list(models_api.get_models(asset_id="test-asset-id", take=500))

        assert len(result) == 750
        assert len(respx.calls) == 2


class TestGetModelState:
    """Tests for Models.get_model_state()."""

    @respx.mock
    def test_get_model_state_returns_alert_state(self, mock_client):
        """get_model_state should return AlertState object."""
        model_id = "22222222-2222-2222-2222-222222222222"
        state_data = make_alert_state(active=True, active_alerts=["HHA"])
        respx.get(f"{BASE_URL}/v1/models/{model_id}/state").mock(
            return_value=Response(200, json=make_api_response([state_data], count=1, type_name="AlertState"))
        )

        models_api = Models(mock_client)
        result = models_api.get_model_state(model_id)

        assert isinstance(result, AlertState)
        assert result.active is True
        assert "HHA" in result.active_alerts


class TestGetModelConfig:
    """Tests for Models.get_model_config()."""

    @respx.mock
    def test_get_model_config_standard(self, mock_client):
        """get_model_config should return ModelConfiguration."""
        model_id = "22222222-2222-2222-2222-222222222222"
        config_data = make_model_config(model_name="Standard Model")
        respx.get(f"{BASE_URL}/v1/models/{model_id}/config").mock(
            return_value=Response(
                200,
                json={
                    "Success": True,
                    "StatusCode": 200,
                    "Type": "ModelConfiguration",
                    "Results": [config_data],
                },
            )
        )

        models_api = Models(mock_client)
        result = models_api.get_model_config(model_id)

        assert isinstance(result, ModelConfiguration)
        assert result.model_name == "Standard Model"

    @respx.mock
    def test_get_model_config_external(self, mock_client):
        """get_model_config should return ExternalModelConfiguration."""
        model_id = "22222222-2222-2222-2222-222222222222"
        config_data = make_external_model_config(model_name="External Model")
        respx.get(f"{BASE_URL}/v1/models/{model_id}/config").mock(
            return_value=Response(
                200,
                json={
                    "Success": True,
                    "StatusCode": 200,
                    "Type": "ExternalModelConfiguration",
                    "Results": [config_data],
                },
            )
        )

        models_api = Models(mock_client)
        result = models_api.get_model_config(model_id)

        assert isinstance(result, ExternalModelConfiguration)
        assert result.model_type == "External"

    @respx.mock
    def test_get_model_states_by_asset(self, mock_client):
        """get_model_states_by_asset should return AlertState objects for all models under an asset."""
        asset_id = "00000000-0000-0000-0000-000000000001"
        states_data = make_alert_states_by_asset(5)
        respx.get(f"{BASE_URL}/v1/models/state").mock(
            return_value=Response(200, json=make_api_response(states_data, count=5, type_name="AlertState"))
        )

        models_api = Models(mock_client)
        result = list(models_api.get_model_states_by_asset(asset_id))

        assert len(result) == 5
        assert all(isinstance(s, AlertState) for s in result)

    @respx.mock
    def test_get_model_actions_by_asset(self, mock_client):
        """get_model_actions_by_asset should return Action objects for an asset's models."""
        asset_id = "00000000-0000-0000-0000-000000000001"
        actions_data = make_action_items_by_asset(3)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        respx.get(f"{BASE_URL}/v1/models/actions").mock(
            return_value=Response(200, json=make_api_response(actions_data, count=3, type_name="Action"))
        )

        models_api = Models(mock_client)
        result = list(models_api.get_model_actions_by_asset(asset_id, changed_after=start, changed_before=end))

        assert len(result) == 3
        assert all(isinstance(a, Action) for a in result)

    @respx.mock
    def test_get_model_actions_by_asset_with_flags(self, mock_client):
        """get_model_actions_by_asset should pass favorite and includeDescendants when set."""
        asset_id = "00000000-0000-0000-0000-000000000001"
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        route = respx.get(f"{BASE_URL}/v1/models/actions").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )

        models_api = Models(mock_client)
        list(
            models_api.get_model_actions_by_asset(
                asset_id, changed_after=start, changed_before=end, favorite=True, include_descendants=True
            )
        )

        params = route.calls.last.request.url.params
        assert params["favorite"] == "true"
        assert params["includeDescendants"] == "true"

    @respx.mock
    def test_get_model_config_with_null_list_fields(self, mock_client):
        """get_model_config should handle null list fields gracefully.

        This tests the fix for GitHub issue #9 where the API sometimes
        returns null instead of empty arrays for list fields.
        """
        model_id = "22222222-2222-2222-2222-222222222222"
        config_data = {
            "Active": True,
            "ModelName": "Model With Nulls",
            "ModelType": "APR",
            "TagId": "55555555-5555-5555-5555-555555555555",
            "TagName": "Example Tag",
            "MethodTypes": None,  # API returns null
            "Inputs": None,  # API returns null
            "OpModeTypes": None,  # API returns null
            "TrainingData": {"AutoRetrain": True, "MinimumDataPoints": 5040, "TimingParameters": []},
        }
        respx.get(f"{BASE_URL}/v1/models/{model_id}/config").mock(
            return_value=Response(
                200,
                json={
                    "Success": True,
                    "StatusCode": 200,
                    "Type": "ModelConfiguration",
                    "Results": [config_data],
                },
            )
        )

        models_api = Models(mock_client)
        result = models_api.get_model_config(model_id)

        # Verify object is created successfully
        assert isinstance(result, ModelConfiguration)
        assert result.model_name == "Model With Nulls"

        # Verify null list fields are converted to empty lists
        assert result.method_types == []
        assert result.inputs == []
        assert result.op_mode_types == []


class TestGetModel:
    """Tests for Models.get_model() error-suppression branches."""

    @respx.mock
    def test_get_model_config_failure_is_suppressed(self, mock_client):
        """get_model should log and continue when config fetch fails."""
        model_id = "22222222-2222-2222-2222-222222222222"
        respx.get(f"{BASE_URL}/v1/models/{model_id}/config").mock(return_value=Response(404, json={"Success": False}))

        models_api = Models(mock_client)
        result = models_api.get_model(model_id, include_config=True)

        assert result.model_id == model_id
        assert result.config is None

    @respx.mock
    def test_get_model_state_failure_is_suppressed(self, mock_client):
        """get_model should log and continue when state fetch fails."""
        model_id = "22222222-2222-2222-2222-222222222222"
        respx.get(f"{BASE_URL}/v1/models/{model_id}/state").mock(return_value=Response(404, json={"Success": False}))

        models_api = Models(mock_client)
        result = models_api.get_model(model_id, include_state=True)

        assert result.model_id == model_id
        assert result.alert_state is None

    @respx.mock
    def test_get_model_actions_failure_is_suppressed(self, mock_client):
        """get_model should log and continue when actions fetch fails."""
        model_id = "22222222-2222-2222-2222-222222222222"
        respx.get(f"{BASE_URL}/v1/models/{model_id}/actions").mock(return_value=Response(500, json={"Success": False}))

        models_api = Models(mock_client)
        result = models_api.get_model(model_id, include_actions=True)

        assert result.model_id == model_id
        assert result.actions is None
