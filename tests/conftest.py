# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Shared pytest fixtures for Atonix unit tests."""

import json
from typing import Any

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import Request, Response

from atonix.client import AtonixClient

# --- Mock RSA Key ---


@pytest.fixture
def mock_private_key() -> rsa.RSAPrivateKey:
    """Generate a mock RSA private key for testing authentication."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())


# --- Mock Client ---


@pytest.fixture
def mock_client(mock_private_key: rsa.RSAPrivateKey) -> AtonixClient:
    """Create an AtonixClient with mocked auth for unit tests."""
    return AtonixClient(api_key="test-api-key-1234567890abcdef", private_key=mock_private_key, max_retries=1, timeout=5)


# --- Base URL ---

BASE_URL = "https://api-us.pgapm.io"


# --- Sample Response Factories ---


def make_api_response(
    results: list[Any],
    count: int | None = None,
    type_name: str = "Object",
    success: bool = True,
    status_code: int = 200,
) -> dict:
    """Create a standard Atonix API response wrapper."""
    return {
        "Success": success,
        "StatusCode": status_code,
        "Count": count if count is not None else len(results),
        "Type": type_name,
        "Results": results,
    }


# --- Sample Asset Data ---


def make_asset(
    asset_id: str = "00000000-0000-0000-0000-000000000001",
    abbrev: str = "Asset1",
    desc: str = "Test Asset 1",
    parent_id: str | None = None,
    asset_type: str = "Equipment",
) -> dict:
    """Create a sample Asset object."""
    return {
        "Id": asset_id,
        "Abbrev": abbrev,
        "Desc": desc,
        "ParentId": parent_id,
        "AssetTypeName": asset_type,
        "CreateDate": "2024-01-01T00:00:00.000Z",
        "ChangeDate": "2024-01-15T12:00:00.000Z",
    }


def make_assets(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample assets."""
    return [
        make_asset(asset_id=f"00000000-0000-0000-0000-{i:012d}", abbrev=f"Asset{i}", desc=f"Test Asset {i}")
        for i in range(start_index, start_index + count)
    ]


# --- Sample Issue Data ---


def make_bare_issue(issue_id: str = "11111111-1111-1111-1111-111111111111", title: str = "Test Issue") -> dict:
    """Create a sample BareIssue object."""
    return {"Id": issue_id, "Title": title}


def make_issue(
    issue_id: str = "11111111-1111-1111-1111-111111111111",
    title: str = "Test Issue",
    asset_id: str = "00000000-0000-0000-0000-000000000001",
    status: str = "Open",
) -> dict:
    """Create a sample Issue object."""
    return {
        "Id": issue_id,
        "AssetId": asset_id,
        "Title": title,
        "ShortSummary": f"Short summary for {title}",
        "FullSummary": f"Full summary for {title}",
        "CategoryDesc": "Maintenance",
        "CategoryId": 1,
        "ChangedBy": "changed@example.com",
        "ChangeDate": "2024-01-15T12:00:00.000Z",
        "CloseDate": None,
        "CreatedBy": "created@example.com",
        "CreateDate": "2024-01-10T00:00:00.000Z",
        "Impact": 500.0,
        "IssueClassTypeDesc": "Mechanical",
        "IssueStatus": status,
        "IssueTypeDesc": "Performance",
        "IssueCauseTypeDescs": ["Wear and Tear"],
        "Links": {"Snapshot": "https://oi.atonix.com/snap/123"},
        "NumericId": 12345,
        "Priority": "Medium",
        "ResolutionStatus": "Monitoring",
        "ResolveByDate": "2024-02-01T00:00:00.000Z",
        "Scorecard": True,
    }


