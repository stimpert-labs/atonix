# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the ProcessData resource."""

import json
from datetime import datetime, timedelta, timezone
from itertools import pairwise

import pytest
import respx
from httpx import Response

from atonix.exceptions import AtonixError, QuerySizeError
from atonix.object_models.processdata import Server, Tag, TagData
from atonix.processdata import (
    _READ_CHUNK_LIMIT,
    ProcessData,
    _merge_tag_results,
    _plan_read_chunks,
    _validate_query_size,
)
from tests.conftest import (
    BASE_URL,
    make_api_response,
    make_servers,
    make_tag,
    make_tags,
    query_echo_side_effect,
)


class TestGetServers:
    """Tests for ProcessData.get_servers()."""

    @respx.mock
    def test_get_servers_single_page(self, mock_client):
        """get_servers should return servers when count < take."""
        servers_data = make_servers(10)
        respx.get(f"{BASE_URL}/v1/processdata/servers").mock(
            return_value=Response(200, json=make_api_response(servers_data, count=10, type_name="ListServerResult"))
        )

        pd_api = ProcessData(mock_client)
        result = list(pd_api.get_servers())

        assert len(result) == 10
        assert all(isinstance(s, Server) for s in result)


class TestGetTagsList:
    """Tests for ProcessData.get_tags_list()."""

    @respx.mock
    def test_get_tags_list(self, mock_client):
        """get_tags_list should return tags."""
        server_id = "33333333-3333-3333-3333-333333333333"
        tags_data = make_tags(10)
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/tags").mock(
            return_value=Response(200, json=make_api_response(tags_data, count=10, type_name="ListTagResult"))
        )

        pd_api = ProcessData(mock_client)
        result = list(pd_api.get_tags_list(server_id))

        assert len(result) == 10

    @respx.mock
    def test_get_tags_list_pagination(self, mock_client):
        """get_tags_list should fetch all tags across multiple pages."""
        # Atonix default take for tags is 50.
        # We'll mock a total of 60 tags across two pages.
        server_id = "33333333-3333-3333-3333-333333333333"

        page1_tags = make_tags(50, start_index=0)
        page2_tags = make_tags(10, start_index=50)

        # Mock first call (skip=0, take=50)
        route1 = respx.get(
            f"{BASE_URL}/v1/processdata/servers/{server_id}/tags", params={"skip": "0", "take": "50"}
        ).mock(return_value=Response(200, json=make_api_response(page1_tags, count=60)))

        # Mock second call (skip=50, take=50)
        route2 = respx.get(
            f"{BASE_URL}/v1/processdata/servers/{server_id}/tags", params={"skip": "50", "take": "50"}
        ).mock(return_value=Response(200, json=make_api_response(page2_tags, count=60)))

        pd_api = ProcessData(mock_client)
        result = list(pd_api.get_tags_list(server_id))

        assert len(result) == 60
        assert result[0].name == "Tag0"
        assert result[59].name == "Tag59"
        assert route1.called
        assert route2.called
        assert len(respx.calls) == 2


class TestGetDataForRange:
    """Tests for ProcessData.get_data_for_range()."""

    @respx.mock
    def test_get_data_for_range_basic(self, mock_client):
        """get_data_for_range should return tag data."""
        server_id = "33333333-3333-3333-3333-333333333333"
        tag_ids = ["44444444-4444-4444-4444-444444444444"]

        # Mock archives
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": "1min", "Interval": 60}], count=1, type_name="ListArchiveResult"),
            )
        )

        data_response = {
            "Success": True,
            "StatusCode": 200,
            "Results": [
                {
                    "TagId": tag_ids[0],
                    "HttpCode": 200,
                    "Data": {
                        "Timestamps": ["2024-01-15T12:00:00.000Z", "2024-01-15T12:01:00.000Z"],
                        "Values": [100.0, 101.0],
                        "Statuses": [0, 0],
                    },
                }
            ],
        }
        respx.post(f"{BASE_URL}/v1/processdata/query").mock(return_value=Response(200, json=data_response))

        pd_api = ProcessData(mock_client)
        result = pd_api.get_data_for_range(
            server_id=server_id,
            start_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc),
            tag_ids=tag_ids,
            archive="1min",
        )

        assert len(result) == 1
        assert isinstance(result[0], TagData)
        assert result[0].tag_id == tag_ids[0]

    @respx.mock
    def test_get_data_for_range_missing_http_code(self, mock_client):
        """get_data_for_range should tolerate tag results that omit HttpCode."""
        server_id = "33333333-3333-3333-3333-333333333333"
        tag_ids = ["44444444-4444-4444-4444-444444444444"]

        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": "1min", "Interval": 60}], count=1, type_name="ListArchiveResult"),
            )
        )
        data_response = {
            "Success": True,
            "StatusCode": 200,
            "Results": [{"TagId": tag_ids[0], "Data": {"Timestamps": [], "Values": [], "Statuses": []}}],
        }
        respx.post(f"{BASE_URL}/v1/processdata/query").mock(return_value=Response(200, json=data_response))

        result = ProcessData(mock_client).get_data_for_range(
            server_id=server_id,
            start_time=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            end_time=datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc),
            tag_ids=tag_ids,
            archive="1min",
        )

        assert len(result) == 1
        assert result[0].http_code is None


