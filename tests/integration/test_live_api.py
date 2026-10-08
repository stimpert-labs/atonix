# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Integration tests for the Atonix API.

These tests require real API credentials and hit the live Atonix API.
They will be skipped if the required environment variables are not set.

Required environment variables:
    ATONIX_API_KEY: Your Atonix API key
    ATONIX_PRIVATE_KEY_PATH: Path to your RSA private key PEM file
    ATONIX_ENVIRONMENT: (Optional) "US" or "INDIA", defaults to "US"

Run with:
    export ATONIX_API_KEY="your-key"
    export ATONIX_PRIVATE_KEY_PATH="/path/to/key.pem"
    uv run pytest tests/integration/ -v
"""

import pytest


class TestLiveAssets:
    """Integration tests for Assets API."""

    def test_can_fetch_top_assets(self, live_client):
        """Smoke test: Can authenticate and retrieve top-level assets."""
        assets = live_client.assets.get_top()

        # We should be able to get some assets (may be empty for limited accounts)
        assert isinstance(assets, list)
        # If we got assets, verify they have expected structure
        if assets:
            assert hasattr(assets[0], "id")
            assert hasattr(assets[0], "abbrev")

    def test_can_get_asset_children(self, live_client):
        """Smoke test: Can retrieve children of an asset."""
        top_assets = live_client.assets.get_top()

        if not top_assets:
            pytest.skip("No assets available to test with")

        parent_id = top_assets[0].id
        children = live_client.assets.get_children(parent_id)

        assert isinstance(children, list)


class TestLiveProcessData:
    """Integration tests for ProcessData API."""

    def test_can_list_servers(self, live_client):
        """Smoke test: Can list available data servers."""
        servers = live_client.process_data.get_servers()

        assert isinstance(servers, list)
        # If we got servers, verify they have expected structure
        if servers:
            assert hasattr(servers[0], "id")
            assert hasattr(servers[0], "name")

    def test_can_list_tags_for_server(self, live_client):
        """Smoke test: Can list tags for a server."""
        servers = live_client.process_data.get_servers()

        if not servers:
            pytest.skip("No servers available to test with")

        server_id = servers[0].id
        tags = live_client.process_data.get_tags_list(server_id)

        assert isinstance(tags, list)


class TestLiveIssues:
    """Integration tests for Issues API."""

    def test_can_fetch_issues_for_asset(self, live_client):
        """Smoke test: Can retrieve issues for an asset."""
        top_assets = live_client.assets.get_top()

        if not top_assets:
            pytest.skip("No assets available to test with")

        asset_id = top_assets[0].id
        issues = live_client.issues.get_issues(asset_id=asset_id)

        assert isinstance(issues, list)


class TestLiveModels:
    """Integration tests for Models API."""

    def test_can_fetch_models_for_asset(self, live_client):
        """Smoke test: Can retrieve models for an asset."""
        top_assets = live_client.assets.get_top()

        if not top_assets:
            pytest.skip("No assets available to test with")

        asset_id = top_assets[0].id
        models = live_client.models.get_models(asset_id=asset_id)

        assert isinstance(models, list)
