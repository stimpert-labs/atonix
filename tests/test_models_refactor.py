# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from datetime import datetime

import respx
from httpx import Response

from atonix.object_models.models import Model
from tests.conftest import BASE_URL


def test_model_instantiation():
    """Test that Model can be instantiated with minimal and full data."""
    # minimal
    m = Model(Id="model-123")
    assert m.model_id == "model-123"
    assert m.alert_state is None

    # nested instantiation
    m_full = Model(
        Id="model-456",
        Name="Test Model",
        AlertState={"Active": True, "EvaluationTime": "2023-01-01T00:00:00Z"},
        Actions=[
            {"ActionNote": "Note", "ActionType": "Type", "ChangeDate": "2023-01-01T00:00:00Z", "ChangedBy": "User"}
        ],
    )
    assert m_full.model_id == "model-456"
    assert m_full.alert_state.active is True
    assert len(m_full.actions) == 1
    assert m_full.actions[0].action_note == "Note"


@respx.mock
def test_get_model_id_only(mock_client):
    """Test get_model with just ID and no include flags."""
    m = mock_client.models.get_model("model-123")
    assert m.model_id == "model-123"
    assert m.config is None


@respx.mock
def test_get_model_from_obj(mock_client):
    """Test get_model passing a Model object."""
    input_model = Model(Id="model-obj", Name="Existing Name")

    m = mock_client.models.get_model(input_model)
    assert m.model_id == "model-obj"
    assert m.name == "Existing Name"
    assert m is not input_model


@respx.mock
def test_get_model_include_config(mock_client):
    """Test get_model with include_config=True."""
    model_id = "model-conf"

    respx.get(f"{BASE_URL}/v1/models/{model_id}/config").mock(
        return_value=Response(
            200,
            json={
                "Success": True,
                "StatusCode": 200,
                "Results": [
                    {
                        "Active": True,
                        "ModelName": "Test Model",
                        "ModelType": "TestType",
                        "TagId": "tag-1",
                        "TagName": "Test Tag",
                        "Inputs": [
                            {
                                "TagId": "input-tag-1",
                                "TagName": "Input Tag",
                                "IsTagSelected": True,
                                "IsTagRequired": True,
                            }
                        ],
                    }
                ],
            },
        )
    )

    m = mock_client.models.get_model(model_id, include_config=True)
    assert m.model_id == model_id
    assert m.config is not None
    assert m.config.active is True
    # Verify Tag restructuring works
    assert m.config.tag.tag_id == "tag-1"
    assert m.config.tag.name == "Test Tag"
    # Verify Inputs restructuring works
    assert len(m.config.inputs) == 1
    assert m.config.inputs[0].tag.tag_id == "input-tag-1"
    assert m.config.inputs[0].is_tag_selected is True


@respx.mock
def test_get_model_include_state_and_actions(mock_client):
    """Test get_model with include_state=True and include_actions=True."""
    model_id = "model-state-actions"

    respx.get(f"{BASE_URL}/v1/models/{model_id}/state").mock(
        return_value=Response(
            200,
            json={
                "Success": True,
                "StatusCode": 200,
                "Results": [{"Active": False, "EvaluationTime": "2023-01-01T12:00:00Z"}],
            },
        )
    )

    respx.get(f"{BASE_URL}/v1/models/{model_id}/actions", params={"skip": 0, "take": 500}).mock(
        return_value=Response(
            200,
            json={
                "Success": True,
                "StatusCode": 200,
                "Results": [
                    {
                        "ActionNote": "Fixed",
                        "ActionType": "Comment",
                        "ChangeDate": "2023-01-01T12:00:00Z",
                        "ChangedBy": "Operator",
                    }
                ],
            },
        )
    )

    m = mock_client.models.get_model(model_id, include_state=True, include_actions=True)
    assert m.model_id == model_id
    assert m.alert_state is not None
    assert m.alert_state.active is False
    assert len(m.actions) == 1
    assert m.actions[0].action_note == "Fixed"


@respx.mock
def test_get_model_actions_with_filters(mock_client):
    """Test get_model with include_actions=True and date filters."""
    model_id = "model-actions-filter"
    start_date = datetime(2023, 1, 1, 12, 0, 0)
    end_date = datetime(2023, 1, 31, 12, 0, 0)

    from datetime import timezone

    # Expected formatting: 2023-01-01T12:00:00.000Z
    # The code implementation uses: .astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    def fmt(dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    params = {"skip": 0, "take": 500, "changedAfter": fmt(start_date), "changedBefore": fmt(end_date)}

    respx.get(f"{BASE_URL}/v1/models/{model_id}/actions", params=params).mock(
        return_value=Response(
            200,
            json={
                "Success": True,
                "StatusCode": 200,
                "Results": [
                    {
                        "ActionNote": "Filtered Action",
                        "ActionType": "Comment",
                        "ChangeDate": "2023-01-15T12:00:00Z",
                        "ChangedBy": "Operator",
                    }
                ],
            },
        )
    )

    m = mock_client.models.get_model(
        model_id, include_actions=True, actions_changed_after=start_date, actions_changed_before=end_date
    )

    assert len(m.actions) == 1
    assert m.actions[0].action_note == "Filtered Action"
