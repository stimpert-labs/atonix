# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, TypeVar, cast

from atonix.object_models.common import APIResponse

if TYPE_CHECKING:
    from atonix.client import AsyncAtonixClient, AtonixClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _to_utc_ms_str(dt: datetime) -> str:
    """Format a datetime as UTC ISO 8601 with millisecond precision (e.g. '2024-01-15T12:00:00.000Z')."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _parse_api_response(result_type: type[T], data: dict[str, Any]) -> APIResponse[T]:
    """Parse raw response data into an ``APIResponse`` parametrized with ``result_type`` at runtime."""
    # Static checkers reject subscripting a generic with a runtime variable, but
    # Pydantic needs the concrete parametrization to validate the result items.
    response_model: type[APIResponse[T]] = cast(Any, APIResponse)[result_type]
    return response_model(**data)


class BaseResource:
    """Base class providing shared functionality for all Atonix API resources."""

    def __init__(self, client: AtonixClient):
        """
        Initialize the resource.

        Args:
            client: The AtonixClient instance to use for requests.
        """
        self._client = client

    def _get_paginated(
        self,
        endpoint: str,
        result_type: type[T],
        params: dict[str, Any] | None = None,
        skip: int = 0,
        take: int = 500,
    ) -> Iterator[T]:
        """
        Generic helper to handle Atonix API pagination.

        Handles the extraction of results from the Atonix standard response format
        and continues fetching until all available items have been retrieved.

        Args:
            endpoint: The API endpoint path.
            result_type: The Pydantic model class for parsing result items.
            params: Base query parameters.
            skip: Starting offset.
            take: Page size (results per request).

        Yields:
            Parsed result objects one by one.
        """
        current_params = (params or {}).copy()

        while True:
            current_params["skip"] = skip
            current_params["take"] = take

            response_data = self._client.get(endpoint, params=current_params)
            response = _parse_api_response(result_type, response_data)

            yield from response.results

            if len(response.results) < take:
                break

            skip += len(response.results)

    def _get_single(self, endpoint: str, result_type: type[T], params: dict[str, Any] | None = None) -> T:
        """
        Helper to get a single object from an endpoint that returns a wrapped list.

        Args:
            endpoint: The API endpoint path.
            result_type: The Pydantic model class for parsing the result item.
            params: Optional query parameters.

        Returns:
            The parsed result object.

        Raises:
            ValueError: If no results were found in the response.
        """
        response_data = self._client.get(endpoint, params=params)
        response = _parse_api_response(result_type, response_data)
        if not response.results:
            raise ValueError(f"No results found for {endpoint}")
        return response.results[0]


class AsyncBaseResource:
    """Base class providing shared async functionality for all Atonix API resources."""

    def __init__(self, client: AsyncAtonixClient):
        """
        Initialize the async resource.

        Args:
            client: The AsyncAtonixClient instance to use for requests.
        """
        self._client = client

    async def _get_paginated(
        self,
        endpoint: str,
        result_type: type[T],
        params: dict[str, Any] | None = None,
        skip: int = 0,
        take: int = 500,
    ) -> AsyncIterator[T]:
        """
        Generic async helper to handle Atonix API pagination.

        Args:
            endpoint: The API endpoint path.
            result_type: The Pydantic model class for parsing result items.
            params: Base query parameters.
            skip: Starting offset.
            take: Page size (results per request).

        Yields:
            Parsed result objects one by one.
        """
        current_params = (params or {}).copy()

        while True:
            current_params["skip"] = skip
            current_params["take"] = take

            response_data = await self._client.get(endpoint, params=current_params)
            response = _parse_api_response(result_type, response_data)

            for item in response.results:
                yield item

            if len(response.results) < take:
                break

            skip += len(response.results)

    async def _get_single(self, endpoint: str, result_type: type[T], params: dict[str, Any] | None = None) -> T:
        """
        Async helper to get a single object from an endpoint that returns a wrapped list.

        Args:
            endpoint: The API endpoint path.
            result_type: The Pydantic model class for parsing the result item.
            params: Optional query parameters.

        Returns:
            The parsed result object.

        Raises:
            ValueError: If no results were found in the response.
        """
        response_data = await self._client.get(endpoint, params=params)
        response = _parse_api_response(result_type, response_data)
        if not response.results:
            raise ValueError(f"No results found for {endpoint}")
        return response.results[0]
