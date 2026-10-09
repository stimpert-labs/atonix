# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the AtonixClient and Auth classes."""

import json
from base64 import b64decode

import httpx
import pytest
import respx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from httpx import Response

from atonix.client import AsyncAtonixClient, AtonixClient, Auth, _parse_private_key
from atonix.exceptions import (
    APIError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)
from tests.conftest import BASE_URL, make_api_response, make_asset


class TestAuth:
    """Tests for the Auth class."""

    def test_init_normalizes_api_key(self, mock_private_key):
        """API key should be normalized (lowercase, no dashes)."""
        auth = Auth(api_key="AB-CD-EF-12", private_key=mock_private_key)
        assert auth.api_key == "abcdef12"

    def test_get_auth_headers_returns_required_headers(self, mock_private_key):
        """Auth headers should include x-api-key and x-atx-auth."""
        auth = Auth(api_key="testkey", private_key=mock_private_key)

        headers = auth.get_auth_headers("/v1/assets", "GET")

        assert "x-api-key" in headers
        assert "x-atx-auth" in headers
        assert headers["x-api-key"] == "testkey"

    def test_get_auth_headers_includes_timestamp(self, mock_private_key):
        """x-atx-auth header should contain a timestamp."""
        auth = Auth(api_key="testkey", private_key=mock_private_key)

        headers = auth.get_auth_headers("/v1/assets", "GET")

        # x-atx-auth format: "api_key:timestamp:signature"
        auth_header = headers["x-atx-auth"]
        parts = auth_header.split(":")
        assert len(parts) == 3
        # Second part should be a valid integer timestamp
        timestamp_str = parts[1]
        assert timestamp_str.isdigit()


