# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Read-only integration tests for the Atonix API.

These tests require real API credentials and hit the live Atonix API.
They will be skipped if the required environment variables are not set.

Required environment variables:
    ATONIX_API_KEY: Your Atonix API key
    ATONIX_PRIVATE_KEY_PATH: Path to your RSA private key PEM file
    ATONIX_ENVIRONMENT: (Optional) "US" or "INDIA", defaults to "US"

Run with:
    export ATONIX_API_KEY="your-key"
    export ATONIX_PRIVATE_KEY_PATH="/path/to/key.pem"
    uv run pytest tests/integration -m integration -v
"""

from itertools import islice

import pytest

from atonix.object_models.assets import Asset
from atonix.object_models.issues import BareIssue
from atonix.object_models.models import Model
from atonix.object_models.processdata import Server, Tag

pytestmark = pytest.mark.integration

# Resource methods return lazy paginated iterators; read only the first few
# items so a smoke test never walks an entire tenant.
SAMPLE = 5


def _first_asset(live_client) -> Asset:
    asset = next(live_client.assets.get_top(), None)
    if asset is None:
        pytest.skip("No assets available to test with")
    return asset


class TestLiveAssets:
    """Integration tests for Assets API."""

    def test_can_fetch_top_assets(self, live_client):
        """Smoke test: Can authenticate and retrieve top-level assets."""
        assets = list(islice(live_client.assets.get_top(), SAMPLE))

        # May be empty for limited accounts
        assert all(isinstance(a, Asset) for a in assets)

    def test_can_get_asset_children(self, live_client):
        """Smoke test: Can retrieve children of an asset."""
        parent = _first_asset(live_client)
        children = list(islice(live_client.assets.get_children(parent.id), SAMPLE))

        assert all(isinstance(c, Asset) for c in children)


class TestLiveProcessData:
    """Integration tests for ProcessData API."""

    def test_can_list_servers(self, live_client):
        """Smoke test: Can list available data servers."""
        servers = list(islice(live_client.process_data.get_servers(), SAMPLE))

        assert all(isinstance(s, Server) for s in servers)

    def test_can_list_tags_for_server(self, live_client):
        """Smoke test: Can list tags for a server."""
        server = next(live_client.process_data.get_servers(), None)
        if server is None:
            pytest.skip("No servers available to test with")

        tags = list(islice(live_client.process_data.get_tags_list(server.server_id), SAMPLE))

        assert all(isinstance(t, Tag) for t in tags)


class TestLiveIssues:
    """Integration tests for Issues API."""

    def test_can_fetch_issues_for_asset(self, live_client):
        """Smoke test: Can retrieve issues for an asset."""
        asset = _first_asset(live_client)
        issues = list(islice(live_client.issues.get_issues(asset_id=asset.id), SAMPLE))

        assert all(isinstance(i, BareIssue) for i in issues)


class TestLiveModels:
    """Integration tests for Models API."""

    def test_can_fetch_models_for_asset(self, live_client):
        """Smoke test: Can retrieve models for an asset."""
        asset = _first_asset(live_client)
        models = list(islice(live_client.models.get_models(asset_id=asset.id), SAMPLE))

        assert all(isinstance(m, Model) for m in models)