class TestWriteTagData:
    """Tests for ProcessData.write_tag_data()."""

    @respx.mock
    def test_write_tag_data_basic(self, mock_client):
        """write_tag_data should send tag data to API."""
        server_id = "33333333-3333-3333-3333-333333333333"

        respx.post(f"{BASE_URL}/v1/processdata/write").mock(
            return_value=Response(200, json=make_api_response([{"TagId": "tag1", "HttpCode": 200}], count=1))
        )

        pd_api = ProcessData(mock_client)
        tag_data = [TagData(tag_id="tag1", timestamps=[datetime.now(timezone.utc)], values=[100.0], statuses=[0])]
        pd_api.write_tag_data(server_id, "1min", tag_data)

        assert len(respx.calls) == 1
        request = respx.calls[0].request
        import json

        payload = json.loads(request.content)
        assert "Data" in payload["TagData"][0]
        assert "Timestamps" in payload["TagData"][0]["Data"]

    @respx.mock
    def test_write_tag_data_packs_multiple_tags(self, mock_client):
        """write_tag_data should pack many small TagData entries into a single POST."""
        server_id = "33333333-3333-3333-3333-333333333333"

        route = respx.post(f"{BASE_URL}/v1/processdata/write").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )

        pd_api = ProcessData(mock_client)
        now = datetime.now(timezone.utc)
        # 100 tiny tags, one point each — well under the 30k chunk limit.
        tag_data = [TagData(tag_id=f"tag-{n}", timestamps=[now], values=[float(n)], statuses=[0]) for n in range(100)]

        pd_api.write_tag_data(server_id, "1min", tag_data)

        assert len(respx.calls) == 1
        import json

        payload = json.loads(route.calls[0].request.content)
        assert len(payload["TagData"]) == 100
        assert payload["TagData"][0]["TagId"] == "tag-0"
        assert payload["TagData"][-1]["TagId"] == "tag-99"

    @respx.mock
    def test_write_tag_data_flushes_at_batch_limit(self, mock_client):
        """write_tag_data should flush the current batch when adding the next chunk would exceed the limit."""
        server_id = "33333333-3333-3333-3333-333333333333"

        route = respx.post(f"{BASE_URL}/v1/processdata/write").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )

        pd_api = ProcessData(mock_client)
        now = datetime.now(timezone.utc)
        # Four tags of 10,000 points each = 40,000 total points.
        # Chunk limit is 30,000:
        #   tag-0 -> batch=10k
        #   tag-1 -> batch=20k
        #   tag-2 -> batch=30k (fits exactly, no flush)
        #   tag-3 -> would push to 40k > 30k -> flush prior (3 tags), then add tag-3
        #   end -> flush trailing (1 tag)
        # Expected: 2 POSTs, with 3 + 1 tags respectively.
        tag_data = []
        for n in range(4):
            ts = [now + timedelta(seconds=i) for i in range(10_000)]
            tag_data.append(TagData(tag_id=f"tag-{n}", timestamps=ts, values=[0.0] * 10_000, statuses=[0] * 10_000))

        pd_api.write_tag_data(server_id, "1min", tag_data)

        assert len(respx.calls) == 2
        import json

        first = json.loads(route.calls[0].request.content)
        second = json.loads(route.calls[1].request.content)
        assert len(first["TagData"]) == 3
        assert len(second["TagData"]) == 1
        assert [t["TagId"] for t in first["TagData"]] == ["tag-0", "tag-1", "tag-2"]
        assert second["TagData"][0]["TagId"] == "tag-3"

    @respx.mock
    def test_write_tag_data_empty_list_makes_no_requests(self, mock_client):
        """write_tag_data with empty data should not POST anything."""
        respx.post(f"{BASE_URL}/v1/processdata/write").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )
        pd_api = ProcessData(mock_client)
        pd_api.write_tag_data("server", "1min", [])
        assert len(respx.calls) == 0

    @respx.mock
    def test_write_tag_data_missing_values_raises(self, mock_client):
        """write_tag_data should reject TagData without timestamps/values before sending anything."""
        respx.post(f"{BASE_URL}/v1/processdata/write").mock(
            return_value=Response(200, json=make_api_response([], count=0))
        )
        tag_data = [TagData(tag_id="tag1", timestamps=[datetime.now(timezone.utc)], values=None)]

        with pytest.raises(ValueError, match="tag1"):
            ProcessData(mock_client).write_tag_data("server", "1min", tag_data)
        assert len(respx.calls) == 0

        server_id = "33333333-3333-3333-3333-333333333333"
        tags_data = make_tags(5)
        route = respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/tags").mock(
            return_value=Response(200, json=make_api_response(tags_data, count=5))
        )

        pd_api = ProcessData(mock_client)
        changed_after = datetime(2024, 1, 1, tzinfo=timezone.utc)
        changed_before = datetime(2024, 2, 1, tzinfo=timezone.utc)
        result = list(pd_api.get_tags_list(server_id, changed_after=changed_after, changed_before=changed_before))

        assert len(result) == 5
        params = route.calls.last.request.url.params
        assert "changedAfter" in params
        assert "changedBefore" in params


