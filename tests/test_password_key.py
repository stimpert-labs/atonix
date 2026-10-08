# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
import os
from unittest.mock import MagicMock, mock_open, patch

from cryptography.hazmat.primitives.asymmetric import rsa

from atonix.client import AtonixClient, _load_private_key


def test_load_private_key_with_password():
    """Test _load_private_key with a password."""
    mock_key_data = b"fake-key-data"
    mock_password = "test-password"

    with (
        patch("builtins.open", mock_open(read_data=mock_key_data)),
        patch("atonix.client.serialization.load_pem_private_key") as mock_load,
    ):
        mock_rsa_key = MagicMock(spec=rsa.RSAPrivateKey)
        mock_load.return_value = mock_rsa_key

        key = _load_private_key("fake/path", password=mock_password)

        mock_load.assert_called_once_with(mock_key_data, password=mock_password.encode())
        assert key == mock_rsa_key


def test_load_private_key_without_password():
    """Test _load_private_key without a password."""
    mock_key_data = b"fake-key-data"

    with (
        patch("builtins.open", mock_open(read_data=mock_key_data)),
        patch("atonix.client.serialization.load_pem_private_key") as mock_load,
    ):
        mock_rsa_key = MagicMock(spec=rsa.RSAPrivateKey)
        mock_load.return_value = mock_rsa_key

        key = _load_private_key("fake/path", password=None)

        mock_load.assert_called_once_with(mock_key_data, password=None)
        assert key == mock_rsa_key


def test_client_init_with_password_arg():
    """Test AtonixClient initialization with explicit password argument."""
    with patch("atonix.client._load_private_key") as mock_load_key:
        mock_rsa_key = MagicMock(spec=rsa.RSAPrivateKey)
        mock_load_key.return_value = mock_rsa_key

        with patch.dict(os.environ, {"ATONIX_PRIVATE_KEY_PATH": "fake/path"}):
            client = AtonixClient(api_key="test-key", private_key_password="arg-password")

            mock_load_key.assert_called_once_with("fake/path", "arg-password")
            assert client._auth.private_key == mock_rsa_key


def test_client_init_with_password_env():
    """Test AtonixClient initialization with password from environment variable."""
    with patch("atonix.client._load_private_key") as mock_load_key:
        mock_rsa_key = MagicMock(spec=rsa.RSAPrivateKey)
        mock_load_key.return_value = mock_rsa_key

        env_vars = {"ATONIX_PRIVATE_KEY_PATH": "fake/path", "ATONIX_PRIVATE_KEY_PASSWORD": "env-password"}
        with patch.dict(os.environ, env_vars):
            client = AtonixClient(api_key="test-key")

            mock_load_key.assert_called_once_with("fake/path", "env-password")
            assert client._auth.private_key == mock_rsa_key


def test_client_init_password_precedence():
    """Test that explicit password argument takes precedence over environment variable."""
    with patch("atonix.client._load_private_key") as mock_load_key:
        mock_rsa_key = MagicMock(spec=rsa.RSAPrivateKey)
        mock_load_key.return_value = mock_rsa_key

        env_vars = {"ATONIX_PRIVATE_KEY_PATH": "fake/path", "ATONIX_PRIVATE_KEY_PASSWORD": "env-password"}
        with patch.dict(os.environ, env_vars):
            AtonixClient(api_key="test-key", private_key_password="arg-password")

            mock_load_key.assert_called_once_with("fake/path", "arg-password")
