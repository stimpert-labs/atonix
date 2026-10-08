# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from __future__ import annotations

import logging
import math
import os
from collections.abc import AsyncIterator, Iterable, Iterator
from datetime import datetime, timedelta
from typing import Any

from atonix.base import AsyncBaseResource, BaseResource
from atonix.exceptions import QuerySizeError
from atonix.object_models.common import APIResponse
from atonix.object_models.processdata import Archive, Server, Tag, TagData

logger = logging.getLogger(__name__)

# Maximum tag x timestamp points per read query.
_READ_CHUNK_LIMIT = 250_000
# Maximum tag x timestamp points per write request.
_WRITE_CHUNK_LIMIT = 30_000

# Env var that opts in to logging full time-series payloads at DEBUG.
# Off by default: bulk payloads can be large and may contain sensitive
# process values, so production logs only get a short summary.
_PAYLOAD_LOG_ENV = "ATONIX_LOG_PAYLOADS"
_TRUTHY = {"1", "true", "yes", "on"}


def _payload_logging_enabled() -> bool:
    """Return True when full payload logging is opted in via env var."""
    return os.environ.get(_PAYLOAD_LOG_ENV, "").strip().lower() in _TRUTHY


def _summarize_query_response(response_data: Any) -> str:
    """Return a short, value-free summary of a /processdata/query response."""
    if not isinstance(response_data, dict):
        return f"<non-dict response: {type(response_data).__name__}>"
    success = response_data.get("Success")
    results = response_data.get("Results") or []
    tag_count = len(results) if isinstance(results, list) else 0
    point_count = 0
    if isinstance(results, list):
        for r in results:
            if not isinstance(r, dict):
                continue
            data = r.get("Data") or {}
            timestamps = data.get("Timestamps") if isinstance(data, dict) else None
            if isinstance(timestamps, list):
                point_count += len(timestamps)
    return f"Success={success}, tags={tag_count}, points={point_count}"


def _summarize_tag_result(tag_res: TagData) -> str:
    """Return a short, value-free summary of a single TagData result."""
    point_count = len(tag_res.timestamps) if tag_res.timestamps else 0
    return f"tag={tag_res.tag_id} http={tag_res.http_code} points={point_count}"


def _validate_time_range(start_time: datetime, end_time: datetime) -> bool:
    return start_time <= end_time


def _validate_query_size(tag_count: int, start_time: datetime, end_time: datetime, interval: int) -> bool:
    if interval <= 0:
        # Raw data: can't estimate point count, so skip size check.
        return True
    total_points = (end_time - start_time).total_seconds() / interval * tag_count
    return total_points <= _READ_CHUNK_LIMIT


def _timestamps_per_tag(start_time: datetime, end_time: datetime, interval: int) -> float:
    """Estimate the number of timestamps per tag for a range at the given archive interval."""
    return (end_time - start_time).total_seconds() / interval