class TestGetTagDetails:
    """Tests for ProcessData.get_tag_details()."""

    @respx.mock
    def test_get_tag_details(self, mock_client):
        """get_tag_details should return a single Tag object."""
        tag_id = "44444444-4444-4444-4444-444444444444"
        tag_data = make_tag(tag_id=tag_id, name="PressureTag")
        respx.get(f"{BASE_URL}/v1/processdata/tags/{tag_id}").mock(
            return_value=Response(200, json=make_api_response([tag_data], count=1, type_name="Tag"))
        )

        pd_api = ProcessData(mock_client)
        result = pd_api.get_tag_details(tag_id)

        assert isinstance(result, Tag)
        assert result.tag_id == tag_id
        assert result.name == "PressureTag"


class TestValidateQuerySize:
    """Tests for the _validate_query_size helper."""

    def test_zero_interval_skips_size_check(self):
        """_validate_query_size should return True (skip check) when interval <= 0 (raw data)."""
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, tzinfo=timezone.utc)
        # interval=0 represents raw data — no size limit applies
        assert _validate_query_size(tag_count=1000, start_time=start, end_time=end, interval=0) is True

    @respx.mock
    def test_write_tag_data_chunks(self, mock_client):
        """write_tag_data should chunk data when exceeding limit."""
        server_id = "33333333-3333-3333-3333-333333333333"

        respx.post(f"{BASE_URL}/v1/processdata/write").mock(
            return_value=Response(200, json=make_api_response([{"TagId": "tag1", "HttpCode": 200}], count=1))
        )

        pd_api = ProcessData(mock_client)

        now = datetime.now(timezone.utc)
        # 35000 points, chunk limit is 30000 -> 2 chunks
        timestamps = [now + timedelta(minutes=i) for i in range(35000)]
        values = [float(i) for i in range(35000)]
        statuses = [0] * 35000

        tag_data = [TagData(tag_id="tag1", timestamps=timestamps, values=values, statuses=statuses)]

        pd_api.write_tag_data(server_id, "1min", tag_data)

        assert len(respx.calls) == 2


