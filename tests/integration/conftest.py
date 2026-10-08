# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Configuration for integration tests with real API credentials."""

import os

import pytest
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

from atonix.client import AtonixClient, AtonixEnvironment


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
def atonix_environment():
    """Get environment from environment variable, default to US."""
    env_name = os.environ.get("ATONIX_ENVIRONMENT", "US").upper()
    if env_name == "INDIA":
        return AtonixEnvironment.INDIA
    return AtonixEnvironment.US


@pytest.fixture(scope="session")
def live_client(api_key, private_key, atonix_environment):
    """Create a real AtonixClient for integration testing."""
    return AtonixClient(api_key=api_key, private_key=private_key, environment=atonix_environment)
