# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Shared, I/O-free request logic for the sync and async resource classes.

Every endpoint is implemented exactly once, as an *operation*: a generator that
yields :class:`Call` objects describing the HTTP requests it needs, receives each
parsed response back via ``send()``, and finally returns its result. Paginated
listings are described by a :class:`Pager` instead, so they can stay lazy.

``BaseResource`` and ``AsyncBaseResource`` are the only places that perform I/O:
they drive operations and pagers against the sync or async client respectively.
The public ``Assets``/``AsyncAssets`` (etc.) classes are thin, fully documented
wrappers that hand an operation or pager to their base class.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable, Generator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Generic, TypeAlias, TypeVar, cast

from atonix.exceptions import APIError
from atonix.object_models.common import APIResponse

if TYPE_CHECKING:
    from atonix.client import AsyncAtonixClient, AtonixClient

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _to_utc_ms_str(dt: datetime) -> str:
    """Format a datetime as UTC ISO 8601 with millisecond precision (e.g. '2024-01-15T12:00:00.000Z')."""
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _parse_api_response(result_type: type[T], data: dict[str, Any]) -> APIResponse[T]:
    """Parse raw response data into an ``APIResponse`` parametrized with ``result_type`` at runtime."""
    # Static checkers reject subscripting a generic with a runtime variable, but
    # Pydantic needs the concrete parametrization to validate the result items.
    response_model: type[APIResponse[T]] = cast(Any, APIResponse)[result_type]
    return response_model(**data)


def _first_result(result_type: type[T], data: dict[str, Any], error: str) -> T:
    """Parse ``data`` and return its first result, raising ``APIError(error)`` when there is none."""
    results = _parse_api_response(result_type, data).results
    if not results:
        raise APIError(error)
    return results[0]


@dataclass(frozen=True)
class Call:
    """One HTTP request an operation needs performed."""

    method: str
    endpoint: str
    params: dict[str, Any] | None = None
    json: Any = None


Op: TypeAlias = Generator[Call, Any, T]
"""An operation: yields ``Call``s, is sent each parsed response, and returns a ``T``."""


def call(method: str, endpoint: str, *, params: dict[str, Any] | None = None, json: Any = None) -> Op[Any]:
    """Operation that performs a single request and returns its parsed response."""
    return (yield Call(method, endpoint, params, json))


def single(endpoint: str, result_type: type[T], params: dict[str, Any] | None = None) -> Op[T]:
    """Operation that GETs an endpoint returning a wrapped list and returns its first result.

    Raises:
        ValueError: If no results were found in the response.
    """
    data = yield Call("GET", endpoint, params)
    response = _parse_api_response(result_type, data)
    if not response.results:
        raise ValueError(f"No results found for {endpoint}")
    return response.results[0]


class Pager(Generic[T]):
    """I/O-free state machine for the Atonix ``skip``/``take`` pagination scheme.

    Call ``next_call()`` to get the next page request (``None`` once exhausted),
    perform it, and pass the response to ``consume()`` to get that page's items.
    """

    def __init__(
        self,
        endpoint: str,
        result_type: type[T],
        params: dict[str, Any] | None = None,
        skip: int = 0,
        take: int = 500,
    ):
        self.endpoint = endpoint
        self.result_type = result_type
        self.params = dict(params or {})
        self.skip = skip
        self.take = take
        self.done = False

    def next_call(self) -> Call | None:
        """Return the request for the next page, or ``None`` when every page has been fetched."""
        if self.done:
            return None
        return Call("GET", self.endpoint, {**self.params, "skip": self.skip, "take": self.take})

    def consume(self, data: dict[str, Any]) -> list[T]:
        """Parse one page response, advance the offset, and return the page's items."""
        results = _parse_api_response(self.result_type, data).results
        if len(results) < self.take:
            self.done = True
        self.skip += len(results)
        return results


def find(pager: Pager[T], predicate: Callable[[T], bool]) -> Op[T | None]:
    """Operation returning the first paginated item matching ``predicate``, fetching no further pages."""
    while (page_call := pager.next_call()) is not None:
        for item in pager.consume((yield page_call)):
            if predicate(item):
                return item
    return None


def collect(pager: Pager[T]) -> Op[list[T]]:
    """Operation returning every item from a paginated listing."""
    items: list[T] = []
    while (page_call := pager.next_call()) is not None:
        items.extend(pager.consume((yield page_call)))
    return items


class BaseResource:
    """Base class for sync resources: runs operations and pagers against an ``AtonixClient``."""

    def __init__(self, client: AtonixClient):
        """
        Initialize the resource.

        Args:
            client: The AtonixClient instance to use for requests.
        """
        self._client = client

    def _send(self, request: Call) -> Any:
        return self._client.request(request.method, request.endpoint, params=request.params, json=request.json)

    def _run(self, op: Op[T]) -> T:
        """Drive an operation to completion, performing each request it yields."""
        try:
            request = next(op)
            while True:
                try:
                    response = self._send(request)
                except Exception as exc:
                    request = op.throw(exc)
                else:
                    request = op.send(response)
        except StopIteration as stop:
            return cast(T, stop.value)

    def _iterate(self, pager: Pager[T]) -> Iterator[T]:
        """Lazily yield every item of a paginated listing; no request is made until iteration starts."""
        while (request := pager.next_call()) is not None:
            yield from pager.consume(self._send(request))


class AsyncBaseResource:
    """Base class for async resources: runs operations and pagers against an ``AsyncAtonixClient``."""

    def __init__(self, client: AsyncAtonixClient):
        """
        Initialize the async resource.

        Args:
            client: The AsyncAtonixClient instance to use for requests.
        """
        self._client = client

    async def _send(self, request: Call) -> Any:
        return await self._client.request(request.method, request.endpoint, params=request.params, json=request.json)

    async def _run(self, op: Op[T]) -> T:
        """Drive an operation to completion, awaiting each request it yields."""
        try:
            request = next(op)
            while True:
                try:
                    response = await self._send(request)
                except Exception as exc:
                    request = op.throw(exc)
                else:
                    request = op.send(response)
        except StopIteration as stop:
            return cast(T, stop.value)

    async def _iterate(self, pager: Pager[T]) -> AsyncIterator[T]:
        """Lazily yield every item of a paginated listing; no request is made until iteration starts."""
        while (request := pager.next_call()) is not None:
            for item in pager.consume(await self._send(request)):
                yield item