class TestGetDataForRangeEdgeCases:
    """Tests for ProcessData.get_data_for_range() error paths."""

    def _mock_archives(self, server_id: str, name: str = "1min", interval: int = 60):
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": name, "Interval": interval}], count=1, type_name="ListArchiveResult"),
            )
        )

    def test_invalid_time_range_raises(self, mock_client):
        """get_data_for_range should raise ValueError when start > end."""
        pd_api = ProcessData(mock_client)
        start = datetime(2024, 2, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="Start time must be before end time"):
            pd_api.get_data_for_range("server-id", start, end, ["tag-id"], "1min")

    @respx.mock
    def test_archive_not_found_raises(self, mock_client):
        """get_data_for_range should raise ValueError when the archive name is not found."""
        server_id = "33333333-3333-3333-3333-333333333333"
        # Mock archives with a different archive name than requested
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": "60min", "Interval": 3600}], count=1),
            )
        )

        pd_api = ProcessData(mock_client)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)

        with pytest.raises(ValueError, match="Archive `1min` not found"):
            pd_api.get_data_for_range(server_id, start, end, ["tag-id"], "1min")

    @respx.mock
    def test_query_too_large_raises_when_chunking_disabled(self, mock_client):
        """get_data_for_range(chunk=False) should raise QuerySizeError when point count exceeds limit."""
        server_id = "33333333-3333-3333-3333-333333333333"
        # interval=60s, 1 day range, 500 tags → 720,000 points, over the 250,000 limit
        self._mock_archives(server_id, name="1min", interval=60)
        query_route = respx.post(f"{BASE_URL}/v1/processdata/query")

        pd_api = ProcessData(mock_client)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 1, 2, tzinfo=timezone.utc)
        tag_ids = [f"tag-{i}" for i in range(500)]

        with pytest.raises(QuerySizeError, match="Query size exceeds limit") as exc_info:
            pd_api.get_data_for_range(server_id, start, end, tag_ids, "1min", chunk=False)

        err = exc_info.value
        # Typed, but still catchable by pre-existing `except ValueError` handlers.
        assert isinstance(err, AtonixError)
        assert isinstance(err, ValueError)
        assert err.limit == _READ_CHUNK_LIMIT
        assert err.tag_count == 500
        assert err.timestamps_per_tag == 1440
        assert err.total_points == 720_000
        assert not query_route.called

    @respx.mock
    def test_query_too_large_chunks_by_tag(self, mock_client):
        """get_data_for_range should split an oversized many-tag query into tag groups."""
        server_id = "33333333-3333-3333-3333-333333333333"
        self._mock_archives(server_id, name="1min", interval=60)
        route = respx.post(f"{BASE_URL}/v1/processdata/query").mock(side_effect=query_echo_side_effect)

        pd_api = ProcessData(mock_client)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(minutes=45_000)
        tag_ids = [f"tag-{i}" for i in range(500)]

        result = pd_api.get_data_for_range(server_id, start, end, tag_ids, "1min")

        # 250,000 // 45,001 = 5 tags per query → 100 queries
        assert route.call_count == 100
        for call in route.calls:
            payload = json.loads(call.request.content)
            assert len(payload["TagIds"]) == 5
            assert payload["Start"] == start.isoformat()
            assert payload["End"] == end.isoformat()
        assert [r.tag_id for r in result] == tag_ids

    @respx.mock
    def test_query_too_large_chunks_by_time_and_merges(self, mock_client):
        """A single tag over the limit should be split into time windows and reassembled without duplicates."""
        server_id = "33333333-3333-3333-3333-333333333333"
        self._mock_archives(server_id, name="1min", interval=60)
        route = respx.post(f"{BASE_URL}/v1/processdata/query").mock(side_effect=query_echo_side_effect)

        pd_api = ProcessData(mock_client)
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(minutes=300_000)

        result = pd_api.get_data_for_range(server_id, start, end, ["tag-0"], "1min")

        assert route.call_count == 2
        payloads = [json.loads(c.request.content) for c in route.calls]
        assert payloads[0]["Start"] == start.isoformat()
        assert payloads[0]["End"] == payloads[1]["Start"]
        assert payloads[1]["End"] == end.isoformat()

        assert len(result) == 1
        boundary = datetime.fromisoformat(payloads[0]["End"])
        # Shared boundary point appears once.
        assert result[0].timestamps == [start, boundary, end]
        assert result[0].values == [1.0, 2.0, 2.0]
        assert result[0].statuses == [0, 0, 0]

    @respx.mock
    def test_api_failure_response_raises(self, mock_client):
        """get_data_for_range should propagate error when the API returns Success=False.

        The AtonixClient._handle_response intercepts Success=False on HTTP 200 and raises
        APIError before the response data reaches processdata, so APIError is what propagates.
        """
        from atonix.exceptions import APIError

        server_id = "33333333-3333-3333-3333-333333333333"
        self._mock_archives(server_id)

        respx.post(f"{BASE_URL}/v1/processdata/query").mock(
            return_value=Response(200, json={"Success": False, "Message": "Query failed", "Results": []})
        )

        pd_api = ProcessData(mock_client)
        start = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 1, tzinfo=timezone.utc)

        with pytest.raises(APIError):
            pd_api.get_data_for_range(server_id, start, end, ["tag-id"], "1min")

    @respx.mock
    def test_non_2xx_tag_http_code_is_logged(self, mock_client):
        """get_data_for_range should log but not raise when a tag returns non-2xx http_code."""
        server_id = "33333333-3333-3333-3333-333333333333"
        tag_id = "44444444-4444-4444-4444-444444444444"
        self._mock_archives(server_id)

        data_response = {
            "Success": True,
            "StatusCode": 200,
            "Results": [
                {
                    "TagId": tag_id,
                    "HttpCode": 404,
                    "Data": {"Timestamps": [], "Values": [], "Statuses": []},
                }
            ],
        }
        respx.post(f"{BASE_URL}/v1/processdata/query").mock(return_value=Response(200, json=data_response))

        pd_api = ProcessData(mock_client)
        start = datetime(2024, 1, 15, tzinfo=timezone.utc)
        end = datetime(2024, 1, 15, 1, tzinfo=timezone.utc)

        # Should not raise — just logs the error
        result = pd_api.get_data_for_range(server_id, start, end, [tag_id], "1min")
        assert len(result) == 1
        assert result[0].http_code == 404