class TestAtonixClient:
    """Tests for the AtonixClient class."""

    def test_init_sets_defaults(self, mock_private_key):
        """Client should initialize with default settings."""
        client = AtonixClient(api_key="testkey", private_key=mock_private_key)

        assert client._base_url == "https://api-us.pgapm.io"
        # Resources should be initialized
        assert hasattr(client, "assets")
        assert hasattr(client, "issues")
        assert hasattr(client, "models")
        assert hasattr(client, "process_data")

    @respx.mock
    def test_get_success(self, mock_client):
        """Successful GET request should return parsed response."""
        response_data = make_api_response([make_asset()], type_name="Asset")
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=response_data))

        result = mock_client.get("/v1/assets")

        assert result["Success"] is True
        assert len(result["Results"]) == 1

    @respx.mock
    def test_post_success(self, mock_client):
        """Successful POST request should return parsed response."""
        response_data = make_api_response([{"Id": "new-id"}], type_name="Issue")
        respx.post(f"{BASE_URL}/v1/issues").mock(return_value=Response(200, json=response_data))

        result = mock_client.post("/v1/issues", json={"Title": "Test"})

        assert result["Success"] is True

    @respx.mock
    def test_handles_401_authentication_error(self, mock_client):
        """401 response should raise AuthenticationError."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(401, json={"Success": False, "StatusCode": 401}))

        with pytest.raises(AuthenticationError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_handles_404_not_found_error(self, mock_client):
        """404 response should raise NotFoundError."""
        respx.get(f"{BASE_URL}/v1/assets/nonexistent").mock(return_value=Response(404, json={"Success": False}))

        with pytest.raises(NotFoundError):
            mock_client.get("/v1/assets/nonexistent")

    @respx.mock
    def test_handles_429_rate_limit_error(self, mock_client):
        """429 response should raise RateLimitError after retries."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(429, json={"Success": False}))

        with pytest.raises(RateLimitError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_retries_on_transient_error(self, mock_private_key):
        """Client should retry on 500 errors."""
        route = respx.get(f"{BASE_URL}/v1/assets")
        route.side_effect = [
            Response(500, json={"Success": False}),
            Response(200, json=make_api_response([make_asset()])),
        ]

        client = AtonixClient(api_key="testkey", private_key=mock_private_key, max_retries=2, timeout=5)

        result = client.get("/v1/assets")

        assert result["Success"] is True
        assert route.call_count == 2
        assert len(respx.calls) == 2

    @respx.mock
    def test_init_loads_private_key_from_env_var(self, monkeypatch, mock_private_key):
        """Client should load private key from ATONIX_PRIVATE_KEY env var."""
        key_bytes = mock_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        monkeypatch.setenv("ATONIX_API_KEY", "testkey")
        monkeypatch.setenv("ATONIX_PRIVATE_KEY", key_bytes.decode("utf-8"))

        client = AtonixClient()
        assert client._auth.api_key == "testkey"
        assert isinstance(client._auth.private_key, rsa.RSAPrivateKey)

    @respx.mock
    def test_init_handles_escaped_newlines_in_env_var(self, monkeypatch, mock_private_key):
        """Client should handle literal \\n characters in ATONIX_PRIVATE_KEY env var."""
        key_bytes = mock_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Replace actual newlines with literal \n
        escaped_key = key_bytes.decode("utf-8").replace("\n", "\\n")

        monkeypatch.setenv("ATONIX_API_KEY", "testkey")
        monkeypatch.setenv("ATONIX_PRIVATE_KEY", escaped_key)

        # This should succeed if we unescape the newlines
        client = AtonixClient()
        assert isinstance(client._auth.private_key, rsa.RSAPrivateKey)

    @respx.mock
    def test_init_prioritizes_private_key_content_over_path(self, monkeypatch, mock_private_key):
        """ATONIX_PRIVATE_KEY should take precedence over ATONIX_PRIVATE_KEY_PATH."""
        key_bytes = mock_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        monkeypatch.setenv("ATONIX_API_KEY", "testkey")
        monkeypatch.setenv("ATONIX_PRIVATE_KEY", key_bytes.decode("utf-8"))
        monkeypatch.setenv("ATONIX_PRIVATE_KEY_PATH", "nonexistent_path")

        # This should NOT raise FileNotFound because it uses the content
        client = AtonixClient()
        assert isinstance(client._auth.private_key, rsa.RSAPrivateKey)

    def test_init_raises_error_if_no_key_found(self, monkeypatch):
        """Client should raise ValueError if no private key is provided via any method."""
        monkeypatch.setenv("ATONIX_API_KEY", "testkey")
        monkeypatch.delenv("ATONIX_PRIVATE_KEY", raising=False)
        monkeypatch.delenv("ATONIX_PRIVATE_KEY_PATH", raising=False)

        with pytest.raises(
            ValueError, match=r"ATONIX_PRIVATE_KEY \(contents\) or ATONIX_PRIVATE_KEY_PATH \(file path\)"
        ):
            AtonixClient()

    @respx.mock
    def test_includes_query_params(self, mock_client):
        """GET request should include query parameters."""
        route = respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))

        mock_client.get("/v1/assets", params={"skip": 0, "take": 50})

        assert route.calls.last.request.url.params["skip"] == "0"
        assert route.calls.last.request.url.params["take"] == "50"

    def test_init_raises_if_no_api_key(self, monkeypatch, mock_private_key):
        """Client should raise ValueError when no API key is provided."""
        monkeypatch.delenv("ATONIX_API_KEY", raising=False)

        with pytest.raises(ValueError, match="ATONIX_API_KEY"):
            AtonixClient(private_key=mock_private_key)

    def test_init_with_custom_url_string(self, mock_private_key):
        """Client should accept a custom URL string as environment."""
        client = AtonixClient(
            api_key="testkey", private_key=mock_private_key, environment="https://custom.example.com/"
        )
        assert client._base_url == "https://custom.example.com"

    @pytest.mark.parametrize("url", ["http://custom.example.com", "HTTP://custom.example.com"])
    def test_init_rejects_http_url(self, mock_private_key, url):
        """Client should refuse a plaintext http:// environment by default."""
        with pytest.raises(ValueError, match="allow_insecure"):
            AtonixClient(api_key="testkey", private_key=mock_private_key, environment=url)

    @pytest.mark.parametrize("url", ["custom.example.com", "ftp://custom.example.com", "https://", ""])
    def test_init_rejects_malformed_url(self, mock_private_key, url):
        """Client should reject URLs without an https scheme and host."""
        with pytest.raises(ValueError, match="Invalid environment URL"):
            AtonixClient(api_key="testkey", private_key=mock_private_key, environment=url, allow_insecure=True)

    def test_init_allows_http_with_opt_in(self, mock_private_key, caplog):
        """allow_insecure=True should permit http:// and log a warning."""
        client = AtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            environment="http://localhost:8080/",
            allow_insecure=True,
        )
        assert client._base_url == "http://localhost:8080"
        assert "insecure" in caplog.text

    def test_async_init_rejects_http_url(self, mock_private_key):
        """AsyncAtonixClient should apply the same HTTPS check."""
        with pytest.raises(ValueError, match="allow_insecure"):
            AsyncAtonixClient(api_key="testkey", private_key=mock_private_key, environment="http://custom.example.com")

    def test_init_raises_if_non_rsa_key(self, mock_private_key):
        """_parse_private_key should raise ValueError for non-RSA keys."""
        ec_key = ec.generate_private_key(ec.SECP256R1())
        ec_pem = ec_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with pytest.raises(ValueError, match="not an RSA private key"):
            _parse_private_key(ec_pem)

    @respx.mock
    def test_context_manager(self, mock_private_key):
        """AtonixClient should work as a context manager."""
        with AtonixClient(api_key="testkey", private_key=mock_private_key) as client:
            respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))
            result = client.get("/v1/assets")
        assert result["Success"] is True

    @respx.mock
    def test_custom_headers_are_sent(self, mock_client):
        """request() should merge custom headers into the request."""
        route = respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))

        mock_client.get("/v1/assets", headers={"X-Custom-Header": "test-value"})

        assert route.calls.last.request.headers["X-Custom-Header"] == "test-value"

    @respx.mock
    def test_put_method(self, mock_client):
        """PUT request should succeed and return parsed response."""
        respx.put(f"{BASE_URL}/v1/assets/1").mock(return_value=Response(200, json=make_api_response([])))

        result = mock_client.put("/v1/assets/1", json={"Name": "Updated"})

        assert result["Success"] is True

    @respx.mock
    def test_patch_method(self, mock_client):
        """PATCH request should succeed and return parsed response."""
        respx.patch(f"{BASE_URL}/v1/assets/1").mock(return_value=Response(200, json=make_api_response([])))

        result = mock_client.patch("/v1/assets/1", json={"Name": "Patched"})

        assert result["Success"] is True

    @respx.mock
    def test_http_200_success_false_raises_auth_error(self, mock_client):
        """HTTP 200 with Success=False and Code=401 should raise AuthenticationError."""
        body = {
            "Success": False,
            "StatusCode": 200,
            "Results": [{"Code": "401", "Message": "Invalid token"}],
        }
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=body))

        with pytest.raises(AuthenticationError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_http_200_success_false_raises_permission_error(self, mock_client):
        """HTTP 200 with Success=False and Code=403 should raise PermissionDeniedError."""
        body = {
            "Success": False,
            "StatusCode": 200,
            "Results": [{"Code": "403", "Message": "Forbidden"}],
        }
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=body))

        with pytest.raises(PermissionDeniedError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_http_200_success_false_raises_not_found(self, mock_client):
        """HTTP 200 with Success=False and Code=404 should raise NotFoundError."""
        body = {
            "Success": False,
            "StatusCode": 200,
            "Results": [{"Code": "404", "Message": "Not found"}],
        }
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=body))

        with pytest.raises(NotFoundError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_http_200_success_false_no_results_raises_api_error(self, mock_client):
        """HTTP 200 with Success=False and no Results should raise APIError."""
        body = {"Success": False, "StatusCode": 200, "Results": []}
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=body))

        with pytest.raises(APIError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_non_2xx_with_message_in_body(self, mock_client):
        """Non-2xx response with Results body should extract message."""
        body = {
            "Success": False,
            "Results": [{"Code": 401, "Message": "Unauthorized"}],
        }
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(401, json=body))

        with pytest.raises(AuthenticationError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_non_2xx_non_json_body(self, mock_client):
        """Non-2xx response with non-JSON body should still raise appropriate error."""
        respx.get(f"{BASE_URL}/v1/assets").mock(
            return_value=Response(404, content=b"Not Found", headers={"content-type": "text/plain"})
        )

        with pytest.raises(NotFoundError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_5xx_raises_server_error(self, mock_private_key):
        """5xx response after all retries should raise ServerError."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(500, json={"Success": False}))

        client = AtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=1,
        )
        with pytest.raises(ServerError):
            client.get("/v1/assets")

    @respx.mock
    def test_400_raises_api_error(self, mock_client):
        """400 response should raise APIError (not mapped to a specific exception)."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(400, json={"Success": False}))

        with pytest.raises(APIError):
            mock_client.get("/v1/assets")

    @respx.mock
    def test_request_error_raises_api_error(self, mock_private_key):
        """httpx.RequestError on last attempt should raise APIError."""
        respx.get(f"{BASE_URL}/v1/assets").mock(side_effect=httpx.ConnectError("Connection refused"))

        client = AtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=1,
        )
        with pytest.raises(APIError, match="Network error"):
            client.get("/v1/assets")

    @respx.mock
    def test_request_error_retries_then_succeeds(self, monkeypatch, mock_private_key):
        """httpx.RequestError on first attempt should retry and succeed."""
        import time

        monkeypatch.setattr(time, "sleep", lambda _: None)

        route = respx.get(f"{BASE_URL}/v1/assets")
        route.side_effect = [
            httpx.ConnectError("Connection refused"),
            Response(200, json=make_api_response([make_asset()])),
        ]

        client = AtonixClient(
            api_key="testkey",
            private_key=mock_private_key,
            max_retries=2,
        )
        result = client.get("/v1/assets")

        assert result["Success"] is True
        assert route.call_count == 2

    @respx.mock
    def test_list_param_values_in_auth_signing(self, mock_client):
        """Auth signing should handle list-valued query parameters."""
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))

        # List values in params trigger the sorted-join branch in _represent_request
        result = mock_client.get("/v1/assets", params={"ids": ["b", "a", "c"]})

        assert result["Success"] is True