def _plan_read_chunks(
    tag_ids: list[str], start_time: datetime, end_time: datetime, interval: int
) -> list[tuple[list[str], datetime, datetime]]:
    """Split a read query into (tag_ids, start, end) sub-queries that each fit within _READ_CHUNK_LIMIT.

    Each sub-query covers ``k`` tags over one time window of ``w`` intervals, with
    ``k * (w + 1) <= _READ_CHUNK_LIMIT`` (windows are inclusive at both ends, so ``w``
    intervals is ``w + 1`` points per tag). Every ``k`` is tried and the one giving the
    fewest requests wins, so both wide-and-short and narrow-and-long queries pack tightly.
    Windows and tag groups are then evened out without changing the request count.
    """
    total_intervals = math.ceil(_timestamps_per_tag(start_time, end_time, interval))
    tag_count = len(tag_ids)

    def _layout(tags_per_chunk: int) -> tuple[int, int]:
        """Return (window_count, group_count) when each request carries ``tags_per_chunk`` tags."""
        max_intervals = _READ_CHUNK_LIMIT // tags_per_chunk - 1
        return max(1, math.ceil(total_intervals / max_intervals)), math.ceil(tag_count / tags_per_chunk)

    max_tags_per_chunk = max(1, min(tag_count, _READ_CHUNK_LIMIT // 2))
    window_count, group_count = min(
        (_layout(k) for k in range(1, max_tags_per_chunk + 1)), key=lambda layout: layout[0] * layout[1]
    )

    # Even out windows and groups; each stays within the chosen bounds, so the limit still holds.
    intervals_per_window = max(1, math.ceil(total_intervals / window_count))
    tags_per_chunk = math.ceil(tag_count / group_count)

    window_span = timedelta(seconds=intervals_per_window * interval)
    windows: list[tuple[datetime, datetime]] = []
    window_start = start_time
    while True:
        window_end = min(window_start + window_span, end_time)
        windows.append((window_start, window_end))
        if window_end >= end_time:
            break
        window_start = window_end

    return [
        (tag_ids[i : i + tags_per_chunk], w_start, w_end)
        for w_start, w_end in windows
        for i in range(0, tag_count, tags_per_chunk)
    ]


def _is_error_code(http_code: int | None) -> bool:
    return http_code is not None and not 200 <= http_code < 300


def _merge_tag_results(tag_ids: list[str], chunk_results: list[list[TagData]]) -> list[TagData]:
    """Reassemble per-chunk TagData results into one TagData per tag.

    ``chunk_results`` must be ordered by time window. Points at or before the last
    timestamp already merged for a tag are dropped, which removes the duplicate point
    shared by adjacent inclusive windows. The first non-2xx ``http_code``/``error`` seen
    for a tag is kept so failures in any chunk remain visible.
    """
    merged: dict[str, TagData] = {}
    for results in chunk_results:
        for res in results:
            existing = merged.get(res.tag_id)
            if existing is None:
                merged[res.tag_id] = res.model_copy(deep=True)
                continue
            if _is_error_code(res.http_code) and not _is_error_code(existing.http_code):
                existing.http_code = res.http_code
                existing.error = res.error
            if not res.timestamps:
                continue
            if not existing.timestamps:
                existing.timestamps, existing.values, existing.statuses = [], [], []
            last = existing.timestamps[-1] if existing.timestamps else None
            for idx, ts in enumerate(res.timestamps):
                if last is not None and ts <= last:
                    continue
                existing.timestamps.append(ts)
                if existing.values is not None and res.values is not None:
                    existing.values.append(res.values[idx])
                if existing.statuses is not None and res.statuses is not None:
                    existing.statuses.append(res.statuses[idx])

    ordered = [merged.pop(tag_id) for tag_id in dict.fromkeys(tag_ids) if tag_id in merged]
    # Keep any tags the API returned that weren't in the request, rather than dropping them silently.
    ordered.extend(merged.values())
    return ordered


def _check_query_size(tag_ids: list[str], start_time: datetime, end_time: datetime, interval: int, chunk: bool) -> bool:
    """Return True when the query must be chunked; raise QuerySizeError if it's too large and chunking is off."""
    if _validate_query_size(len(tag_ids), start_time, end_time, interval):
        return False
    timestamps_per_tag = _timestamps_per_tag(start_time, end_time, interval)
    if not chunk:
        logger.error(
            "Query limit: %d tag-timestamp pairs. Tag count: %d, Timestamps: %.0f",
            _READ_CHUNK_LIMIT,
            len(tag_ids),
            timestamps_per_tag,
        )
        raise QuerySizeError(_READ_CHUNK_LIMIT, len(tag_ids), timestamps_per_tag)
    return True


def _build_query_payload(
    server_id: str, start_time: datetime, end_time: datetime, tag_ids: list[str], archive: str
) -> dict[str, Any]:
    return {
        "ServerId": server_id,
        "Start": start_time.isoformat(),
        "End": end_time.isoformat(),
        "Archive": archive,
        "TagIds": tag_ids,
    }


def _parse_query_response(response_data: Any) -> list[TagData]:
    """Log, validate, and parse a /processdata/query response into TagData results."""
    if _payload_logging_enabled():
        logger.debug("Response data: %s", response_data)
    else:
        logger.debug("Response data summary: %s", _summarize_query_response(response_data))
    if not response_data.get("Success"):
        logger.error("Failed to retrieve data: %s", response_data.get("Results"))
        raise ValueError(response_data.get("Message") or "API returned failure with no message")
    response = APIResponse[TagData](**response_data)

    for tag_res in response.results:
        if _payload_logging_enabled():
            logger.debug("tag_res: %s", tag_res)
        else:
            logger.debug("tag_res summary: %s", _summarize_tag_result(tag_res))
        if _is_error_code(tag_res.http_code):
            logger.error("Failed to retrieve data for tag %s: Code %d", tag_res.tag_id, tag_res.http_code)

    return response.results


def _iter_tag_chunks(data: list[TagData]) -> Iterable[tuple[dict[str, Any], int]]:
    """Yield (tag-entry dict, point count) tuples chunked at _WRITE_CHUNK_LIMIT per series.

    Each yielded entry corresponds to one TagData slice of up to _WRITE_CHUNK_LIMIT
    points, in the wire shape expected inside the ``TagData`` array of a write
    payload. Callers are responsible for packing entries into batches.
    """
    for series in data:
        if series.timestamps is None or series.values is None:
            raise ValueError(f"TagData for tag {series.tag_id} must have both timestamps and values to be written")
        for i in range(0, len(series.timestamps), _WRITE_CHUNK_LIMIT):
            chunk_timestamps = series.timestamps[i : i + _WRITE_CHUNK_LIMIT]
            chunk_values = series.values[i : i + _WRITE_CHUNK_LIMIT]
            chunk_statuses = (
                series.statuses[i : i + _WRITE_CHUNK_LIMIT] if series.statuses else [0] * len(chunk_timestamps)
            )
            entry = {
                "TagId": series.tag_id,
                "Data": {
                    "Timestamps": [t.isoformat() for t in chunk_timestamps],
                    "Values": chunk_values,
                    "Statuses": chunk_statuses,
                },
            }
            yield entry, len(chunk_timestamps)


class ProcessData(BaseResource):
    """Interface for the Atonix ProcessData (Time-Series) API."""

    def get_servers(self, skip: int = 0, take: int = 50) -> Iterator[Server]:
        """
        List all available operational servers (historians).

        Args:
            skip: Offset for pagination.
            take: Number of results per page (expected max 50).

        Yields:
            Server objects one by one.
        """
        return self._get_paginated("/v1/processdata/servers", Server, skip=skip, take=take)

    def get_tags_list(
        self,
        server_id: str,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        skip: int = 0,
        take: int = 50,
    ) -> Iterator[Tag]:
        """
        List tags available on a specific server.

        Args:
            server_id: The unique identifier (GUID) of the historian server.
            changed_after: Filter tags modified after this date.
            changed_before: Filter tags modified before this date.
            skip: Offset for pagination.
            take: Results per page.

        Yields:
            Tag objects (basic info) one by one.
        """
        params: dict[str, Any] = {}
        if changed_after:
            params["changedAfter"] = changed_after.isoformat()
        if changed_before:
            params["changedBefore"] = changed_before.isoformat()

        return self._get_paginated(
            f"/v1/processdata/servers/{server_id}/tags", Tag, params=params, skip=skip, take=take
        )

    def get_tag_details(self, tag_id: str) -> Tag:
        """
        Get full details for a single tag.

        Args:
            tag_id: The unique identifier (GUID) of the tag.

        Returns:
            A Tag object with all detail fields populated.
        """
        return self._get_single(f"/v1/processdata/tags/{tag_id}", Tag)

    def get_archives(self, server_id: str) -> Iterator[Archive]:
        """
        List available archives (time resolutions) for a server.

        Common archives include '1min', '60min'.

        Args:
            server_id: The unique identifier (GUID) of the server.

        Yields:
            Archive objects one by one.
        """
        return self._get_paginated(f"/v1/processdata/servers/{server_id}/archives", Archive, take=50)

    def get_data_for_range(
        self,
        server_id: str,
        start_time: datetime,
        end_time: datetime,
        tag_ids: list[str],
        archive: str,
        chunk: bool = True,
    ) -> list[TagData]:
        """
        Retrieve time-series data for a set of tags over a date range.

        Automatically calculates requirements for interval/sampling based on the archive.
        Queries larger than ``_READ_CHUNK_LIMIT`` (250,000 tag x timestamp points) are split
        into sub-queries by tag group and, when a single tag exceeds the limit, by time window.
        The per-tag series are reassembled before returning.

        Args:
            server_id: The unique identifier (GUID) of the historian server.
            start_time: Start of the query window (UTC).
            end_time: End of the query window (UTC).
            tag_ids: List of tag GUIDs to retrieve data for.
            archive: Archive name to query (e.g., '1min', 'raw').
            chunk: When True (default), split oversized queries automatically. When False,
                raise ``QuerySizeError`` instead.

        Returns:
            A list of TagData objects, one per tag requested.

        Raises:
            QuerySizeError: If the query exceeds the point limit and ``chunk`` is False.
        """

        if not _validate_time_range(start_time, end_time):
            raise ValueError("Start time must be before end time")

        logger.debug("Querying ProcessData range: %s to %s for %d tags", start_time, end_time, len(tag_ids))

        # We need the interval from the archive to build the request correctly
        archives = self.get_archives(server_id)
        archive_info = next((a for a in archives if a.name.lower() == archive.lower()), None)
        if not archive_info:
            raise ValueError(f"Archive `{archive}` not found on server: {server_id}")
        else:
            interval = archive_info.interval

        if not _check_query_size(tag_ids, start_time, end_time, interval, chunk):
            payload = _build_query_payload(server_id, start_time, end_time, tag_ids, archive)
            return _parse_query_response(self._client.post("/v1/processdata/query", json=payload))

        chunks = _plan_read_chunks(tag_ids, start_time, end_time, interval)
        logger.info("Query exceeds %d points; splitting into %d sub-queries", _READ_CHUNK_LIMIT, len(chunks))
        chunk_results = []
        for chunk_tags, chunk_start, chunk_end in chunks:
            payload = _build_query_payload(server_id, chunk_start, chunk_end, chunk_tags, archive)
            chunk_results.append(_parse_query_response(self._client.post("/v1/processdata/query", json=payload)))
        return _merge_tag_results(tag_ids, chunk_results)

    def write_tag_data(self, server_id: str, archive: str, data: list[TagData]) -> None:
        """
        Write time-series data back to Atonix.

        Handles large payloads by automatically chunking data into manageable sizes
        for the Atonix API (limit approx 30,000 points per call). Multiple tags are
        packed into a single POST whenever their combined point count fits within
        ``_WRITE_CHUNK_LIMIT``, which dramatically reduces request count for
        wide-but-shallow uploads (many tags, few points each).

        Args:
            server_id: The unique identifier (GUID) of the target server.
            archive: The archive to write to.
            data: List of TagData objects containing the data to write.
        """
        logger.debug("Writing process data to server %s, archive %s", server_id, archive)

        batch: list[dict[str, Any]] = []
        batch_points = 0

        def _flush() -> None:
            nonlocal batch, batch_points
            if not batch:
                return
            payload = {
                "ServerId": server_id,
                "Archive": archive,
                "TagData": batch,
            }
            self._client.post("/v1/processdata/write", json=payload)
            batch = []
            batch_points = 0

        for entry, points in _iter_tag_chunks(data):
            if batch and batch_points + points > _WRITE_CHUNK_LIMIT:
                _flush()
            batch.append(entry)
            batch_points += points

        _flush()


class AsyncProcessData(AsyncBaseResource):
    """Async interface for the Atonix ProcessData (Time-Series) API."""

    def get_servers(self, skip: int = 0, take: int = 50) -> AsyncIterator[Server]:
        """
        List all available operational servers (historians).

        Args:
            skip: Offset for pagination.
            take: Number of results per page (expected max 50).

        Returns:
            An async iterator of Server objects.
        """
        return self._get_paginated("/v1/processdata/servers", Server, skip=skip, take=take)

    def get_tags_list(
        self,
        server_id: str,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        skip: int = 0,
        take: int = 50,
    ) -> AsyncIterator[Tag]:
        """
        List tags available on a specific server.

        Args:
            server_id: The unique identifier (GUID) of the historian server.
            changed_after: Filter tags modified after this date.
            changed_before: Filter tags modified before this date.
            skip: Offset for pagination.
            take: Results per page.

        Returns:
            An async iterator of Tag objects.
        """
        params: dict[str, Any] = {}
        if changed_after:
            params["changedAfter"] = changed_after.isoformat()
        if changed_before:
            params["changedBefore"] = changed_before.isoformat()

        return self._get_paginated(
            f"/v1/processdata/servers/{server_id}/tags", Tag, params=params, skip=skip, take=take
        )

    async def get_tag_details(self, tag_id: str) -> Tag:
        """
        Get full details for a single tag.

        Args:
            tag_id: The unique identifier (GUID) of the tag.

        Returns:
            A Tag object with all detail fields populated.
        """
        return await self._get_single(f"/v1/processdata/tags/{tag_id}", Tag)

    def get_archives(self, server_id: str) -> AsyncIterator[Archive]:
        """
        List available archives (time resolutions) for a server.

        Args:
            server_id: The unique identifier (GUID) of the server.

        Returns:
            An async iterator of Archive objects.
        """
        return self._get_paginated(f"/v1/processdata/servers/{server_id}/archives", Archive, take=50)

    async def get_data_for_range(
        self,
        server_id: str,
        start_time: datetime,
        end_time: datetime,
        tag_ids: list[str],
        archive: str,
        chunk: bool = True,
    ) -> list[TagData]:
        """
        Retrieve time-series data for a set of tags over a date range.

        Queries larger than ``_READ_CHUNK_LIMIT`` (250,000 tag x timestamp points) are split
        into sub-queries by tag group and, when a single tag exceeds the limit, by time window.
        Sub-queries run sequentially and the per-tag series are reassembled before returning.

        Args:
            server_id: The unique identifier (GUID) of the historian server.
            start_time: Start of the query window (UTC).
            end_time: End of the query window (UTC).
            tag_ids: List of tag GUIDs to retrieve data for.
            archive: Archive name to query (e.g., '1min', 'raw').
            chunk: When True (default), split oversized queries automatically. When False,
                raise ``QuerySizeError`` instead.

        Returns:
            A list of TagData objects, one per tag requested.

        Raises:
            QuerySizeError: If the query exceeds the point limit and ``chunk`` is False.
        """
        if not _validate_time_range(start_time, end_time):
            raise ValueError("Start time must be before end time")

        logger.debug("Querying ProcessData range: %s to %s for %d tags", start_time, end_time, len(tag_ids))

        archive_info = None
        async for a in self.get_archives(server_id):
            if a.name.lower() == archive.lower():
                archive_info = a
                break

        if not archive_info:
            raise ValueError(f"Archive `{archive}` not found on server: {server_id}")

        interval = archive_info.interval

        if not _check_query_size(tag_ids, start_time, end_time, interval, chunk):
            payload = _build_query_payload(server_id, start_time, end_time, tag_ids, archive)
            return _parse_query_response(await self._client.post("/v1/processdata/query", json=payload))

        chunks = _plan_read_chunks(tag_ids, start_time, end_time, interval)
        logger.info("Query exceeds %d points; splitting into %d sub-queries", _READ_CHUNK_LIMIT, len(chunks))
        chunk_results = []
        for chunk_tags, chunk_start, chunk_end in chunks:
            payload = _build_query_payload(server_id, chunk_start, chunk_end, chunk_tags, archive)
            chunk_results.append(_parse_query_response(await self._client.post("/v1/processdata/query", json=payload)))
        return _merge_tag_results(tag_ids, chunk_results)

    async def write_tag_data(self, server_id: str, archive: str, data: list[TagData]) -> None:
        """
        Write time-series data back to Atonix.

        Handles large payloads by automatically chunking data into manageable sizes
        for the Atonix API (limit approx 30,000 points per call). Multiple tags are
        packed into a single POST whenever their combined point count fits within
        ``_WRITE_CHUNK_LIMIT``, which dramatically reduces request count for
        wide-but-shallow uploads (many tags, few points each).

        Args:
            server_id: The unique identifier (GUID) of the target server.
            archive: The archive to write to.
            data: List of TagData objects containing the data to write.
        """
        logger.debug("Writing process data to server %s, archive %s", server_id, archive)

        batch: list[dict[str, Any]] = []
        batch_points = 0

        async def _flush() -> None:
            nonlocal batch, batch_points
            if not batch:
                return
            payload = {
                "ServerId": server_id,
                "Archive": archive,
                "TagData": batch,
            }
            await self._client.post("/v1/processdata/write", json=payload)
            batch = []
            batch_points = 0

        for entry, points in _iter_tag_chunks(data):
            if batch and batch_points + points > _WRITE_CHUNK_LIMIT:
                await _flush()
            batch.append(entry)
            batch_points += points

        await _flush()