class TestPayloadLogging:
    """Tests for time-series payload logging redaction (issue #43)."""

    def _mock_archives(self, server_id: str) -> None:
        respx.get(f"{BASE_URL}/v1/processdata/servers/{server_id}/archives").mock(
            return_value=Response(
                200,
                json=make_api_response([{"Name": "1min", "Interval": 60}], count=1, type_name="ListArchiveResult"),
            )
        )

    def _mock_query(self, tag_id: str) -> None:
        data_response = {
            "Success": True,
            "StatusCode": 200,
            "Results": [
                {
                    "TagId": tag_id,
                    "HttpCode": 200,
                    "Data": {
                        "Timestamps": [
                            "2024-01-15T12:00:00.000Z",
                            "2024-01-15T12:01:00.000Z",
                            "2024-01-15T12:02:00.000Z",
                        ],
                        "Values": [123456.789, 234567.89, 345678.901],
                        "Statuses": [0, 0, 0],
                    },
                }
            ],
        }
        respx.post(f"{BASE_URL}/v1/processdata/query").mock(return_value=Response(200, json=data_response))

    @respx.mock
    def test_default_logs_summary_not_raw_values(self, mock_client, monkeypatch, caplog):
        """By default, DEBUG logs must not contain raw timestamps/values."""
        monkeypatch.delenv("ATONIX_LOG_PAYLOADS", raising=False)
        server_id = "33333333-3333-3333-3333-333333333333"
        tag_id = "44444444-4444-4444-4444-444444444444"
        self._mock_archives(server_id)
        self._mock_query(tag_id)

        pd_api = ProcessData(mock_client)
        with caplog.at_level("DEBUG", logger="atonix.processdata"):
            pd_api.get_data_for_range(
                server_id,
                datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc),
                [tag_id],
                "1min",
            )

        log_text = "\n".join(r.getMessage() for r in caplog.records)
        # Raw values must not leak.
        assert "123456.789" not in log_text
        assert "234567.89" not in log_text
        assert "2024-01-15T12:00:00" not in log_text
        # Summary must include counts.
        assert "tags=1" in log_text
        assert "points=3" in log_text

    @respx.mock
    def test_opt_in_logs_full_payload(self, mock_client, monkeypatch, caplog):
        """With ATONIX_LOG_PAYLOADS=1, the full payload is logged at DEBUG."""
        monkeypatch.setenv("ATONIX_LOG_PAYLOADS", "1")
        server_id = "33333333-3333-3333-3333-333333333333"
        tag_id = "44444444-4444-4444-4444-444444444444"
        self._mock_archives(server_id)
        self._mock_query(tag_id)

        pd_api = ProcessData(mock_client)
        with caplog.at_level("DEBUG", logger="atonix.processdata"):
            pd_api.get_data_for_range(
                server_id,
                datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
                datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc),
                [tag_id],
                "1min",
            )

        log_text = "\n".join(r.getMessage() for r in caplog.records)
        assert "123456.789" in log_text

    def test_payload_logging_enabled_truthy_values(self, monkeypatch):
        from atonix.processdata import _payload_logging_enabled

        for val in ["1", "true", "TRUE", "Yes", "on"]:
            monkeypatch.setenv("ATONIX_LOG_PAYLOADS", val)
            assert _payload_logging_enabled() is True, val

        for val in ["0", "false", "no", "off", ""]:
            monkeypatch.setenv("ATONIX_LOG_PAYLOADS", val)
            assert _payload_logging_enabled() is False, val

        monkeypatch.delenv("ATONIX_LOG_PAYLOADS", raising=False)
        assert _payload_logging_enabled() is False


