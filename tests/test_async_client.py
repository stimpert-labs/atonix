# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the async API: AsyncAtonixClient and async resource classes."""

from datetime import datetime, timezone

import pytest
import respx
from httpx import Response

from atonix.client import AsyncAtonixClient
from atonix.exceptions import APIError, AuthenticationError, NotFoundError, QuerySizeError, ServerError
from atonix.object_models.assets import Asset
from atonix.object_models.issues import BareIssue, Issue, IssueCreate, IssueKeyword, IssuePatch
from atonix.object_models.models import Action, AlertState, Model, ModelConfiguration
from atonix.object_models.processdata import Server, Tag, TagData
from tests.conftest import (
    BASE_URL,
    make_alert_state,
    make_api_response,
    make_asset,
    make_assets,
    make_bare_issues,
    make_issue,
    make_model_config,
    make_models,
    make_servers,
    make_tag,
    make_tags,
    query_echo_side_effect,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def async_mock_client(mock_private_key) -> AsyncAtonixClient:
    """Create an AsyncAtonixClient with mocked auth for unit tests."""
    return AsyncAtonixClient(
        api_key="test-api-key-1234567890abcdef",
        private_key=mock_private_key,
        max_retries=1,
        timeout=5,
    )


# ---------------------------------------------------------------------------
# AsyncAtonixClient
# ---------------------------------------------------------------------------


class TestAsyncAtonixClient:
    """Tests for the AsyncAtonixClient class."""

    def test_init_creates_async_resources(self, async_mock_client):
        """AsyncAtonixClient should initialize async resource attributes."""
        assert hasattr(async_mock_client, "assets")
        assert hasattr(async_mock_client, "issues")
        assert hasattr(async_mock_client, "models")
        assert hasattr(async_mock_client, "process_data")

    @pytest.mark.anyio
    @respx.mock
    async def test_async_context_manager(self, mock_private_key):
        """AsyncAtonixClient should work as an async context manager."""
        async with AsyncAtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=1,
        ) as client:
            respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))
            result = await client.get("/v1/assets")
        assert result["Success"] is True

    @pytest.mark.anyio
    @respx.mock
    async def test_get_request(self, async_mock_client):
        """Async GET request should return parsed response."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([make_asset()])))
        result = await async_mock_client.get("/v1/assets")
        assert result["Success"] is True

    @pytest.mark.anyio
    @respx.mock
    async def test_post_request(self, async_mock_client):
        """Async POST request should return parsed response."""
        respx.post(f"{BASE_URL}/v1/issues").mock(return_value=Response(200, json=make_api_response([])))
        result = await async_mock_client.post("/v1/issues", json={"Title": "test"})
        assert result["Success"] is True

    @pytest.mark.anyio
    @respx.mock
    async def test_put_request(self, async_mock_client):
        """Async PUT request should return parsed response."""
        respx.put(f"{BASE_URL}/v1/assets/1").mock(return_value=Response(200, json=make_api_response([])))
        result = await async_mock_client.put("/v1/assets/1", json={"Name": "updated"})
        assert result["Success"] is True

    @pytest.mark.anyio
    @respx.mock
    async def test_patch_request(self, async_mock_client):
        """Async PATCH request should return parsed response."""
        respx.patch(f"{BASE_URL}/v1/assets/1").mock(return_value=Response(200, json=make_api_response([])))
        result = await async_mock_client.patch("/v1/assets/1", json={"Name": "patched"})
        assert result["Success"] is True

    @pytest.mark.anyio
    @respx.mock
    async def test_delete_request(self, async_mock_client):
        """Async DELETE request should execute and return response."""
        respx.delete(f"{BASE_URL}/v1/issues/1/keywords").mock(return_value=Response(204))
        # DELETE on 204 returns text
        await async_mock_client.delete("/v1/issues/1/keywords", json=["k1"])

    @pytest.mark.anyio
    @respx.mock
    async def test_handles_401_error(self, async_mock_client):
        """401 response should raise AuthenticationError."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(401, json={"Success": False}))
        with pytest.raises(AuthenticationError):
            await async_mock_client.get("/v1/assets")

    @pytest.mark.anyio
    @respx.mock
    async def test_handles_404_error(self, async_mock_client):
        """404 response should raise NotFoundError."""
        respx.get(f"{BASE_URL}/v1/assets/nonexistent").mock(return_value=Response(404, json={"Success": False}))
        with pytest.raises(NotFoundError):
            await async_mock_client.get("/v1/assets/nonexistent")

    @pytest.mark.anyio
    @respx.mock
    async def test_handles_5xx_raises_server_error(self, mock_private_key):
        """5xx response after last retry should raise ServerError."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(500, json={"Success": False}))
        client = AsyncAtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=1,
        )
        with pytest.raises(ServerError):
            await client.get("/v1/assets")

    @pytest.mark.anyio
    @respx.mock
    async def test_request_error_raises_api_error(self, mock_private_key):
        """Network error on last attempt should raise APIError."""
        import httpx as _httpx

        respx.get(f"{BASE_URL}/v1/assets").mock(side_effect=_httpx.ConnectError("refused"))
        client = AsyncAtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=1,
        )
        with pytest.raises(APIError, match="Network error"):
            await client.get("/v1/assets")

    @pytest.mark.anyio
    @respx.mock
    async def test_retries_on_transient_error(self, mock_private_key, monkeypatch):
        """Async client should retry on transient 5xx and succeed."""
        import asyncio

        async def noop(_):
            pass

        monkeypatch.setattr(asyncio, "sleep", noop)

        route = respx.get(f"{BASE_URL}/v1/assets")
        route.side_effect = [
            Response(500, json={"Success": False}),
            Response(200, json=make_api_response([make_asset()])),
        ]
        client = AsyncAtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=2,
        )
        result = await client.get("/v1/assets")
        assert result["Success"] is True
        assert route.call_count == 2


# ---------------------------------------------------------------------------
# AsyncAssets
# ---------------------------------------------------------------------------


class TestAsyncAssets:
    """Tests for AsyncAssets resource methods."""

    @pytest.mark.anyio
    @respx.mock
    async def test_get_top(self, async_mock_client):
        """async get_top should return assets via async iteration."""
        assets_data = make_assets(5)
        respx.get(f"{BASE_URL}/v1/assets").mock(
            return_value=Response(200, json=make_api_response(assets_data, count=5, type_name="Asset"))
        )
        result = [a async for a in async_mock_client.assets.get_top()]
        assert len(result) == 5
        assert all(isinstance(a, Asset) for a in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_asset_details(self, async_mock_client):
        """async get_asset_details should return a single Asset."""
        asset_id = "00000000-0000-0000-0000-000000000001"
        asset_data = make_asset(asset_id=asset_id, abbrev="TestAsset")
        respx.get(f"{BASE_URL}/v1/assets/{asset_id}").mock(
            return_value=Response(200, json=make_api_response([asset_data], count=1, type_name="Asset"))
        )
        result = await async_mock_client.assets.get_asset_details(asset_id)
        assert isinstance(result, Asset)
        assert result.abbrev == "TestAsset"

    @pytest.mark.anyio
    @respx.mock
    async def test_get_children(self, async_mock_client):
        """async get_children should return child assets via async iteration."""
        parent_id = "00000000-0000-0000-0000-000000000001"
        children_data = make_assets(3, start_index=10)
        respx.get(f"{BASE_URL}/v1/assets/{parent_id}/assets").mock(
            return_value=Response(200, json=make_api_response(children_data, count=3, type_name="Asset"))
        )
        result = [a async for a in async_mock_client.assets.get_children(parent_id)]
        assert len(result) == 3

    @pytest.mark.anyio
    @respx.mock
    async def test_get_asset_details_empty_raises(self, async_mock_client):
        """async _get_single should raise ValueError when results are empty."""
        asset_id = "00000000-0000-0000-0000-000000000001"
        respx.get(f"{BASE_URL}/v1/assets/{asset_id}").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )
        with pytest.raises(ValueError, match="No results found"):
            await async_mock_client.assets.get_asset_details(asset_id)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_children_with_date_filters(self, async_mock_client):
        """async get_children should pass date filter params."""
        parent_id = "00000000-0000-0000-0000-000000000001"
        route = respx.get(f"{BASE_URL}/v1/assets/{parent_id}/assets").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )
        changed_after = datetime(2024, 1, 1, tzinfo=timezone.utc)
        changed_before = datetime(2024, 6, 1, tzinfo=timezone.utc)
        _ = [
            a
            async for a in async_mock_client.assets.get_children(
                parent_id, changed_after=changed_after, changed_before=changed_before
            )
        ]
        params = route.calls.last.request.url.params
        assert "changedAfter" in params
        assert "changedBefore" in params


# ---------------------------------------------------------------------------
# AsyncIssues
# ---------------------------------------------------------------------------


class TestAsyncIssues:
    """Tests for AsyncIssues resource methods."""

    @pytest.mark.anyio
    @respx.mock
    async def test_get_issues(self, async_mock_client):
        """async get_issues should return issues via async iteration."""
        issues_data = make_bare_issues(4)
        respx.get(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response(issues_data, count=4, type_name="BareIssue"))
        )
        result = [i async for i in async_mock_client.issues.get_issues(asset_id="asset-1")]
        assert len(result) == 4
        assert all(isinstance(i, BareIssue) for i in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_issues_with_status(self, async_mock_client):
        """async get_issues should pass the status filter."""
        issues_data = make_bare_issues(2)
        route = respx.get(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response(issues_data, count=2, type_name="BareIssue"))
        )
        _ = [i async for i in async_mock_client.issues.get_issues(asset_id="asset-1", status="open")]
        assert route.calls.last.request.url.params["status"] == "open"

    @pytest.mark.anyio
    @respx.mock
    async def test_get_issue(self, async_mock_client):
        """async get_issue should return a full Issue."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        respx.get(f"{BASE_URL}/v1/issues/{issue_id}").mock(
            return_value=Response(200, json=make_api_response([make_issue(issue_id=issue_id)], count=1))
        )
        result = await async_mock_client.issues.get_issue(issue_id)
        assert isinstance(result, Issue)
        assert result.id == issue_id

    @pytest.mark.anyio
    @respx.mock
    async def test_create_issue(self, async_mock_client):
        """async create_issue should POST and return created Issue."""
        issue_data = make_issue(title="Async Issue")
        respx.post(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response([issue_data], count=1))
        )
        new_issue = IssueCreate(
            asset_id="00000000-0000-0000-0000-000000000001",
            title="Async Issue",
            category_desc="Maintenance",
            issue_class_type_desc="Mechanical",
        )
        result = await async_mock_client.issues.create_issue(new_issue)
        assert isinstance(result, Issue)

    @pytest.mark.anyio
    @respx.mock
    async def test_patch_issue(self, async_mock_client):
        """async patch_issue should PATCH and return updated Issue."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        issue_data = make_issue(issue_id=issue_id, title="Patched")
        respx.patch(f"{BASE_URL}/v1/issues/{issue_id}").mock(
            return_value=Response(200, json=make_api_response([issue_data], count=1))
        )
        result = await async_mock_client.issues.patch_issue(issue_id, IssuePatch(title="Patched"))
        assert result.title == "Patched"

    @pytest.mark.anyio
    @respx.mock
    async def test_add_keyword(self, async_mock_client):
        """async add_keyword should POST and return created keyword."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        respx.post(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(
            return_value=Response(200, json=make_api_response([{"KeywordDesc": "AsyncKeyword"}], count=1))
        )
        result = await async_mock_client.issues.add_keyword(issue_id, "AsyncKeyword")
        assert isinstance(result, IssueKeyword)
        assert result.keyword_desc == "AsyncKeyword"

    @pytest.mark.anyio
    @respx.mock
    async def test_delete_keywords(self, async_mock_client):
        """async delete_keywords should send DELETE request."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        route = respx.delete(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(return_value=Response(204))
        await async_mock_client.issues.delete_keywords(issue_id, ["K1"])
        assert route.called

    @pytest.mark.anyio
    @respx.mock
    async def test_get_keywords(self, async_mock_client):
        """async get_keywords should return keywords via async iteration."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        respx.get(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(
            return_value=Response(
                200,
                json=make_api_response([{"KeywordDesc": "K1"}, {"KeywordDesc": "K2"}], count=2),
            )
        )
        result = [k async for k in async_mock_client.issues.get_keywords(issue_id)]
        assert len(result) == 2
        assert all(isinstance(k, IssueKeyword) for k in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_discussion_entries(self, async_mock_client):
        """async get_discussion_entries should return entries via async iteration."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        from tests.conftest import make_discussion_entries

        entries_data = make_discussion_entries(2)
        respx.get(f"{BASE_URL}/v1/issues/{issue_id}/discussionentries").mock(
            return_value=Response(200, json=make_api_response(entries_data, count=2))
        )
        result = [e async for e in async_mock_client.issues.get_discussion_entries(issue_id)]
        assert len(result) == 2

    @pytest.mark.anyio
    @respx.mock
    async def test_get_resolution_statuses(self, async_mock_client):
        """async get_resolution_statuses should return statuses via async iteration."""
        statuses_data = [
            {"ResolutionStatus": "Monitoring", "DisplayOrder": 1},
            {"ResolutionStatus": "Resolved", "DisplayOrder": 2},
        ]
        respx.get(f"{BASE_URL}/v1/issues/resolutionstatuses").mock(
            return_value=Response(200, json=make_api_response(statuses_data, count=2))
        )
        result = [s async for s in async_mock_client.issues.get_resolution_statuses(category_id=3)]
        assert len(result) == 2


# ---------------------------------------------------------------------------
# AsyncModels
# ---------------------------------------------------------------------------


class TestAsyncModels:
    """Tests for AsyncModels resource methods."""

    @pytest.mark.anyio
    @respx.mock
    async def test_get_models(self, async_mock_client):
        """async get_models should return models via async iteration."""
        models_data = make_models(6)
        respx.get(f"{BASE_URL}/v1/models").mock(
            return_value=Response(200, json=make_api_response(models_data, count=6, type_name="Model"))
        )
        result = [m async for m in async_mock_client.models.get_models(asset_id="asset-1")]
        assert len(result) == 6
        assert all(isinstance(m, Model) for m in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_state(self, async_mock_client):
        """async get_model_state should return AlertState."""
        model_id = "22222222-2222-2222-2222-222222222222"
        state_data = make_alert_state(active=True)
        respx.get(f"{BASE_URL}/v1/models/{model_id}/state").mock(
            return_value=Response(200, json=make_api_response([state_data], count=1))
        )
        result = await async_mock_client.models.get_model_state(model_id)
        assert isinstance(result, AlertState)
        assert result.active is True

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_config(self, async_mock_client):
        """async get_model_config should return ModelConfiguration."""
        model_id = "22222222-2222-2222-2222-222222222222"
        config_data = make_model_config(model_name="Async Model")
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
        result = await async_mock_client.models.get_model_config(model_id)
        assert isinstance(result, ModelConfiguration)
        assert result.model_name == "Async Model"

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_actions(self, async_mock_client):
        """async get_model_actions should return actions via async iteration."""
        from tests.conftest import make_action_items

        model_id = "22222222-2222-2222-2222-222222222222"
        actions_data = make_action_items(3)
        respx.get(f"{BASE_URL}/v1/models/{model_id}/actions").mock(
            return_value=Response(200, json=make_api_response(actions_data, count=3))
        )
        result = [a async for a in async_mock_client.models.get_model_actions(model_id)]
        assert len(result) == 3
        assert all(isinstance(a, Action) for a in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_states_by_asset(self, async_mock_client):
        """async get_model_states_by_asset should return AlertState objects."""
        from tests.conftest import make_alert_states_by_asset

        states_data = make_alert_states_by_asset(4)
        respx.get(f"{BASE_URL}/v1/models/state").mock(
            return_value=Response(200, json=make_api_response(states_data, count=4))
        )
        result = [s async for s in async_mock_client.models.get_model_states_by_asset("asset-1")]
        assert len(result) == 4
        assert all(isinstance(s, AlertState) for s in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_actions_by_asset(self, async_mock_client):
        """async get_model_actions_by_asset should return actions."""
        from tests.conftest import make_action_items_by_asset

        actions_data = make_action_items_by_asset(2)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        respx.get(f"{BASE_URL}/v1/models/actions").mock(
            return_value=Response(200, json=make_api_response(actions_data, count=2))
        )
        result = [
            a
            async for a in async_mock_client.models.get_model_actions_by_asset(
                "asset-1", changed_after=start, changed_before=end
            )
        ]
        assert len(result) == 2

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_id_only(self, async_mock_client):
        """async get_model with ID only should return Model with no extras."""
        result = await async_mock_client.models.get_model("model-id-123")
        assert result.model_id == "model-id-123"
        assert result.config is None

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_include_state(self, async_mock_client):
        """async get_model with include_state should attach AlertState."""
        model_id = "model-with-state"
        state_data = make_alert_state(active=False)
        respx.get(f"{BASE_URL}/v1/models/{model_id}/state").mock(
            return_value=Response(200, json=make_api_response([state_data], count=1))
        )
        result = await async_mock_client.models.get_model(model_id, include_state=True)
        assert result.alert_state is not None
        assert result.alert_state.active is False

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_include_actions(self, async_mock_client):
        """async get_model with include_actions should attach actions list."""
        from tests.conftest import make_action_items

        model_id = "model-with-actions"
        actions_data = make_action_items(2)
        respx.get(f"{BASE_URL}/v1/models/{model_id}/actions").mock(
            return_value=Response(200, json=make_api_response(actions_data, count=2))
        )
        result = await async_mock_client.models.get_model(model_id, include_actions=True)
        assert result.actions is not None
        assert len(result.actions) == 2


# ---------------------------------------------------------------------------
# AsyncProcessData
# ---------------------------------------------------------------------------


class TestAsyncProcessData:
    """Tests for AsyncProcessData resource methods."""

    @pytest.mark.anyio
    @respx.mock
    async def test_get_servers(self, async_mock_client):
        """async get_servers should return servers via async iteration."""
        servers_data = make_servers(3)
        respx.get(f"{BASE_URL}/v1/processdata/servers").mock(
            return_value=Response(200, json=make_api_response(servers_data, count=3))
        )
        result = [s async for s in async_mock_client.process_data.get_servers()]
        assert len(result) == 3
        assert all(isinstance(s, Server) for s in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_tags_list(self, async_mock_client):
        """async get_tags_list should return tags via async iteration."""
        server_id = "33333333-3333-3333-3333-333333333333"
        tags_data = make_tags(5)
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/tags").mock(
            return_value=Response(200, json=make_api_response(tags_data, count=5))
        )
        result = [t async for t in async_mock_client.process_data.get_tags_list(server_id)]
        assert len(result) == 5
        assert all(isinstance(t, Tag) for t in result)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_tag_details(self, async_mock_client):
        """async get_tag_details should return a single Tag."""
        tag_id = "44444444-4444-4444-4444-444444444444"
        tag_data = make_tag(tag_id=tag_id, name="PressureTag")
        respx.get(f"{BASE_URL}/v1/processdata/tags/{tag_id}").mock(
            return_value=Response(200, json=make_api_response([tag_data], count=1))
        )
        result = await async_mock_client.process_data.get_tag_details(tag_id)
        assert isinstance(result, Tag)
        assert result.name == "PressureTag"

    @pytest.mark.anyio
    @respx.mock
    async def test_get_data_for_range(self, async_mock_client):
        """async get_data_for_range should return TagData results."""
        server_id = "33333333-3333-3333-3333-333333333333"
        tag_id = "44444444-4444-4444-4444-444444444444"

        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": "1min", "Interval": 60}], count=1),
            )
        )
        data_response = {
            "Success": True,
            "StatusCode": 200,
            "Results": [
                {
                    "TagId": tag_id,
                    "HttpCode": 200,
                    "Data": {
                        "Timestamps": ["2024-01-15T12:00:00.000Z"],
                        "Values": [42.0],
                        "Statuses": [0],
                    },
                }
            ],
        }
        respx.post(f"{BASE_URL}/v1/processdata/query").mock(return_value=Response(200, json=data_response))

        result = await async_mock_client.process_data.get_data_for_range(
            server_id=server_id,
            start_time=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 12, 30, tzinfo=timezone.utc),
            tag_ids=[tag_id],
            archive="1min",
        )
        assert len(result) == 1
        assert isinstance(result[0], TagData)

    @pytest.mark.anyio
    async def test_get_data_for_range_invalid_time_raises(self, async_mock_client):
        """async get_data_for_range should raise ValueError when start > end."""
        start = datetime(2024, 2, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="Start time must be before end time"):
            await async_mock_client.process_data.get_data_for_range("server-id", start, end, ["tag-id"], "1min")

    @pytest.mark.anyio
    @respx.mock
    async def test_get_data_for_range_archive_not_found(self, async_mock_client):
        """async get_data_for_range should raise ValueError when archive not found."""
        server_id = "33333333-3333-3333-3333-333333333333"
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": "60min", "Interval": 3600}], count=1),
            )
        )
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="Archive `1min` not found"):
            await async_mock_client.process_data.get_data_for_range(server_id, start, end, ["tag-id"], "1min")

    @pytest.mark.anyio
    @respx.mock
    async def test_write_tag_data(self, async_mock_client):
        """async write_tag_data should POST tag data to API."""
        server_id = "33333333-3333-3333-3333-333333333333"
        respx.post(f"{BASE_URL}/v1/processdata/write").mock(return_value=Response(200, json=make_api_response([])))
        tag_data = [
            TagData(
                tag_id="tag-1",
                timestamps=[datetime.now(timezone.utc)],
                values=[99.9],
                statuses=[0],
            )
        ]
        await async_mock_client.process_data.write_tag_data(server_id, "1min", tag_data)
        assert len(respx.calls) == 1

    @pytest.mark.anyio
    @respx.mock
    async def test_write_tag_data_packs_multiple_tags(self, async_mock_client):
        """async write_tag_data should pack many small TagData entries into a single POST."""
        server_id = "33333333-3333-3333-3333-333333333333"
        route = respx.post(f"{BASE_URL}/v1/processdata/write").mock(
            return_value=Response(200, json=make_api_response([]))
        )
        now = datetime.now(timezone.utc)
        tag_data = [TagData(tag_id=f"tag-{n}", timestamps=[now], values=[float(n)], statuses=[0]) for n in range(50)]
        await async_mock_client.process_data.write_tag_data(server_id, "1min", tag_data)

        assert len(respx.calls) == 1
        import json

        payload = json.loads(route.calls[0].request.content)
        assert len(payload["TagData"]) == 50

    @pytest.mark.anyio
    @respx.mock
    async def test_get_tags_list_with_date_filters(self, async_mock_client):
        """async get_tags_list should pass changedAfter and changedBefore."""
        server_id = "33333333-3333-3333-3333-333333333333"
        route = respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/tags").mock(
            return_value=Response(200, json=make_api_response(make_tags(3), count=3))
        )
        changed_after = datetime(2024, 1, 1, tzinfo=timezone.utc)
        changed_before = datetime(2024, 6, 1, tzinfo=timezone.utc)
        _ = [
            t
            async for t in async_mock_client.process_data.get_tags_list(
                server_id, changed_after=changed_after, changed_before=changed_before
            )
        ]
        params = route.calls.last.request.url.params
        assert "changedAfter" in params
        assert "changedBefore" in params

    @pytest.mark.anyio
    @respx.mock
    async def test_get_data_for_range_query_too_large(self, async_mock_client):
        """async get_data_for_range(chunk=False) should raise QuerySizeError when point count exceeds limit."""
        server_id = "33333333-3333-3333-3333-333333333333"
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": "1min", "Interval": 60}], count=1),
            )
        )
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, tzinfo=timezone.utc)
        tag_ids = [f"tag-{i}" for i in range(500)]
        with pytest.raises(QuerySizeError, match="Query size exceeds limit"):
            await async_mock_client.process_data.get_data_for_range(server_id, start, end, tag_ids, "1min", chunk=False)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_data_for_range_chunks_large_query(self, async_mock_client):
        """async get_data_for_range should split an oversized query and reassemble per-tag results."""
        server_id = "33333333-3333-3333-3333-333333333333"
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(200, json=make_api_response([{"Name": "1min", "Interval": 60}], count=1))
        )
        route = respx.post(f"{BASE_URL}/v1/processdata/query").mock(side_effect=query_echo_side_effect)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, tzinfo=timezone.utc)  # 527,040 minutes → 3 windows
        tag_ids = ["tag-0", "tag-1"]

        result = await async_mock_client.process_data.get_data_for_range(server_id, start, end, tag_ids, "1min")

        # 3 windows x 2 tag groups (2 tags don't fit in one ~175k-point window)
        assert route.call_count == 6
        assert [r.tag_id for r in result] == tag_ids
        for r in result:
            # Each window contributes Start+End; the 2 shared boundaries are deduplicated.
            assert len(r.timestamps) == 4
            assert r.timestamps[0] == start
            assert r.timestamps[-1] == end

    @pytest.mark.anyio
    @respx.mock
    async def test_get_data_for_range_non_2xx_tag_logged(self, async_mock_client):
        """async get_data_for_range should log but not raise for non-2xx tag http_code."""
        server_id = "33333333-3333-3333-3333-333333333333"
        tag_id = "44444444-4444-4444-4444-444444444444"
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(200, json=make_api_response([{"Name": "1min", "Interval": 60}], count=1))
        )
        data_response = {
            "Success": True,
            "StatusCode": 200,
            "Results": [
                {"TagId": tag_id, "HttpCode": 404, "Data": {"Timestamps": [], "Values": [], "Statuses": []}},
            ],
        }
        respx.post(f"{BASE_URL}/v1/processdata/query").mock(return_value=Response(200, json=data_response))
        start = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 1, tzinfo=timezone.utc)
        result = await async_mock_client.process_data.get_data_for_range(server_id, start, end, [tag_id], "1min")
        assert result[0].http_code == 404


# ---------------------------------------------------------------------------
# Additional edge cases for higher coverage
# ---------------------------------------------------------------------------


class TestAsyncBaseResourcePagination:
    """Tests for async pagination continuation."""

    @pytest.mark.anyio
    @respx.mock
    async def test_async_get_paginated_continuation(self, async_mock_client):
        """Async _get_paginated should continue fetching when page is full."""
        page1 = make_assets(50)
        page2 = make_assets(10, start_index=50)
        respx.get(f"{BASE_URL}/v1/assets", params={"skip": 0, "take": 50}).mock(
            return_value=Response(200, json=make_api_response(page1, count=50))
        )
        respx.get(f"{BASE_URL}/v1/assets", params={"skip": 50, "take": 50}).mock(
            return_value=Response(200, json=make_api_response(page2, count=10))
        )
        result = [a async for a in async_mock_client.assets.get_top(take=50)]
        assert len(result) == 60
        assert len(respx.calls) == 2


class TestAsyncClientRetry:
    """Tests for async client retry behavior."""

    @pytest.mark.anyio
    @respx.mock
    async def test_request_error_retries_then_succeeds(self, mock_private_key, monkeypatch):
        """httpx.RequestError on first async attempt should retry and succeed."""
        import asyncio

        import httpx as _httpx

        async def noop(_):
            pass

        monkeypatch.setattr(asyncio, "sleep", noop)

        route = respx.get(f"{BASE_URL}/v1/assets")
        route.side_effect = [
            _httpx.ConnectError("refused"),
            Response(200, json=make_api_response([make_asset()])),
        ]
        client = AsyncAtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=2,
        )
        result = await client.get("/v1/assets")
        assert result["Success"] is True
        assert route.call_count == 2


class TestAsyncIssuesErrorPaths:
    """Tests for async Issues error-raise paths."""

    @pytest.mark.anyio
    @respx.mock
    async def test_create_issue_no_results_raises(self, async_mock_client):
        """async create_issue should raise APIError when no results returned."""
        respx.post(f"{BASE_URL}/v1/issues").mock(return_value=Response(200, json=make_api_response([], count=0)))
        new_issue = IssueCreate(
            asset_id="asset-1",
            title="Fail Issue",
            category_desc="Maintenance",
            issue_class_type_desc="Mechanical",
        )
        with pytest.raises(APIError, match="Failed to retrieve created issue"):
            await async_mock_client.issues.create_issue(new_issue)

    @pytest.mark.anyio
    @respx.mock
    async def test_patch_issue_no_results_raises(self, async_mock_client):
        """async patch_issue should raise APIError when no results returned."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        respx.patch(f"{BASE_URL}/v1/issues/{issue_id}").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )
        with pytest.raises(APIError, match="No result returned when patching"):
            await async_mock_client.issues.patch_issue(issue_id, IssuePatch(title="x"))

    @pytest.mark.anyio
    @respx.mock
    async def test_add_keyword_no_results_raises(self, async_mock_client):
        """async add_keyword should raise APIError when no results returned."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        respx.post(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )
        with pytest.raises(APIError):
            await async_mock_client.issues.add_keyword(issue_id, "kw")


class TestAsyncModelsEdgeCases:
    """Additional edge cases for AsyncModels."""

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_from_model_object(self, async_mock_client):
        """async get_model should accept a Model object and use model_copy()."""
        input_model = Model(Id="model-obj", Name="Original")
        result = await async_mock_client.models.get_model(input_model)
        assert result.model_id == "model-obj"
        assert result.name == "Original"
        assert result is not input_model

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_include_config(self, async_mock_client):
        """async get_model with include_config should attach config."""
        from tests.conftest import make_model_config

        model_id = "model-conf-async"
        config_data = make_model_config(model_name="Async Config Model")
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
        result = await async_mock_client.models.get_model(model_id, include_config=True)
        assert result.config is not None

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_config_failure_suppressed(self, async_mock_client):
        """async get_model should suppress config fetch errors."""
        model_id = "model-conf-fail"
        respx.get(f"{BASE_URL}/v1/models/{model_id}/config").mock(return_value=Response(404, json={"Success": False}))
        result = await async_mock_client.models.get_model(model_id, include_config=True)
        assert result.config is None

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_state_failure_suppressed(self, async_mock_client):
        """async get_model should suppress state fetch errors."""
        model_id = "model-state-fail"
        respx.get(f"{BASE_URL}/v1/models/{model_id}/state").mock(return_value=Response(500, json={"Success": False}))
        result = await async_mock_client.models.get_model(model_id, include_state=True)
        assert result.alert_state is None

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_actions_failure_suppressed(self, async_mock_client):
        """async get_model should suppress actions fetch errors."""
        model_id = "model-actions-fail"
        respx.get(f"{BASE_URL}/v1/models/{model_id}/actions").mock(return_value=Response(500, json={"Success": False}))
        result = await async_mock_client.models.get_model(model_id, include_actions=True)
        assert result.actions is None

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_config_external(self, async_mock_client):
        """async get_model_config should detect ExternalModelConfiguration."""
        from atonix.object_models.models import ExternalModelConfiguration
        from tests.conftest import make_external_model_config

        model_id = "model-ext"
        config_data = make_external_model_config(model_name="External Async")
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
        result = await async_mock_client.models.get_model_config(model_id)
        assert isinstance(result, ExternalModelConfiguration)

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_actions_with_date_filters(self, async_mock_client):
        """async get_model_actions should pass changedAfter and changedBefore."""
        from tests.conftest import make_action_items

        model_id = "model-act-filter"
        actions_data = make_action_items(1)
        route = respx.get(f"{BASE_URL}/v1/models/{model_id}/actions").mock(
            return_value=Response(200, json=make_api_response(actions_data, count=1))
        )
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        _ = [
            a
            async for a in async_mock_client.models.get_model_actions(model_id, changed_after=start, changed_before=end)
        ]
        params = route.calls.last.request.url.params
        assert "changedAfter" in params
        assert "changedBefore" in params

    @pytest.mark.anyio
    @respx.mock
    async def test_get_model_actions_by_asset_with_flags(self, async_mock_client):
        """async get_model_actions_by_asset should pass favorite and includeDescendants."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 31, tzinfo=timezone.utc)
        route = respx.get(f"{BASE_URL}/v1/models/actions").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )
        _ = [
            a
            async for a in async_mock_client.models.get_model_actions_by_asset(
                "asset-1", changed_after=start, changed_before=end, favorite=True, include_descendants=True
            )
        ]
        params = route.calls.last.request.url.params
        assert params["favorite"] == "true"
        assert params["includeDescendants"] == "true"