class TestAPIError:
    """Tests for the APIError exception class."""

    def test_api_error_str_with_status_code(self):
        """APIError.__str__ should include status code when present."""
        err = APIError("Something failed", status_code=422, response_content="body")
        assert "422" in str(err)
        assert "Something failed" in str(err)
        assert err.status_code == 422
        assert err.response_content == "body"

    def test_api_error_str_without_status_code(self):
        """APIError.__str__ should return plain message when no status code."""
        err = APIError("Network timeout")
        assert str(err) == "Network timeout"
        assert err.status_code is None
        assert err.response_content is None


class TestClockSkewHint:
    """Tests for the clock-skew hint appended to AuthenticationError on 401."""

    @respx.mock
    def test_http_401_skew_keyword_includes_hint(self, mock_client):
        """A 401 with a skew-related Message should include the clock-sync hint."""
        body = {
            "Success": False,
            "Results": [{"Code": 401, "Message": "Request timestamp expired"}],
        }
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(401, json=body))

        with pytest.raises(AuthenticationError) as exc_info:
            mock_client.get("/v1/assets")

        assert "system clock" in str(exc_info.value).lower()
        assert "ntp" in str(exc_info.value).lower()

    @respx.mock
    def test_http_401_mismatched_date_header_includes_hint(self, mock_client):
        """A 401 whose Date header is far from local time should include the hint."""
        body = {
            "Success": False,
            "Results": [{"Code": 401, "Message": "Unauthorized"}],
        }
        # Date far in the past — well beyond the 60s threshold.
        respx.get(f"{BASE_URL}/v1/assets").mock(
            return_value=Response(
                401,
                json=body,
                headers={"Date": "Mon, 01 Jan 2001 00:00:00 GMT"},
            )
        )

        with pytest.raises(AuthenticationError) as exc_info:
            mock_client.get("/v1/assets")

        assert "system clock" in str(exc_info.value).lower()

    @respx.mock
    def test_http_401_plain_message_no_hint(self, mock_client, monkeypatch):
        """A plain 401 with no skew indicators should NOT include the hint."""
        body = {
            "Success": False,
            "Results": [{"Code": 401, "Message": "Invalid API key"}],
        }
        # Pin time so the Date header and the skew check use the same value,
        # making this test deterministic regardless of the host clock.
        from email.utils import formatdate

        fixed_now = 1_700_000_000.0
        monkeypatch.setattr("atonix.client.time.time", lambda: fixed_now)
        respx.get(f"{BASE_URL}/v1/assets").mock(
            return_value=Response(
                401,
                json=body,
                headers={"Date": formatdate(timeval=fixed_now, usegmt=True)},
            )
        )

        with pytest.raises(AuthenticationError) as exc_info:
            mock_client.get("/v1/assets")

        assert "system clock" not in str(exc_info.value).lower()

    @respx.mock
    def test_http_200_success_false_skew_keyword_includes_hint(self, mock_client):
        """A 200/Success=False with Code=401 and skew message should include the hint."""
        body = {
            "Success": False,
            "StatusCode": 200,
            "Results": [{"Code": "401", "Message": "Invalid signature - clock skew"}],
        }
        respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=body))

        with pytest.raises(AuthenticationError) as exc_info:
            mock_client.get("/v1/assets")

        assert "system clock" in str(exc_info.value).lower()


