# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for Pydantic object models."""

from datetime import datetime, timezone

from atonix.object_models.assets import Asset
from atonix.object_models.common import APIResponse
from atonix.object_models.issues import BareIssue, Issue, IssueCreate, IssueKeyword, IssuePatch
from atonix.object_models.models import AlertState, Model
from atonix.object_models.processdata import Archive, Server, TagData


class TestBaseAtonixModel:
    """Tests for BaseAtonixModel shared functionality."""

    def test_update_from_copies_set_fields(self):
        """update_from should copy fields that were explicitly set on the other model."""
        from pydantic import Field

        from atonix.object_models.common import BaseAtonixModel

        class SampleModel(BaseAtonixModel):
            name: str = Field(default="", alias="Name")
            value: int = Field(default=0, alias="Value")

        base = SampleModel(Name="original", Value=10)
        update = SampleModel(Name="updated")  # only Name is set

        base.update_from(update)

        assert base.name == "updated"
        assert base.value == 10  # unchanged, not in model_fields_set of update


class TestAPIResponse:
    """Tests for the generic APIResponse wrapper."""

    def test_parse_success_response(self):
        """APIResponse should parse standard success response."""
        data = {
            "Success": True,
            "StatusCode": 200,
            "Count": 2,
            "Type": "Asset",
            "Results": [
                {
                    "Id": "1",
                    "Abbrev": "A1",
                    "Desc": "Asset 1",
                    "ParentId": None,
                    "AssetTypeName": "Equipment",
                    "CreateDate": "2024-01-01T00:00:00Z",
                    "ChangeDate": "2024-01-15T00:00:00Z",
                },
                {
                    "Id": "2",
                    "Abbrev": "A2",
                    "Desc": "Asset 2",
                    "ParentId": "1",
                    "AssetTypeName": "Equipment",
                    "CreateDate": "2024-01-01T00:00:00Z",
                    "ChangeDate": "2024-01-15T00:00:00Z",
                },
            ],
        }

        response = APIResponse[Asset](**data)

        assert response.success is True
        assert response.status_code == 200
        assert response.count == 2
        assert len(response.results) == 2
        assert all(isinstance(r, Asset) for r in response.results)

    def test_parse_empty_response(self):
        """APIResponse should handle empty results."""
        data = {"Success": True, "StatusCode": 200, "Count": 0, "Type": "Asset", "Results": []}

        response = APIResponse[Asset](**data)

        assert response.success is True
        assert response.count == 0
        assert len(response.results) == 0

    def test_optional_count_field(self):
        """APIResponse should handle missing Count field."""
        data = {"Success": True, "StatusCode": 200, "Type": "Asset", "Results": []}

        response = APIResponse[Asset](**data)

        assert response.count is None


class TestAssetModel:
    """Tests for Asset Pydantic model."""

    def test_parse_asset_with_camelcase_aliases(self):
        """Asset should parse JSON with CamelCase field names."""
        data = {
            "Id": "00000000-0000-0000-0000-000000000001",
            "Abbrev": "TestAsset",
            "Desc": "Test Asset Description",
            "ParentId": "00000000-0000-0000-0000-000000000000",
            "AssetTypeName": "Compressor",
            "CreateDate": "2024-01-01T00:00:00.000Z",
            "ChangeDate": "2024-01-15T12:00:00.000Z",
        }

        asset = Asset(**data)

        assert asset.id == "00000000-0000-0000-0000-000000000001"
        assert asset.abbrev == "TestAsset"
        assert asset.desc == "Test Asset Description"
        assert asset.asset_type_name == "Compressor"

    def test_parse_asset_with_null_parent(self):
        """Asset should handle null ParentId (root asset)."""
        data = {
            "Id": "00000000-0000-0000-0000-000000000001",
            "Abbrev": "RootAsset",
            "Desc": "Root Asset",
            "ParentId": None,
            "AssetTypeName": "Site",
            "CreateDate": "2024-01-01T00:00:00.000Z",
            "ChangeDate": "2024-01-15T12:00:00.000Z",
        }

        asset = Asset(**data)

        assert asset.parent_id is None


class TestIssueModels:
    """Tests for Issue-related Pydantic models."""

    def test_parse_bare_issue(self):
        """BareIssue should parse minimal issue reference."""
        data = {"Id": "11111111-1111-1111-1111-111111111111", "Title": "Test Issue Title"}

        issue = BareIssue(**data)

        assert issue.id == "11111111-1111-1111-1111-111111111111"
        assert issue.title == "Test Issue Title"

    def test_parse_full_issue(self):
        """Issue should parse full issue details."""
        data = {
            "Id": "11111111-1111-1111-1111-111111111111",
            "Title": "High Vibration Alert",
            "AssetId": "00000000-0000-0000-0000-000000000001",
            "IssueStatus": "Open",
            "CategoryDesc": "Maintenance",
            "CategoryId": 1,
            "IssueClassTypeDesc": "Mechanical",
            "Priority": "High",
            "CreateDate": "2024-01-10T00:00:00.000Z",
            "ChangeDate": "2024-01-15T12:00:00.000Z",
        }

        issue = Issue(**data)

        assert issue.id == "11111111-1111-1111-1111-111111111111"
        assert issue.issue_status == "Open"
        assert issue.priority == "High"

    def test_issue_create_serialization(self):
        """IssueCreate should serialize to CamelCase JSON."""
        issue = IssueCreate(
            asset_id="00000000-0000-0000-0000-000000000001",
            title="New Issue",
            category_desc="Maintenance",
            issue_class_type_desc="Electrical",
        )

        # Serialize with aliases for API
        json_data = issue.model_dump(by_alias=True, exclude_none=True)

        assert "AssetId" in json_data
        assert "Title" in json_data
        assert json_data["Title"] == "New Issue"

    def test_issue_patch_excludes_none(self):
        """IssuePatch should exclude None fields when serializing."""
        patch = IssuePatch(title="Updated Title")

        json_data = patch.model_dump(by_alias=True, exclude_none=True)

        assert "Title" in json_data
        # Other fields should not be present
        assert "Priority" not in json_data

    def test_issue_keyword(self):
        """IssueKeyword should parse keyword description."""
        data = {"KeywordDesc": "CriticalPump"}

        keyword = IssueKeyword(**data)

        assert keyword.keyword_desc == "CriticalPump"


