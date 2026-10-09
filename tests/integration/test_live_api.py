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
    uv run pytest tests/integration/ -m integration -v
"""

from collections.abc import Iterable
from itertools import islice
from typing import TypeVar

import pytest

from atonix.object_models.assets import Asset
from atonix.object_models.issues import BareIssue
from atonix.object_models.models import Model
from atonix.object_models.processdata import Server, Tag

pytestmark = pytest.mark.integration

T = TypeVar("T")

# Listing methods return lazy iterators that page through the whole tenant.
# Each smoke test asks for one small page and stops after SAMPLE_SIZE items.
SAMPLE_SIZE = 3


def _first(items: Iterable[T], n: int = SAMPLE_SIZE) -> list[T]:
    """Return at most the first ``n`` items without consuming the rest."""
    return list(islice(items, n))


def _first_top_asset(live_client) -> Asset:
    """Return one top-level asset, or skip the test if the tenant has none."""
    assets = _first(live_client.assets.get_top(take=1), 1)
    if not assets:
        pytest.skip("No assets available to test with")
    return assets[0]


class TestLiveAssets:
    """Integration tests for Assets API."""

    def test_can_fetch_top_assets(self, live_client):
        """Smoke test: Can authenticate and retrieve top-level assets."""
        assets = _first(live_client.assets.get_top(take=SAMPLE_SIZE))

        # May be empty for limited accounts; the request itself must succeed.
        assert all(isinstance(asset, Asset) for asset in assets)
        for asset in assets:
            assert asset.id

    def test_can_get_asset_children(self, live_client):
        """Smoke test: Can retrieve children of an asset."""
        parent = _first_top_asset(live_client)

        children = _first(live_client.assets.get_children(parent.id, take=SAMPLE_SIZE))

        assert all(isinstance(child, Asset) for child in children)


class TestLiveProcessData:
    """Integration tests for ProcessData API."""

    def test_can_list_servers(self, live_client):
        """Smoke test: Can list available data servers."""
        servers = _first(live_client.process_data.get_servers(take=SAMPLE_SIZE))

        assert all(isinstance(server, Server) for server in servers)
        for server in servers:
            assert server.server_id

    def test_can_list_tags_for_server(self, live_client):
        """Smoke test: Can list tags for a server."""
        servers = _first(live_client.process_data.get_servers(take=1), 1)
        if not servers:
            pytest.skip("No servers available to test with")

        tags = _first(live_client.process_data.get_tags_list(servers[0].server_id, take=SAMPLE_SIZE))

        assert all(isinstance(tag, Tag) for tag in tags)


class TestLiveIssues:
    """Integration tests for Issues API."""

    def test_can_fetch_issues_for_asset(self, live_client):
        """Smoke test: Can retrieve issues for an asset."""
        asset = _first_top_asset(live_client)

        issues = _first(live_client.issues.get_issues(asset_id=asset.id, take=SAMPLE_SIZE))

        assert all(isinstance(issue, BareIssue) for issue in issues)


class TestLiveModels:
    """Integration tests for Models API."""

    def test_can_fetch_models_for_asset(self, live_client):
        """Smoke test: Can retrieve models for an asset."""
        asset = _first_top_asset(live_client)

        models = _first(live_client.models.get_models(asset_id=asset.id, take=SAMPLE_SIZE))

        assert all(isinstance(model, Model) for model in models)


class TestLiveRequestSigning:
    """Probes that the server accepts the request signature (#12, #13).

    These only assert that the server did not reject the signature (no
    AuthenticationError). A 400/404 for an unknown parameter or archive still
    proves the signature check passed.
    """

    def test_non_ascii_query_param_signature_accepted(self, live_client):
        """A non-ASCII query value is signed like .NET Encoding.ASCII and accepted by the server."""
        from atonix.exceptions import AtonixError, AuthenticationError

        try:
            live_client.get("/v1/assets", params={"skip": 0, "take": 1, "atonixProbe": "Kühler-温度"})
        except AuthenticationError:
            raise
        except AtonixError:
            pass

    def test_json_body_signature_accepted(self, live_client):
        """A non-ASCII POST body is signed from the exact wire text, and the server accepts it."""
        from datetime import datetime, timedelta, timezone

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
