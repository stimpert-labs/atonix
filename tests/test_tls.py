# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the TLS options (``verify`` / ``cert``) on both clients."""

import datetime
import ipaddress
import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from atonix.client import AsyncAtonixClient, AtonixClient
from atonix.exceptions import APIError

CLIENTS = [AtonixClient, AsyncAtonixClient]

# Keep the developer's proxy settings (env vars or OS) away from requests to the local test server.
NO_ENV = {"trust_env": False}


def _ssl_context_of(client) -> ssl.SSLContext:
    """The SSL context the client's transport will actually use."""
    return client._client._transport._pool._ssl_context


@pytest.fixture
def cert_files(tmp_path):
    """Write a synthetic self-signed cert and its key (plain and encrypted) to disk."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "atonix-test.invalid")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
    )
    enc_key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"test-password"),
    )

    paths = {
        "cert": tmp_path / "cert.pem",
        "key": tmp_path / "key.pem",
        "enc_key": tmp_path / "key-enc.pem",
        "combined": tmp_path / "combined.pem",
    }
    paths["cert"].write_bytes(cert_pem)
    paths["key"].write_bytes(key_pem)
    paths["enc_key"].write_bytes(enc_key_pem)
    paths["combined"].write_bytes(cert_pem + key_pem)
    return {k: str(v) for k, v in paths.items()}


def _make(cls, mock_private_key, **kwargs):
    return cls(api_key="testkey", private_key=mock_private_key, **kwargs)


@pytest.mark.parametrize("cls", CLIENTS)
class TestVerify:
    def test_default_verifies_certificates(self, cls, mock_private_key):
        client = _make(cls, mock_private_key)
        ctx = _ssl_context_of(client)
        assert client._verify is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True

    def test_verify_false_disables_verification(self, cls, mock_private_key):
        ctx = _ssl_context_of(_make(cls, mock_private_key, verify=False))
        assert ctx.verify_mode == ssl.CERT_NONE
        assert ctx.check_hostname is False

    def test_ssl_context_used_as_is(self, cls, mock_private_key):
        custom = ssl.create_default_context()
        client = _make(cls, mock_private_key, verify=custom)
        assert _ssl_context_of(client) is custom

    def test_ca_bundle_path_is_trusted(self, cls, mock_private_key, cert_files):
        ctx = _ssl_context_of(_make(cls, mock_private_key, verify=cert_files["cert"]))
        subjects = [dict(x[0] for x in ca["subject"]) for ca in ctx.get_ca_certs()]
        assert {"commonName": "atonix-test.invalid"} in subjects
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_ca_directory_path_accepted(self, cls, mock_private_key, tmp_path):
        ctx = _ssl_context_of(_make(cls, mock_private_key, verify=str(tmp_path)))
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_missing_ca_path_raises(self, cls, mock_private_key, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            _make(cls, mock_private_key, verify=str(tmp_path / "nope.pem"))

    def test_invalid_verify_type_raises(self, cls, mock_private_key):
        with pytest.raises(TypeError):
            _make(cls, mock_private_key, verify=42)


@pytest.mark.parametrize("cls", CLIENTS)
class TestClientCert:
    def test_cert_and_key_tuple(self, cls, mock_private_key, cert_files):
        client = _make(cls, mock_private_key, cert=(cert_files["cert"], cert_files["key"]))
        assert isinstance(client._verify, ssl.SSLContext)
        assert _ssl_context_of(client) is client._verify
        assert client._verify.verify_mode == ssl.CERT_REQUIRED

    def test_combined_pem(self, cls, mock_private_key, cert_files):
        client = _make(cls, mock_private_key, cert=cert_files["combined"])
        assert _ssl_context_of(client) is client._verify

    def test_encrypted_key_with_password(self, cls, mock_private_key, cert_files):
        client = _make(cls, mock_private_key, cert=(cert_files["cert"], cert_files["enc_key"], "test-password"))
        assert _ssl_context_of(client) is client._verify

    def test_encrypted_key_wrong_password_raises(self, cls, mock_private_key, cert_files):
        with pytest.raises(ssl.SSLError):
            _make(cls, mock_private_key, cert=(cert_files["cert"], cert_files["enc_key"], "wrong"))

    def test_cert_with_custom_ca_path(self, cls, mock_private_key, cert_files):
        client = _make(cls, mock_private_key, verify=cert_files["cert"], cert=cert_files["combined"])
        subjects = [dict(x[0] for x in ca["subject"]) for ca in client._verify.get_ca_certs()]
        assert {"commonName": "atonix-test.invalid"} in subjects

    def test_cert_with_verify_false_keeps_verification_off(self, cls, mock_private_key, cert_files):
        client = _make(cls, mock_private_key, verify=False, cert=cert_files["combined"])
        assert client._verify.verify_mode == ssl.CERT_NONE

    def test_cert_with_ssl_context_rejected(self, cls, mock_private_key, cert_files):
        with pytest.raises(ValueError, match="not both"):
            _make(cls, mock_private_key, verify=ssl.create_default_context(), cert=cert_files["combined"])


@pytest.fixture
def tls_server(tmp_path):
    """A local HTTPS server on 127.0.0.1 using a synthetic self-signed certificate."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "server.pem"
    key_path = tmp_path / "server-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
        )
    )

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"Success": True, "Results": []}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(cert_path, key_path)
    server.socket = server_ctx.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"https://127.0.0.1:{server.server_address[1]}", str(cert_path)
    finally:
        server.shutdown()
        server.server_close()


class TestTLSEndToEnd:
    def test_untrusted_server_rejected_by_default(self, mock_private_key, tls_server):
        url, _ = tls_server
        with (
            _make(AtonixClient, mock_private_key, environment=url, max_retries=1, httpx_kwargs=NO_ENV) as client,
            pytest.raises(APIError, match=r"(?i)certificate"),
        ):
            client.get("/v1/ping")

    def test_custom_ca_bundle_trusts_server(self, mock_private_key, tls_server):
        url, ca_path = tls_server
        with _make(
            AtonixClient, mock_private_key, environment=url, max_retries=1, httpx_kwargs=NO_ENV, verify=ca_path
        ) as client:
            assert client.get("/v1/ping")["Success"] is True

    @pytest.mark.anyio
    async def test_async_ssl_context_trusts_server(self, mock_private_key, tls_server):
        url, ca_path = tls_server
        ctx = ssl.create_default_context(cafile=ca_path)
        async with _make(
            AsyncAtonixClient, mock_private_key, environment=url, max_retries=1, httpx_kwargs=NO_ENV, verify=ctx
        ) as client:
            assert (await client.get("/v1/ping"))["Success"] is True
