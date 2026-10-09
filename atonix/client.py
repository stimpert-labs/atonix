# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from base64 import b64encode
from datetime import timezone
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from atonix.assets import Assets, AsyncAssets
from atonix.exceptions import (
    APIError,
    AtonixError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)
from atonix.issues import AsyncIssues, Issues
from atonix.models import AsyncModels, Models
from atonix.processdata import AsyncProcessData, ProcessData


class AtonixEnvironment(str, Enum):
    """Available Atonix API environments."""

    US = "https://api-us.pgapm.io"
    INDIA = "https://api-in.pgapm.io"


logger = logging.getLogger(__name__)


_CLOCK_SKEW_KEYWORDS = (
    "timestamp",
    "expired",
    "stale",
    "skew",
    "clock",
    "signature",
    "time window",
    "out of date",
)

_CLOCK_SKEW_THRESHOLD_SECONDS = 60.0

_CLOCK_SKEW_HINT = (
    " Hint: Atonix request signatures embed a millisecond timestamp and the server "
    "rejects requests whose clock is too far from server time. Verify the system "
    "clock is synchronized via NTP (UTC) and retry."
)


def _clock_skew_hint(message: str, response: httpx.Response | None) -> str:
    """Return a clock-sync hint string when a 401 looks skew-related, else "".

    Detection is intentionally heuristic so it works without assuming the server
    surfaces a dedicated clock-skew error code:

    * The error message contains any of the ``_CLOCK_SKEW_KEYWORDS``, or
    * The response ``Date`` header differs from local time by more than
      ``_CLOCK_SKEW_THRESHOLD_SECONDS``.
    """
    lowered = (message or "").lower()
    if any(kw in lowered for kw in _CLOCK_SKEW_KEYWORDS):
        return _CLOCK_SKEW_HINT

    if response is not None:
        date_header = response.headers.get("Date")
        if date_header:
            try:
                server_time = parsedate_to_datetime(date_header)
            except (TypeError, ValueError):
                server_time = None
            if server_time is not None:
                if server_time.tzinfo is None or server_time.tzinfo.utcoffset(server_time) is None:
                    server_time = server_time.replace(tzinfo=timezone.utc)
                server_ts = server_time.timestamp()
                if abs(time.time() - server_ts) > _CLOCK_SKEW_THRESHOLD_SECONDS:
                    return _CLOCK_SKEW_HINT

    return ""


