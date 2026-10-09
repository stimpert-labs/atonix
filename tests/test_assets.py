# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the Assets resource."""

from datetime import datetime, timezone

import pytest
import respx
from httpx import Response

from atonix.assets import Assets
from atonix.object_models.assets import Asset
from tests.conftest import BASE_URL, make_api_response, make_asset, make_assets


class TestAssets:
    """Tests for the Assets resource methods."""

    @respx.mock
    def test_get_top_single_page(self, mock_client):
        """get_top should return assets when count < take."""
        assets_data = make_assets(10)
        respx.get(f"{BASE_URL}/v1/assets").mock(
            return_value=Response(200, json=make_api_response(assets_data, count=10, type_name="Asset"))
        )

        assets_api = Assets(mock_client)
        result = list(assets_api.get_top())

        assert len(result) == 10
        assert all(isinstance(a, Asset) for a in result)

    @respx.mock
    def test_get_top_tolerates_null_dates(self, mock_client):
        """A null CreateDate/ChangeDate mid-page must not break iteration (#21)."""
        assets_data = make_assets(3)
        assets_data[1]["CreateDate"] = None
        assets_data[1]["ChangeDate"] = None
        respx.get(f"{BASE_URL}/v1/assets").mock(
            return_value=Response(200, json=make_api_response(assets_data, count=3, type_name="Asset"))
        )

        result = list(Assets(mock_client).get_top())

        assert len(result) == 3
        assert result[1].create_date is None
        assert result[1].change_date is None
        assert result[0].create_date is not None

    @respx.mock
    def test_get_top_pagination_exceeds_max_take(self, mock_client):
        """get_top should paginate when results exceed max take (50)."""
        # First page
        page1_assets = make_assets(50, start_index=0)
        respx.get(f"{BASE_URL}/v1/assets", params={"skip": 0, "take": 50}).mock(
            return_value=Response(200, json=make_api_response(page1_assets, count=50, type_name="Asset"))
        )

        # Second page
        page2_assets = make_assets(25, start_index=50)
        respx.get(f"{BASE_URL}/v1/assets", params={"skip": 50, "take": 50}).mock(
            return_value=Response(200, json=make_api_response(page2_assets, count=25, type_name="Asset"))
        )

        assets_api = Assets(mock_client)
        result = list(assets_api.get_top(take=50))

        assert len(result) == 75
        assert len(respx.calls) == 2

    @respx.mock
    def test_get_asset_details(self, mock_client):
        """get_asset_details should return a single Asset."""
        asset_id = "00000000-0000-0000-0000-000000000001"
        asset_data = make_asset(asset_id=asset_id, abbrev="TestAsset")
        respx.get(f"{BASE_URL}/v1/assets/{asset_id}").mock(
            return_value=Response(200, json=make_api_response([asset_data], count=1, type_name="Asset"))
        )

        assets_api = Assets(mock_client)
        result = assets_api.get_asset_details(asset_id)

        assert isinstance(result, Asset)
        assert result.id == asset_id
        assert result.abbrev == "TestAsset"

    @respx.mock
    def test_get_children_single_page(self, mock_client):
        """get_children should return child assets."""
        parent_id = "00000000-0000-0000-0000-000000000001"
        children_data = make_assets(5, start_index=100)
        respx.get(f"{BASE_URL}/v1/assets/{parent_id}/assets").mock(
            return_value=Response(200, json=make_api_response(children_data, count=5, type_name="Asset"))
        )

        assets_api = Assets(mock_client)
        result = list(assets_api.get_children(parent_id))

        assert len(result) == 5
        assert all(isinstance(a, Asset) for a in result)

    @respx.mock
    def test_get_children_pagination_exceeds_max_take(self, mock_client):
        """get_children should paginate when results exceed max take (500)."""
        parent_id = "00000000-0000-0000-0000-000000000001"

        # First page
        page1_assets = make_assets(500, start_index=0)
        respx.get(f"{BASE_URL}/v1/assets/{parent_id}/assets", params={"skip": 0, "take": 500}).mock(
            return_value=Response(200, json=make_api_response(page1_assets, count=500, type_name="Asset"))
        )

        # Second page
        page2_assets = make_assets(250, start_index=500)
        respx.get(f"{BASE_URL}/v1/assets/{parent_id}/assets", params={"skip": 500, "take": 500}).mock(
            return_value=Response(200, json=make_api_response(page2_assets, count=250, type_name="Asset"))
        )

        assets_api = Assets(mock_client)
        result = list(assets_api.get_children(parent_id, take=500))

        assert len(result) == 750
        assert len(respx.calls) == 2

    @respx.mock
    def test_get_children_with_include_descendants(self, mock_client):
        """get_children should pass includeDescendants parameter."""
        parent_id = "00000000-0000-0000-0000-000000000001"
        route = respx.get(f"{BASE_URL}/v1/assets/{parent_id}/assets").mock(
            return_value=Response(200, json=make_api_response([], count=0, type_name="Asset"))
        )

        assets_api = Assets(mock_client)
        list(assets_api.get_children(parent_id, include_descendants=True))

        assert route.calls.last.request.url.params["includeDescendants"] == "true"

    @respx.mock
    def test_get_children_with_date_filters(self, mock_client):
        """get_children should pass changedAfter and changedBefore when provided."""
        parent_id = "00000000-0000-0000-0000-000000000001"
        route = respx.get(f"{BASE_URL}/v1/assets/{parent_id}/assets").mock(
            return_value=Response(200, json=make_api_response([], count=0, type_name="Asset"))
        )

        changed_after = datetime(2024, 1, 1, tzinfo=timezone.utc)
        changed_before = datetime(2024, 6, 1, tzinfo=timezone.utc)

        assets_api = Assets(mock_client)
        list(assets_api.get_children(parent_id, changed_after=changed_after, changed_before=changed_before))

        params = route.calls.last.request.url.params
        assert "changedAfter" in params
        assert "changedBefore" in params

    @respx.mock
    def test_get_single_empty_results_raises(self, mock_client):
        """_get_single should raise ValueError when the API returns no results."""
        asset_id = "00000000-0000-0000-0000-000000000001"
        respx.get(f"{BASE_URL}/v1/assets/{asset_id}").mock(
            return_value=Response(200, json=make_api_response([], count=0, type_name="Asset"))
        )

        assets_api = Assets(mock_client)
        with pytest.raises(ValueError, match="No results found"):
            assets_api.get_asset_details(asset_id)
