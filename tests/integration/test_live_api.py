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


class TestLiveRequestSigning:
    """Probes that the server accepts the request signature (#12, #13).

    These only assert that the server did not reject the signature (no
    AuthenticationError). A 400/404 for an unknown parameter or archive still
    proves the signature check passed.
    """

    def test_non_ascii_query_param_signature_accepted(self, live_client):
        """A non-ASCII query value is signed as UTF-8 and accepted by the server."""
        from atonix.exceptions import AtonixError, AuthenticationError

        try:
            live_client.get("/v1/assets", params={"skip": 0, "take": 1, "atonixProbe": "Kühler-温度"})
        except AuthenticationError:
            raise
        except AtonixError:
            pass

    def test_json_body_signature_accepted(self, live_client):
        """A POST body is signed and sent as the same bytes, and the server accepts it."""
        from datetime import datetime, timedelta, timezone
        from itertools import islice

        from atonix.exceptions import AtonixError, AuthenticationError

        servers = list(islice(live_client.process_data.get_servers(take=1), 1))
        if not servers:
            pytest.skip("No servers available to test with")
        tags = list(islice(live_client.process_data.get_tags_list(servers[0].server_id, take=1), 1))
        if not tags:
            pytest.skip("No tags available to test with")

        end = datetime.now(timezone.utc)
        payload = {
            "ServerId": servers[0].server_id,
            "Start": (end - timedelta(hours=1)).isoformat(),
            "End": end.isoformat(),
            "Archive": "Ünïcødé-probe",
            "TagIds": [tags[0].tag_id],
        }
        try:
            live_client.post("/v1/processdata/query", json=payload)
        except AuthenticationError:
            raise
        except AtonixError:
            pass

    def test_assets_with_null_dates_parse(self, live_client):
        """Iterating top-level assets and their children must not fail on null dates (#21)."""
        top_assets = list(live_client.assets.get_top())
        for asset in top_assets[:5]:
            list(live_client.assets.get_children(asset.id))