class TestModelModels:
    """Tests for Model-related Pydantic models."""

    def test_parse_model(self):
        """Model should parse model reference."""
        data = {"Id": "22222222-2222-2222-2222-222222222222", "Name": "Pump Vibration Model"}

        model = Model(**data)

        assert model.model_id == "22222222-2222-2222-2222-222222222222"
        assert model.name == "Pump Vibration Model"

    def test_parse_alert_state(self):
        """AlertState should parse alert status fields."""
        data = {
            "Active": True,
            "ActiveAlerts": ["HHA", "AAS"],
            "Actual": 105.5,
            "Expected": 90.0,
            "Lower": 80.0,
            "Upper": 100.0,
            "EvaluationTime": "2024-01-15T12:00:00.000Z",
            "Diagnose": True,
            "Watch": False,
            "Issue": True,
            "ModelMaintenance": False,
        }

        state = AlertState(**data)

        assert state.active is True
        assert "HHA" in state.active_alerts
        assert "AAS" in state.active_alerts
        assert state.actual == 105.5
        assert state.diagnose is True

    def test_parse_alert_state_by_asset(self):
        """AlertState should include model and asset IDs when present (formerly AlertStateByAsset)."""
        data = {
            "ModelId": "22222222-2222-2222-2222-222222222222",
            "AssetId": "00000000-0000-0000-0000-000000000001",
            "Active": True,
            "ActiveAlerts": [],
            "Actual": 90.0,
            "Expected": 90.0,
            "Lower": 80.0,
            "Upper": 100.0,
            "EvaluationTime": "2024-01-15T12:00:00.000Z",
            "Diagnose": False,
            "Watch": False,
            "Issue": False,
            "ModelMaintenance": False,
        }

        state = AlertState(**data)

        assert state.model_id == "22222222-2222-2222-2222-222222222222"
        assert state.asset_id == "00000000-0000-0000-0000-000000000001"


class TestModelConfiguration:
    """Tests for ModelConfiguration Pydantic model."""

    def test_parse_model_configuration_with_null_lists(self):
        """ModelConfiguration should handle null list fields (GitHub issue #9).

        The API sometimes returns null instead of empty arrays for list fields.
        The normalize_null_lists validator should convert these to empty lists.
        """
        from atonix.object_models.models import ModelConfiguration

        data = {
            "Active": True,
            "ModelName": "Test Model",
            "ModelType": "APR",
            "TagId": "55555555-5555-5555-5555-555555555555",
            "TagName": "Example Tag",
            "MethodTypes": None,  # Null instead of []
            "Inputs": None,  # Null instead of []
            "OpModeTypes": None,  # Null instead of []
        }

        # Should not raise validation error
        config = ModelConfiguration(**data)

        # Verify null values were converted to empty lists
        assert config.method_types == []
        assert config.inputs == []
        assert config.op_mode_types == []

    def test_parse_model_configuration_with_populated_lists(self):
        """ModelConfiguration should correctly parse populated list fields."""
        from atonix.object_models.models import ModelConfiguration

        data = {
            "Active": True,
            "ModelName": "Test Model",
            "ModelType": "APR",
            "TagId": "55555555-5555-5555-5555-555555555555",
            "TagName": "Example Tag",
            "MethodTypes": [{"IsActive": True, "MethodType": "GFF", "Score": 95.5}],
            "Inputs": [{"TagId": "tag-1", "TagName": "Input 1", "IsTagSelected": True, "IsTagRequired": True}],
            "OpModeTypes": ["Steady State", "Transient"],
        }

        config = ModelConfiguration(**data)

        # Verify populated lists are preserved
        assert len(config.method_types) == 1
        assert config.method_types[0].method_type == "GFF"
        assert len(config.inputs) == 1
        assert len(config.op_mode_types) == 2


class TestProcessDataModels:
    """Tests for ProcessData-related Pydantic models."""

    def test_parse_server(self):
        """Server should parse server info."""
        data = {
            "Id": "33333333-3333-3333-3333-333333333333",
            "Name": "Plant Data Server",
            "AssetId": "00000000-0000-0000-0000-000000000001",
        }

        server = Server(**data)

        assert server.server_id == "33333333-3333-3333-3333-333333333333"
        assert server.name == "Plant Data Server"

    def test_parse_archive(self):
        """Archive should parse archive info."""
        data = {"Name": "1min", "Interval": 60}

        archive = Archive(**data)

        assert archive.name == "1min"
        assert archive.interval == 60

    def test_tag_data_series_serialization(self):
        """TagData should serialize for write operations."""
        now = datetime.now(timezone.utc)
        series = TagData(tag_id="44444444-4444-4444-4444-444444444444", timestamps=[now], values=[100.5], statuses=[0])

        json_data = series.model_dump(by_alias=True)

        assert "TagId" in json_data
        assert len(json_data["Timestamps"]) == 1
        assert json_data["Values"][0] == 100.5