class TestPlanReadChunks:
    """Tests for the _plan_read_chunks helper."""

    @staticmethod
    def _assert_within_limit(chunks, interval):
        for tags, start, end in chunks:
            points_per_tag = (end - start).total_seconds() / interval + 1
            assert points_per_tag * len(tags) <= _READ_CHUNK_LIMIT

    def test_wide_query_splits_by_tag(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = start + timedelta(minutes=45_000)
        tag_ids = [f"tag-{i}" for i in range(500)]

        chunks = _plan_read_chunks(tag_ids, start, end, 60)

        self._assert_within_limit(chunks, 60)
        assert all((s, e) == (start, end) for _, s, e in chunks)
        assert [t for tags, _, _ in chunks for t in tags] == tag_ids

    def test_long_query_splits_by_time(self):
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, tzinfo=timezone.utc)  # 527,040 minutes

        chunks = _plan_read_chunks(["tag-0", "tag-1"], start, end, 60)

        self._assert_within_limit(chunks, 60)
        windows = sorted({(s, e) for _, s, e in chunks})
        assert windows[0][0] == start
        assert windows[-1][1] == end
        # Windows are contiguous.
        assert all(a[1] == b[0] for a, b in pairwise(windows))
        # Every tag is queried in every window.
        for window in windows:
            assert sorted(t for tags, s, e in chunks if (s, e) == window for t in tags) == ["tag-0", "tag-1"]


class TestMergeTagResults:
    """Tests for the _merge_tag_results helper."""

    def test_preserves_request_order_and_keeps_errors(self):
        t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
        t1 = t0 + timedelta(minutes=1)
        t2 = t0 + timedelta(minutes=2)
        chunk_a = [
            TagData(tag_id="b", http_code=200, timestamps=[t0, t1], values=[1.0, 2.0], statuses=[0, 0]),
            TagData(tag_id="a", http_code=200, timestamps=[t0], values=[5.0], statuses=[0]),
        ]
        chunk_b = [
            TagData(tag_id="b", http_code=200, timestamps=[t1, t2], values=[2.0, 3.0], statuses=[0, 1]),
            TagData(tag_id="a", http_code=404, error="not found"),
        ]

        merged = _merge_tag_results(["a", "b"], [chunk_a, chunk_b])

        assert [m.tag_id for m in merged] == ["a", "b"]
        assert merged[0].http_code == 404
        assert merged[0].error == "not found"
        assert merged[0].values == [5.0]
        assert merged[1].timestamps == [t0, t1, t2]
        assert merged[1].values == [1.0, 2.0, 3.0]
        assert merged[1].statuses == [0, 0, 1]
        # Inputs are not mutated.
        assert chunk_a[0].timestamps == [t0, t1]