def _dotnet_ascii(text: str) -> bytes:
    """Model of .NET ``Encoding.ASCII.GetBytes``: every non-ASCII UTF-16 code unit becomes ``?``."""
    units = memoryview(text.encode("utf-16-le")).cast("H")
    return bytes(u if u < 0x80 else 0x3F for u in units)


def _verify_wire_signature(request: httpx.Request, private_key: rsa.RSAPrivateKey, api_key: str) -> None:
    """Rebuild the challenge string from what is actually on the wire and verify the signature.

    Mirrors the server per the Atonix auth spec: it only sees the wire request, builds the
    challenge from it, and verifies over ``Encoding.ASCII.GetBytes(challenge)``.
    """
    _key, timestamp, signature = request.headers["x-atx-auth"].split(":")
    params: dict = {}
    for k, v in request.url.params.multi_items():
        params.setdefault(k, []).append(v)
    params = {k: v[0] if len(v) == 1 else v for k, v in params.items()}
    representation = Auth(api_key, private_key)._represent_request(
        int(timestamp),
        request.url.path,
        request.method,
        params,
        request.content or None,
    )
    private_key.public_key().verify(
        b64decode(signature), _dotnet_ascii(representation), padding.PKCS1v15(), hashes.SHA256()
    )


class TestRequestSigning:
    """Signed bytes must match wire bytes and survive non-ASCII input (#12, #13)."""

    API_KEY = "test-api-key-1234567890abcdef"

    def test_sign_accepts_non_ascii_representation(self, mock_private_key):
        """_sign must not raise UnicodeEncodeError on non-ASCII input (#12)."""
        auth = Auth(self.API_KEY, mock_private_key)

        headers = auth.get_auth_headers("/v1/assets", "GET", params={"name": "Kühler Ø-Pumpe 温度"})

        assert headers["x-atx-auth"].count(":") == 2

    def test_challenge_encoding_matches_dotnet_ascii(self):
        """Non-ASCII chars become '?' per UTF-16 code unit, like .NET Encoding.ASCII (#12)."""
        from atonix.client import _encode_challenge

        assert _encode_challenge("plain") == b"plain"
        assert _encode_challenge("Kühler") == b"K?hler"
        assert _encode_challenge("温度") == b"??"
        assert _encode_challenge("a😀b") == b"a??b"  # surrogate pair -> two code units
        for text in ("Kühler Ø-Pumpe 温度", "😀x€"):
            assert _encode_challenge(text) == _dotnet_ascii(text)

    def test_challenge_string_matches_auth_spec_example(self, mock_private_key):
        """Challenge format follows the auth spec's worked example (sorted keys, merged duplicates)."""
        auth = Auth("00000000-aaaa-bbbb-cccc-000000000001", mock_private_key)
        body = b'{"JsonKey":"JsonValue","ABCD":"Json body text is not alphabetized"}'

        rep = auth._represent_request(
            1546300800000, "/rest/echo/authenticate", "PUT", {"value": ["2", "1"], "data": "xyz"}, body
        )

        assert rep == (
            "00000000aaaabbbbcccc000000000001\n1546300800000\n/rest/echo/authenticate\nput\n"
            "data:xyz\nvalue:12\n"
            '{"JsonKey":"JsonValue","ABCD":"Json body text is not alphabetized"}'
        )

    @pytest.mark.skipif(
        tuple(int(x) for x in httpx.__version__.split(".")[:2]) < (0, 28),
        reason="httpx < 0.28 used non-compact JSON for json=",
    )
    def test_body_bytes_identical_to_httpx_json_encoding(self):
        """The wire body is byte-for-byte what httpx sends for json= (no change for existing callers)."""
        from atonix.client import _encode_json_body

        body = {"Title": "Température - 温度", "Values": [1, 2.5, None, True], "Nested": {"z": 1, "a": "x"}}

        assert _encode_json_body(body) == httpx.Request("POST", BASE_URL, json=body).content

    def test_ascii_representation_unchanged(self, mock_private_key):
        """For ASCII input the canonical string is identical to the pre-fix format."""
        auth = Auth(self.API_KEY, mock_private_key)
        body = {"ServerId": "s1", "TagIds": ["t1", "t2"], "Nested": {"b": 1, "a": None}}

        rep = auth._represent_request(123, "/v1/ProcessData/Query", "POST", {"take": 50}, b'{"x":1}')

        assert rep == 'testapikey1234567890abcdef\n123\n/v1/processdata/query\npost\ntake:50\n{"x":1}'
        # The serialized body equals the compact json.dumps the signer used before the fix.
        from atonix.client import _encode_json_body

        assert _encode_json_body(body) == json.dumps(body, separators=(",", ":")).encode()

    @respx.mock
    def test_post_signature_verifies_against_wire_body(self, mock_client, mock_private_key):
        """The server-side check (signature over the wire bytes) must pass for a JSON body (#13)."""
        route = respx.post(f"{BASE_URL}/v1/issues").mock(return_value=Response(200, json=make_api_response([])))
        body = {"Title": "Pump vibration", "Priority": 2, "Tags": ["b", "a"], "Meta": {"z": 1, "a": [1.5, None]}}

        mock_client.post("/v1/issues", json=body)

        request = route.calls.last.request
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.content) == body
        _verify_wire_signature(request, mock_private_key, self.API_KEY)

    @respx.mock
    def test_non_ascii_body_signature_verifies_against_wire_body(self, mock_client, mock_private_key):
        """Non-ASCII bodies are sent as raw UTF-8 and signed the way the server encodes them (#12, #13)."""
        route = respx.post(f"{BASE_URL}/v1/issues").mock(return_value=Response(200, json=make_api_response([])))
        body = {"Title": "Température élevée - 温度", "Summary": "Ω 😀"}

        mock_client.post("/v1/issues", json=body)

        request = route.calls.last.request
        assert request.content == json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        assert json.loads(request.content) == body
        _verify_wire_signature(request, mock_private_key, self.API_KEY)

    @respx.mock
    def test_non_ascii_query_param_signature_verifies(self, mock_client, mock_private_key):
        """GET with non-ASCII query values is signed (server-style ASCII) instead of raising (#12)."""
        route = respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(200, json=make_api_response([])))

        mock_client.get("/v1/assets", params={"name": "Kühler"})

        request = route.calls.last.request
        assert "Content-Type" not in request.headers
        _verify_wire_signature(request, mock_private_key, self.API_KEY)

    @respx.mock
    def test_delete_with_list_body_signature_verifies(self, mock_client, mock_private_key):
        """A JSON list body on DELETE is signed and sent as the same bytes."""
        route = respx.delete(f"{BASE_URL}/v1/issues/abc/keywords").mock(
            return_value=Response(200, json=make_api_response([]))
        )

        mock_client.delete("/v1/issues/abc/keywords", json=["k1", "k2"])

        request = route.calls.last.request
        assert request.content == b'["k1","k2"]'
        _verify_wire_signature(request, mock_private_key, self.API_KEY)

    @respx.mock
    def test_custom_content_type_header_wins(self, mock_client):
        """A caller-supplied Content-Type still overrides the default."""
        route = respx.post(f"{BASE_URL}/v1/issues").mock(return_value=Response(200, json=make_api_response([])))

        mock_client.post("/v1/issues", json={"a": 1}, headers={"Content-Type": "application/json; charset=utf-8"})

        assert route.calls.last.request.headers["Content-Type"] == "application/json; charset=utf-8"

    def test_nan_body_rejected(self, mock_client):
        """NaN is not valid JSON; it is rejected before sending, as httpx did before."""
        with pytest.raises(ValueError):
            mock_client.post("/v1/issues", json={"v": float("nan")})


