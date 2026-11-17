# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Configuration for integration tests with real API credentials."""

import os

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from atonix.client import AtonixClient


def _load_private_key(path: str):
    """Load RSA private key from PEM file."""
    with open(path, "rb") as key_file:
        return serialization.load_pem_private_key(key_file.read(), password=None, backend=default_backend())


@pytest.fixture(scope="session")
def api_key():
    """Load API key from environment variable."""
    key = os.environ.get("ATONIX_API_KEY")
    if not key:
        pytest.skip("ATONIX_API_KEY environment variable not set")
    return key


@pytest.fixture(scope="session")
def private_key():
    """Load private key from path specified in environment variable."""
    key_path = os.environ.get("ATONIX_PRIVATE_KEY_PATH")
    if not key_path:
        pytest.skip("ATONIX_PRIVATE_KEY_PATH environment variable not set")
    if not os.path.exists(key_path):
        pytest.skip(f"Private key file not found: {key_path}")
    return _load_private_key(key_path)


@pytest.fixture(scope="session")
def live_client(api_key, private_key):
    """Create a real AtonixClient for integration testing.

    The target comes from ATONIX_ENVIRONMENT (a region name such as ``US``/``INDIA``,
    or a base URL), resolved by the client itself; it defaults to US.
    """
    return AtonixClient(api_key=api_key, private_key=private_key)


@pytest.fixture(scope="session")
def test_issue_id():
    """Issue that write tests may modify; write tests skip unless this is set."""
    issue_id = os.environ.get("ATONIX_TEST_ISSUE_ID")
    if not issue_id:
        pytest.skip("ATONIX_TEST_ISSUE_ID not set; skipping tests that write to the tenant")
    return issue_id