def make_bare_issues(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample bare issues."""
    return [
        make_bare_issue(issue_id=f"11111111-1111-1111-1111-{i:012d}", title=f"Issue {i}")
        for i in range(start_index, start_index + count)
    ]


# --- Sample Model Data ---


def make_model(model_id: str = "22222222-2222-2222-2222-222222222222", name: str = "Test Model") -> dict:
    """Create a sample Model object."""
    return {"Id": model_id, "Name": name}


def make_models(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample models."""
    return [
        make_model(model_id=f"22222222-2222-2222-2222-{i:012d}", name=f"Model {i}")
        for i in range(start_index, start_index + count)
    ]


def make_alert_state(
    active: bool = True, active_alerts: list[str] | None = None, actual: float = 100.0, expected: float = 90.0
) -> dict:
    """Create a sample AlertState object."""
    return {
        "Active": active,
        "ActiveAlerts": active_alerts or [],
        "Actual": actual,
        "Expected": expected,
        "Lower": expected - 10,
        "Upper": expected + 10,
        "EvaluationTime": "2024-01-15T12:00:00.000Z",
        "Diagnose": False,
        "Watch": False,
        "Issue": False,
        "ModelMaintenance": False,
    }


def make_alert_state_by_asset(
    model_id: str = "22222222-2222-2222-2222-222222222222",
    asset_id: str = "00000000-0000-0000-0000-000000000001",
    **kwargs,
) -> dict:
    """Create a sample AlertStateByAsset object."""
    state = make_alert_state(**kwargs)
    state["ModelId"] = model_id
    state["AssetId"] = asset_id
    return state


def make_alert_states_by_asset(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample alert states by asset."""
    return [
        make_alert_state_by_asset(
            model_id=f"22222222-2222-2222-2222-{i:012d}", asset_id=f"00000000-0000-0000-0000-{i:012d}"
        )
        for i in range(start_index, start_index + count)
    ]


def make_action_item(action_type: str = "Watch Set", action_note: str = "Test action") -> dict:
    """Create a sample ActionItem object."""
    return {
        "ActionType": action_type,
        "ActionNote": action_note,
        "Actual": 100.0,
        "Expected": 90.0,
        "Lower": 80.0,
        "Upper": 100.0,
        "ChangeDate": "2024-01-15T12:00:00.000Z",
        "ChangedBy": "test@example.com",
        "IsFavorite": False,
    }


def make_action_items(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample action items."""
    return [make_action_item(action_note=f"Action {i}") for i in range(start_index, start_index + count)]


def make_action_item_by_asset(
    model_id: str = "22222222-2222-2222-2222-222222222222",
    asset_id: str = "00000000-0000-0000-0000-000000000001",
    **kwargs,
) -> dict:
    """Create a sample ActionItemByAsset object."""
    item = make_action_item(**kwargs)
    item["ModelId"] = model_id
    item["AssetId"] = asset_id
    return item


def make_action_items_by_asset(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample action items by asset."""
    return [
        make_action_item_by_asset(
            model_id=f"22222222-2222-2222-2222-{i:012d}",
            asset_id=f"00000000-0000-0000-0000-{i:012d}",
            action_note=f"Action {i}",
        )
        for i in range(start_index, start_index + count)
    ]


def make_model_config(
    model_name: str = "Standard Model", model_type: str = "APR", asset_id: str = "00000000-0000-0000-0000-000000000001"
) -> dict:
    """Create a sample ModelConfiguration object."""
    return {
        "Active": True,
        "AssetId": asset_id,
        "ModelName": model_name,
        "ModelType": model_type,
        "TagId": "55555555-5555-5555-5555-555555555555",
        "TagName": "Example Tag",
        "EngUnits": "Watts",
        "LastBuildTime": "2024-01-02T03:00:00.000Z",
        "LastSaveTime": "2024-01-02T02:00:00.000Z",
        "MethodTypes": [{"IsActive": True, "MethodType": "GFF", "Score": 95.1}],
        "TrainingData": {
            "AutoRetrain": True,
            "MinimumDataPoints": 5040,
            "TimingParameters": [{"ParameterName": "SampleRate", "TemporalType": "Seconds", "Value": 15}],
        },
        "Inputs": [{"TagId": "tag-id-1", "TagName": "Tag 1", "IsTagSelected": True, "IsTagRequired": True}],
        "OpModeTypes": ["Steady State"],
        "AnomalyCriteria": {"Criticality": {"Upper": "High", "Lower": ""}, "Bias": {"Upper": 25.5, "Lower": 10.5}},
    }


def make_external_model_config(
    model_name: str = "External Model", asset_id: str = "00000000-0000-0000-0000-000000000001"
) -> dict:
    """Create a sample ExternalModelConfiguration object."""
    return {
        "Active": True,
        "ModelName": model_name,
        "ModelType": "External",
        "AssetId": asset_id,
        "DiagnosticDrilldownURL": "https://example.com/drill",
        "ModelConfigurationURL": "https://example.com/config",
        "AnomalyCriteria": {"Criticality": {"Upper": "High", "Lower": ""}},
    }


# --- Sample ProcessData Data ---


def make_server(
    server_id: str = "33333333-3333-3333-3333-333333333333",
    name: str = "Test Server",
    asset_id: str = "00000000-0000-0000-0000-000000000001",
) -> dict:
    """Create a sample Server object."""
    return {"Id": server_id, "Name": name, "AssetId": asset_id}


def make_servers(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample servers."""
    return [
        make_server(server_id=f"33333333-3333-3333-3333-{i:012d}", name=f"Server {i}")
        for i in range(start_index, start_index + count)
    ]


def make_tag(tag_id: str = "44444444-4444-4444-4444-444444444444", name: str = "Tag1") -> dict:
    """Create a sample Tag (list item) object."""
    return {
        "Id": tag_id,
        "Name": name,
        "Description": f"Description for {name}",
        "EngUnit": "Unit",
        "Source": "Test Source",
        "CreateDate": "2024-01-01T00:00:00.000Z",
        "ChangeDate": "2024-01-15T12:00:00.000Z",
    }


def make_tags(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample tags."""
    return [
        make_tag(tag_id=f"44444444-4444-4444-4444-{i:012d}", name=f"Tag{i}")
        for i in range(start_index, start_index + count)
    ]


def make_archive(name: str = "1min", interval: int = 60) -> dict:
    """Create a sample Archive object."""
    return {"Name": name, "Interval": interval}


def make_archives(count: int) -> list[dict]:
    """Generate a list of sample archives."""
    intervals = [("1min", 60), ("5min", 300), ("60min", 3600), ("1day", 86400)]
    return [
        make_archive(name=intervals[i % len(intervals)][0], interval=intervals[i % len(intervals)][1])
        for i in range(count)
    ]


def make_keyword(keyword: str = "TestKeyword") -> dict:
    """Create a sample IssueKeyword object."""
    return {"KeywordDesc": keyword, "CreatedBy": "user@example.com", "CreateDate": "2024-01-15T12:00:00.000Z"}


def make_keywords(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample keywords."""
    return [make_keyword(keyword=f"Keyword{i}") for i in range(start_index, start_index + count)]


def make_discussion_entry(text: str = "Discussion entry text") -> dict:
    """Create a sample IssueDiscussionEntryDetails object."""
    return {
        "Title": "Discussion Title",
        "Contents": text,
        "CreatedBy": "test@example.com",
        "CreateDate": "2024-01-15T12:00:00.000Z",
        "ChangedBy": "test@example.com",
        "ChangeDate": "2024-01-15T12:00:00.000Z",
        "Attachments": [],
    }


def make_discussion_entries(count: int, start_index: int = 0) -> list[dict]:
    """Generate a list of sample discussion entries."""
    return [make_discussion_entry(text=f"Discussion entry {i}") for i in range(start_index, start_index + count)]


def query_echo_side_effect(request: Request) -> Response:
    """respx side effect for /v1/processdata/query that returns the window's Start and End
    as the two data points for every requested tag (mimicking inclusive endpoints)."""
    payload = json.loads(request.content)
    results = [
        {
            "TagId": tag_id,
            "HttpCode": 200,
            "Data": {
                "Timestamps": [payload["Start"], payload["End"]],
                "Values": [1.0, 2.0],
                "Statuses": [0, 0],
            },
        }
        for tag_id in payload["TagIds"]
    ]
    return Response(200, json={"Success": True, "StatusCode": 200, "Results": results})