class TestMaxRetries:
    """Every request is attempted at least once regardless of max_retries (#15)."""

    @respx.mock
    def test_max_retries_zero_still_sends_request(self, mock_private_key):
        route = respx.get(f"{BASE_URL}/v1/assets").mock(
            return_value=Response(200, json=make_api_response([make_asset()]))
        )
        client = AtonixClient(api_key="testkey", private_key=mock_private_key, max_retries=0)

        result = client.get("/v1/assets")

        assert result is not None
        assert result["Success"] is True
        assert route.call_count == 1

    @respx.mock
    def test_max_retries_zero_raises_without_retrying(self, mock_private_key):
        route = respx.get(f"{BASE_URL}/v1/assets").mock(return_value=Response(500, json={"Success": False}))
        client = AtonixClient(api_key="testkey", private_key=mock_private_key, max_retries=0)

        with pytest.raises(ServerError):
            client.get("/v1/assets")
        assert route.call_count == 1

    @respx.mock
    def test_max_retries_zero_network_error_raises(self, mock_private_key):
        respx.get(f"{BASE_URL}/v1/assets").mock(side_effect=httpx.ConnectError("refused"))
        client = AtonixClient(api_key="testkey", private_key=mock_private_key, max_retries=0)

        with pytest.raises(APIError, match="Network error"):
            client.get("/v1/assets")

    def test_negative_max_retries_rejected(self, mock_private_key):
        with pytest.raises(ValueError, match="max_retries"):
            AtonixClient(api_key="testkey", private_key=mock_private_key, max_retries=-1)