class Auth:
    """Internal class to handle Atonix API Authentication signature generation.

    Each request is signed with the user's RSA private key over a canonical
    string that includes a millisecond timestamp (see the ``get_auth_headers``
    method below).
    The Atonix server rejects requests whose timestamp is too far from server
    time, so the host running this client **must keep its system clock
    synchronized with UTC** (e.g. via NTP). A skewed clock typically presents
    as a 401 ``AuthenticationError``.
    """

    def __init__(self, api_key: str, private_key: rsa.RSAPrivateKey):
        """
        Initialize Authentication handler.

        Args:
            api_key: The user's Atonix API Key.
            private_key: The RSA Private Key for signing requests.
        """
        self.api_key = api_key.replace("-", "").lower()
        self.private_key = private_key

    def _represent_request(
        self,
        timestamp: int,
        resource: str,
        method: str,
        params: dict | None = None,
        body: Any | None = None,
    ) -> str:
        """
        Creates the canonical string representation of the request for signing.

        Args:
            timestamp: Millisecond timestamp.
            resource: API path.
            method: HTTP method.
            params: Query parameters.
            body: JSON request body.

        Returns:
            The canonical representation string.
        """
        parts = [
            self.api_key,
            str(timestamp),
            resource.lower(),
            method.lower(),
        ]

        if params:
            query_parts = []
            for key in sorted(params.keys()):
                value = params[key]
                val_str = "".join(sorted([str(v) for v in value])) if isinstance(value, list) else str(value)
                query_parts.append(f"{key}:{val_str}")

            if query_parts:
                parts.append("\n".join(query_parts))

        if body is not None:
            body_json = json.dumps(body, separators=(",", ":"))
            parts.append(body_json)

        return "\n".join(parts)

    def _sign(self, representation: str) -> str:
        """Signs the request representation using the private key."""
        signature = self.private_key.sign(
            representation.encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return b64encode(signature).decode("ascii")

    def get_auth_headers(
        self,
        resource: str,
        method: str,
        params: dict | None = None,
        body: Any | None = None,
    ) -> dict[str, str]:
        """
        Generates the x-atx-auth and x-api-key headers.

        The ``x-atx-auth`` header has the form ``api_key:timestamp:signature``
        where ``timestamp`` is the current time in **milliseconds since the
        Unix epoch (UTC)**. The Atonix server validates the timestamp is
        within an allowed skew window, so the host clock must be synchronized
        (e.g. via NTP). Significant clock drift will cause requests to be
        rejected with a 401 ``AuthenticationError``.

        Args:
            resource: API path.
            method: HTTP method.
            params: Query parameters.
            body: JSON request body.

        Returns:
            Dictionary containing auth headers.
        """
        timestamp = round(time.time() * 1000)
        representation = self._represent_request(timestamp, resource, method, params, body)
        signature = self._sign(representation)

        auth_string = f"{self.api_key}:{timestamp}:{signature}"

        return {
            "x-atx-auth": auth_string,
            "x-api-key": self.api_key,
        }


def _parse_private_key(data: bytes, password: str | None = None) -> rsa.RSAPrivateKey:
    """Helper to parse RSA private key from PEM bytes.

    Args:
        data: PEM-encoded private key data.
        password: Optional password to decrypt the private key.

    Returns:
        The loaded RSA private key.
    """
    key_password = password.encode() if password else None
    key = serialization.load_pem_private_key(
        data,
        password=key_password,
    )
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("Provided key is not an RSA private key")
    return key


def _load_private_key(path: str, password: str | None = None) -> rsa.RSAPrivateKey:
    """Helper to load RSA private key from file.

    Args:
        path: Path to the private key file.
        password: Optional password to decrypt the private key.

    Returns:
        The loaded RSA private key.
    """
    with open(path, "rb") as key_file:
        return _parse_private_key(key_file.read(), password)


def _validate_base_url(base_url: str, allow_insecure: bool) -> None:
    """Reject base URLs that would send signed requests over plaintext HTTP.

    Raises:
        ValueError: If the URL has no host, or uses a scheme other than ``https``
            (``http`` is accepted only when ``allow_insecure`` is True).
    """
    parts = urlsplit(base_url)
    scheme = parts.scheme.lower()
    if scheme not in ("https", "http") or not parts.netloc:
        raise ValueError(f"Invalid environment URL {base_url!r}: expected an absolute https:// URL.")
    if scheme == "http":
        if not allow_insecure:
            raise ValueError(
                f"Refusing insecure environment URL {base_url!r}: credentials and signed requests "
                "would be sent in plaintext. Use https://, or pass allow_insecure=True to override."
            )
        logger.warning("Using insecure environment URL %s; requests will not be encrypted.", base_url)


class _BaseAtonixClient:
    """Shared credential resolution and request handling for Atonix clients."""

    def __init__(
        self,
        api_key: str | None = None,
        private_key: rsa.RSAPrivateKey | None = None,
        private_key_password: str | None = None,
        environment: AtonixEnvironment | str = AtonixEnvironment.US,
        timeout: float = 30.0,
        max_retries: int = 3,
        allow_insecure: bool = False,
    ):
        api_key = api_key or os.environ.get("ATONIX_API_KEY")
        if not api_key:
            raise ValueError("API Key must be provided or set via ATONIX_API_KEY environment variable")

        if not private_key:
            private_key_content = os.environ.get("ATONIX_PRIVATE_KEY")
            if private_key_content:
                private_key_content = private_key_content.replace("\\n", "\n")
                key_password = private_key_password or os.environ.get("ATONIX_PRIVATE_KEY_PASSWORD")
                private_key = _parse_private_key(private_key_content.encode("utf-8"), key_password)
            else:
                private_key_path = os.environ.get("ATONIX_PRIVATE_KEY_PATH")
                if private_key_path:
                    key_password = private_key_password or os.environ.get("ATONIX_PRIVATE_KEY_PASSWORD")
                    private_key = _load_private_key(private_key_path, key_password)
                else:
                    raise ValueError(
                        "Private key must be provided, or ATONIX_PRIVATE_KEY (contents) "
                        "or ATONIX_PRIVATE_KEY_PATH (file path) must be set."
                    )

        if isinstance(environment, AtonixEnvironment):
            self._base_url = environment.value.rstrip("/")
        else:
            self._base_url = str(environment).rstrip("/")
        _validate_base_url(self._base_url, allow_insecure)

        self._max_retries = max_retries
        self._auth = Auth(api_key, private_key)

    def _prepare_request(
        self,
        method: str,
        endpoint: str,
        params: dict | None = None,
        json_body: Any | None = None,
        headers: dict | None = None,
    ) -> tuple[str, dict, dict]:
        """Internal helper to prepare request components."""
        url = f"{self._base_url}{endpoint}"
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        auth_headers = self._auth.get_auth_headers(endpoint, method, clean_params, json_body)

        request_headers = auth_headers.copy()
        if headers:
            request_headers.update(headers)

        return url, clean_params, request_headers

    def _handle_response(self, response: httpx.Response, cause: BaseException | None = None) -> Any:
        """Maps HTTP status codes to Atonix exceptions."""
        if response.is_success:
            try:
                data = response.json()
                if isinstance(data, dict):
                    success = data.get("Success")
                    if success is False or (isinstance(success, str) and success.lower() == "false"):
                        msg = f"API Error (HTTP {response.status_code})"
                        code = response.status_code

                        if data.get("Results"):
                            err = data["Results"][0]
                            if isinstance(err, dict):
                                err_msg = err.get("Message", "Unknown Error")
                                err_code = err.get("Code", code)
                                msg = f"{err_code}: {err_msg}"

                                if str(err_code) == "401":
                                    raise AuthenticationError(msg + _clock_skew_hint(msg, response)) from cause
                                elif str(err_code) == "403":
                                    raise PermissionDeniedError(msg) from cause
                                elif str(err_code) == "404":
                                    raise NotFoundError(msg) from cause

                        raise APIError(msg, status_code=response.status_code, response_content=response.text) from cause

                return data
            except json.JSONDecodeError:
                return response.text

        msg = f"{response.status_code} Error: {response.reason_phrase}"
        try:
            data = response.json()
            if data.get("Results"):
                err = data["Results"][0]
                if isinstance(err, dict) and "Message" in err:
                    msg = f"{response.status_code}: {err.get('Message')} (Code: {err.get('Code')})"
        except (ValueError, json.JSONDecodeError):
            msg = f"{response.status_code} Error: {response.text}"

        error_map = {
            401: AuthenticationError,
            403: PermissionDeniedError,
            404: NotFoundError,
            429: RateLimitError,
        }

        exception_cls: type[AtonixError] = error_map.get(response.status_code, APIError)
        if exception_cls is APIError and 500 <= response.status_code < 600:
            exception_cls = ServerError

        if exception_cls is APIError:
            raise APIError(msg, status_code=response.status_code, response_content=response.text) from cause
        if exception_cls is AuthenticationError:
            msg = msg + _clock_skew_hint(msg, response)
        raise exception_cls(msg) from cause


class AtonixClient(_BaseAtonixClient):
    """Synchronous client for interacting with the Atonix OI API.

    Note:
        Authenticated requests are signed with a millisecond UTC timestamp.
        The server rejects requests whose clock is too far from server time,
        so the host running this client must keep its system clock
        synchronized (e.g. via NTP). Significant clock drift surfaces as a
        401 ``AuthenticationError`` — the error message includes a hint when
        a clock-skew cause is suspected.
    """

    def __init__(
        self,
        api_key: str | None = None,
        private_key: rsa.RSAPrivateKey | None = None,
        private_key_password: str | None = None,
        environment: AtonixEnvironment | str = AtonixEnvironment.US,
        timeout: float = 30.0,
        max_retries: int = 3,
        allow_insecure: bool = False,
    ):
        """
        Initialize the Atonix Client.

        Args:
            api_key: API Key (defaults to ATONIX_API_KEY env var).
            private_key: RSA Private Key (defaults to loading from ATONIX_PRIVATE_KEY_PATH).
            private_key_password: Password for encrypted private key (defaults to ATONIX_PRIVATE_KEY_PASSWORD env var).
            environment: API target environment or custom URL.
            timeout: Request timeout in seconds.
            max_retries: Number of times to retry transient errors (429, 5xx).
            allow_insecure: Permit a plain ``http://`` custom environment URL. Only
                intended for local testing; credentials are sent unencrypted.
        """
        super().__init__(api_key, private_key, private_key_password, environment, timeout, max_retries, allow_insecure)
        transport = httpx.HTTPTransport(retries=0)
        self._client = httpx.Client(timeout=timeout, transport=transport)

        self.assets = Assets(self)
        self.issues = Issues(self)
        self.models = Models(self)
        self.process_data = ProcessData(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """
        Executes a synchronous HTTP request to the Atonix API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/v1/assets")
            **kwargs: Additional arguments passed to httpx.Client.request.

        Returns:
            The parsed JSON or text response.

        Raises:
            AtonixError: On API or network errors.
        """
        url, params, headers = self._prepare_request(
            method,
            endpoint,
            params=kwargs.pop("params", None),
            json_body=kwargs.get("json"),
            headers=kwargs.pop("headers", None),
        )

        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    **kwargs,
                )
                response.raise_for_status()
                return self._handle_response(response)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [429, 500, 502, 503, 504] and attempt < self._max_retries:
                    wait_time = 2 ** (attempt - 1)
                    logger.warning(
                        "Request failed with %d. Retrying in %ds... (Attempt %d/%d)",
                        e.response.status_code,
                        wait_time,
                        attempt,
                        self._max_retries,
                    )
                    time.sleep(wait_time)
                    continue
                return self._handle_response(e.response, cause=e)
            except httpx.RequestError as e:
                if attempt < self._max_retries:
                    logger.warning("Request error: %s. Retrying...", str(e))
                    time.sleep(1)
                    continue
                raise APIError(f"Network error: {e!s}") from e

    def get(self, endpoint: str, **kwargs) -> Any:
        """Perform a GET request."""
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> Any:
        """Perform a POST request."""
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs) -> Any:
        """Perform a PUT request."""
        return self.request("PUT", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs) -> Any:
        """Perform a PATCH request."""
        return self.request("PATCH", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> Any:
        """Perform a DELETE request."""
        return self.request("DELETE", endpoint, **kwargs)


class AsyncAtonixClient(_BaseAtonixClient):
    """Asynchronous client for interacting with the Atonix OI API.

    Note:
        Authenticated requests are signed with a millisecond UTC timestamp.
        The server rejects requests whose clock is too far from server time,
        so the host running this client must keep its system clock
        synchronized (e.g. via NTP). Significant clock drift surfaces as a
        401 ``AuthenticationError`` — the error message includes a hint when
        a clock-skew cause is suspected.
    """

    def __init__(
        self,
        api_key: str | None = None,
        private_key: rsa.RSAPrivateKey | None = None,
        private_key_password: str | None = None,
        environment: AtonixEnvironment | str = AtonixEnvironment.US,
        timeout: float = 30.0,
        max_retries: int = 3,
        allow_insecure: bool = False,
    ):
        """
        Initialize the async Atonix Client.

        Args:
            api_key: API Key (defaults to ATONIX_API_KEY env var).
            private_key: RSA Private Key (defaults to loading from ATONIX_PRIVATE_KEY_PATH).
            private_key_password: Password for encrypted private key (defaults to ATONIX_PRIVATE_KEY_PASSWORD env var).
            environment: API target environment or custom URL.
            timeout: Request timeout in seconds.
            max_retries: Number of times to retry transient errors (429, 5xx).
            allow_insecure: Permit a plain ``http://`` custom environment URL. Only
                intended for local testing; credentials are sent unencrypted.
        """
        super().__init__(api_key, private_key, private_key_password, environment, timeout, max_retries, allow_insecure)
        transport = httpx.AsyncHTTPTransport(retries=0)
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport)

        self.assets = AsyncAssets(self)
        self.issues = AsyncIssues(self)
        self.models = AsyncModels(self)
        self.process_data = AsyncProcessData(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def aclose(self):
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def request(self, method: str, endpoint: str, **kwargs: Any) -> Any:
        """
        Executes an asynchronous HTTP request to the Atonix API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/v1/assets")
            **kwargs: Additional arguments passed to httpx.AsyncClient.request.

        Returns:
            The parsed JSON or text response.

        Raises:
            AtonixError: On API or network errors.
        """
        url, params, headers = self._prepare_request(
            method,
            endpoint,
            params=kwargs.pop("params", None),
            json_body=kwargs.get("json"),
            headers=kwargs.pop("headers", None),
        )

        for attempt in range(1, self._max_retries + 1):
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    **kwargs,
                )
                response.raise_for_status()
                return self._handle_response(response)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in [429, 500, 502, 503, 504] and attempt < self._max_retries:
                    wait_time = 2 ** (attempt - 1)
                    logger.warning(
                        "Request failed with %d. Retrying in %ds... (Attempt %d/%d)",
                        e.response.status_code,
                        wait_time,
                        attempt,
                        self._max_retries,
                    )
                    await asyncio.sleep(wait_time)
                    continue
                return self._handle_response(e.response, cause=e)
            except httpx.RequestError as e:
                if attempt < self._max_retries:
                    logger.warning("Request error: %s. Retrying...", str(e))
                    await asyncio.sleep(1)
                    continue
                raise APIError(f"Network error: {e!s}") from e

    async def get(self, endpoint: str, **kwargs) -> Any:
        """Perform a GET request."""
        return await self.request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Any:
        """Perform a POST request."""
        return await self.request("POST", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Any:
        """Perform a PUT request."""
        return await self.request("PUT", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs) -> Any:
        """Perform a PATCH request."""
        return await self.request("PATCH", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Any:
        """Perform a DELETE request."""
        return await self.request("DELETE", endpoint, **kwargs)
