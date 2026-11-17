# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the proxy, default header, and ``httpx_kwargs`` client options."""

import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
import respx
from httpx import Response

from atonix.client import AsyncAtonixClient, AtonixClient
from tests.conftest import BASE_URL, make_api_response

# A target host that is never resolved: every request to it must go through the proxy.
# Plain http (with allow_insecure) lets the local proxy read each request instead of tunnelling it.
TARGET = "http://atonix-api.invalid"

PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "no_proxy",
)


def _make(cls, mock_private_key, **kwargs):
    kwargs.setdefault("max_retries", 1)
    return cls(api_key="testkey", private_key=mock_private_key, **kwargs)


@pytest.fixture(autouse=True)
def _clean_proxy_env(monkeypatch):
    """Keep the developer's own proxy settings out of these tests."""
    for var in PROXY_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def proxy_server():
    """A local forward proxy that answers every request itself and records what it saw."""
    seen: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append({"path": self.path, "headers": dict(self.headers)})
            body = json.dumps(make_api_response([])).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", seen
    finally:
        server.shutdown()
        server.server_close()


class TestProxy:
    def test_explicit_proxy_routes_requests(self, mock_private_key, proxy_server):
        proxy_url, seen = proxy_server
        with _make(AtonixClient, mock_private_key, environment=TARGET, allow_insecure=True, proxy=proxy_url) as client:
            assert client.get("/v1/ping")["Success"] is True
        assert seen[0]["path"] == f"{TARGET}/v1/ping"
        assert "x-atx-auth" in {k.lower() for k in seen[0]["headers"]}

    @pytest.mark.anyio
    async def test_async_explicit_proxy_routes_requests(self, mock_private_key, proxy_server):
        proxy_url, seen = proxy_server
        async with _make(
            AsyncAtonixClient, mock_private_key, environment=TARGET, allow_insecure=True, proxy=proxy_url
        ) as client:
            assert (await client.get("/v1/ping"))["Success"] is True
        assert seen[0]["path"] == f"{TARGET}/v1/ping"

    def test_httpx_proxy_object_accepted(self, mock_private_key, proxy_server):
        proxy_url, seen = proxy_server
        with _make(
            AtonixClient, mock_private_key, environment=TARGET, allow_insecure=True, proxy=httpx.Proxy(proxy_url)
        ) as client:
            client.get("/v1/ping")
        assert len(seen) == 1

    def test_environment_proxy_is_honored(self, mock_private_key, proxy_server, monkeypatch):
        proxy_url, seen = proxy_server
        monkeypatch.setenv("HTTP_PROXY", proxy_url)
        with _make(AtonixClient, mock_private_key, environment=TARGET, allow_insecure=True) as client:
            assert client.get("/v1/ping")["Success"] is True
        assert seen[0]["path"] == f"{TARGET}/v1/ping"

    def test_no_proxy_bypasses_environment_proxy(self, mock_private_key, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
        monkeypatch.setenv("NO_PROXY", "api-us.pgapm.io")
        client = _make(AtonixClient, mock_private_key)
        assert client._client._transport_for_url(httpx.URL(f"{BASE_URL}/v1/assets")) is client._client._transport

    def test_trust_env_false_ignores_environment_proxy(self, mock_private_key, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
        client = _make(AtonixClient, mock_private_key, httpx_kwargs={"trust_env": False})
        assert client._client._mounts == {}

    def test_proxy_transport_uses_custom_tls_settings(self, mock_private_key):
        """A CA or SSLContext must also apply to the tunnel through the proxy."""
        ctx = ssl.create_default_context()
        client = _make(AtonixClient, mock_private_key, verify=ctx, proxy="http://127.0.0.1:9")
        proxy_transport = client._client._transport_for_url(httpx.URL(f"{BASE_URL}/v1/assets"))
        assert proxy_transport is not client._client._transport
        assert proxy_transport._pool._ssl_context is ctx


@pytest.mark.parametrize("cls", [AtonixClient, AsyncAtonixClient])
class TestHeaders:
    def test_default_headers_set_on_client(self, cls, mock_private_key):
        client = _make(cls, mock_private_key, headers={"User-Agent": "my-app/1.0", "X-Team": "reliability"})
        assert client._client.headers["User-Agent"] == "my-app/1.0"
        assert client._client.headers["X-Team"] == "reliability"


class TestHeadersOnTheWire:
    @respx.mock
    def test_default_headers_sent_with_auth(self, mock_private_key):
        route = respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))
        with _make(AtonixClient, mock_private_key, headers={"User-Agent": "my-app/1.0"}) as client:
            client.get("/v1/assets")
        sent = route.calls.last.request.headers
        assert sent["User-Agent"] == "my-app/1.0"
        assert sent["x-api-key"] == "testkey"
        assert sent["x-atx-auth"].startswith("testkey:")

    @respx.mock
    def test_default_headers_cannot_replace_auth(self, mock_private_key):
        route = respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))
        with _make(AtonixClient, mock_private_key, headers={"X-Api-Key": "spoofed", "X-ATX-Auth": "spoofed"}) as client:
            client.get("/v1/assets")
        sent = route.calls.last.request.headers
        assert sent["x-api-key"] == "testkey"
        assert sent["x-atx-auth"] != "spoofed"

    @respx.mock
    def test_per_request_headers_override_defaults(self, mock_private_key):
        route = respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))
        with _make(AtonixClient, mock_private_key, headers={"X-Trace": "default"}) as client:
            client.get("/v1/assets", headers={"X-Trace": "per-request"})
        assert route.calls.last.request.headers["X-Trace"] == "per-request"


class TestHttpxKwargs:
    def test_custom_transport_receives_signed_requests(self, mock_private_key):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=make_api_response([]))

        transport = httpx.MockTransport(handler)
        with _make(AtonixClient, mock_private_key, httpx_kwargs={"transport": transport}) as client:
            assert client.get("/v1/assets")["Success"] is True
        assert "x-atx-auth" in seen[0].headers

    @pytest.mark.anyio
    async def test_async_event_hooks_called(self, mock_private_key):
        urls: list[str] = []

        async def log_request(request: httpx.Request) -> None:
            urls.append(str(request.url))

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=make_api_response([]))

        kwargs = {"transport": httpx.MockTransport(handler), "event_hooks": {"request": [log_request]}}
        async with _make(AsyncAtonixClient, mock_private_key, httpx_kwargs=kwargs) as client:
            await client.get("/v1/assets")
        assert urls == [f"{BASE_URL}/v1/assets"]

    def test_limits_forwarded(self, mock_private_key):
        limits = httpx.Limits(max_connections=7)
        client = _make(AtonixClient, mock_private_key, httpx_kwargs={"limits": limits})
        assert client._client._transport._pool._max_connections == 7

    @pytest.mark.parametrize("key", ["timeout", "verify", "cert", "proxy", "headers"])
    def test_named_arguments_rejected_in_httpx_kwargs(self, mock_private_key, key):
        with pytest.raises(ValueError, match=key):
            _make(AtonixClient, mock_private_key, httpx_kwargs={key: None})

    def test_httpx_kwargs_not_mutated(self, mock_private_key):
        kwargs = {"follow_redirects": True}
        _make(AtonixClient, mock_private_key, httpx_kwargs=kwargs)
        assert kwargs == {"follow_redirects": True}
