# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for the Issues resource."""

import pytest
import respx
from httpx import Response

from atonix.exceptions import APIError
from atonix.issues import Issues
from atonix.object_models.issues import (
    BareIssue,
    Issue,
    IssueCreate,
    IssueDiscussionEntryDetails,
    IssueKeyword,
    IssuePatch,
    IssueResolutionStatus,
)
from tests.conftest import BASE_URL, make_api_response, make_bare_issues, make_discussion_entries, make_issue


class TestGetIssues:
    """Tests for Issues.get_issues()."""

    @respx.mock
    def test_get_issues_single_page(self, mock_client):
        """get_issues should return issues when count < take."""
        issues_data = make_bare_issues(10)
        respx.get(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response(issues_data, count=10, type_name="BareIssue"))
        )

        issues_api = Issues(mock_client)
        result = list(issues_api.get_issues(asset_id="test-asset-id"))

        assert len(result) == 10
        assert all(isinstance(i, BareIssue) for i in result)

    @respx.mock
    def test_get_issues_pagination(self, mock_client):
        """get_issues should paginate when results exceed max take (500)."""
        # First page
        page1_issues = make_bare_issues(500, start_index=0)
        respx.get(f"{BASE_URL}/v1/issues", params={"skip": 0, "take": 500}).mock(
            return_value=Response(200, json=make_api_response(page1_issues, count=500, type_name="BareIssue"))
        )

        # Second page
        page2_issues = make_bare_issues(100, start_index=500)
        respx.get(f"{BASE_URL}/v1/issues", params={"skip": 500, "take": 500}).mock(
            return_value=Response(200, json=make_api_response(page2_issues, count=100, type_name="BareIssue"))
        )

        issues_api = Issues(mock_client)
        result = list(issues_api.get_issues(asset_id="test-asset-id", take=500))

        assert len(result) == 600
        assert len(respx.calls) == 2


class TestGetIssue:
    """Tests for Issues.get_issue()."""

    @respx.mock
    def test_get_issue_details(self, mock_client):
        """get_issue should return full Issue object."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        issue_data = make_issue(issue_id=issue_id, title="Test Issue")
        respx.get(f"{BASE_URL}/v1/issues/{issue_id}").mock(
            return_value=Response(200, json=make_api_response([issue_data], count=1, type_name="Issue"))
        )

        issues_api = Issues(mock_client)
        result = issues_api.get_issue(issue_id)

        assert isinstance(result, Issue)
        assert result.id == issue_id
        assert result.title == "Test Issue"


class TestKeywords:
    """Tests for keyword-related methods."""

    @respx.mock
    def test_get_keywords(self, mock_client):
        """get_keywords should return keyword list."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        keywords_data = [{"KeywordDesc": "K1"}, {"KeywordDesc": "K2"}]
        respx.get(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(
            return_value=Response(200, json=make_api_response(keywords_data, count=2, type_name="IssueKeyword"))
        )

        issues_api = Issues(mock_client)
        result = list(issues_api.get_keywords(issue_id))

        assert len(result) == 2
        assert all(isinstance(k, IssueKeyword) for k in result)

    @respx.mock
    def test_add_keyword(self, mock_client):
        """add_keyword should POST to API and return created keyword."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        keyword_data = {"KeywordDesc": "NewKeyword"}
        respx.post(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(
            return_value=Response(200, json=make_api_response([keyword_data], count=1, type_name="IssueKeyword"))
        )

        issues_api = Issues(mock_client)
        result = issues_api.add_keyword(issue_id, "NewKeyword")

        assert isinstance(result, IssueKeyword)
        assert result.keyword_desc == "NewKeyword"

    @respx.mock
    def test_delete_keywords(self, mock_client):
        """delete_keywords should send DELETE request."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        route = respx.delete(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(return_value=Response(204))

        issues_api = Issues(mock_client)
        issues_api.delete_keywords(issue_id, ["K1", "K2"])

        assert len(respx.calls) == 1
        assert route.calls.last.request.method == "DELETE"

    @respx.mock
    def test_add_keyword_no_results_raises(self, mock_client):
        """add_keyword should raise APIError when API returns no results."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        respx.post(f"{BASE_URL}/v1/issues/{issue_id}/keywords").mock(
            return_value=Response(200, json=make_api_response([], count=0, type_name="IssueKeyword"))
        )

        issues_api = Issues(mock_client)
        with pytest.raises(APIError):
            issues_api.add_keyword(issue_id, "SomeKeyword")


class TestGetIssuesWithFilters:
    """Tests for Issues.get_issues() with optional filters."""

    @respx.mock
    def test_get_issues_with_status_filter(self, mock_client):
        """get_issues should pass status parameter to API."""
        issues_data = make_bare_issues(3)
        route = respx.get(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response(issues_data, count=3, type_name="BareIssue"))
        )

        issues_api = Issues(mock_client)
        result = list(issues_api.get_issues(asset_id="test-asset-id", status="open"))

        assert len(result) == 3
        assert route.calls.last.request.url.params["status"] == "open"

    @respx.mock
    def test_get_issues_with_changed_after(self, mock_client):
        """get_issues should pass changedAfter parameter to API."""
        from datetime import datetime, timezone

        issues_data = make_bare_issues(2)
        route = respx.get(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response(issues_data, count=2, type_name="BareIssue"))
        )

        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        issues_api = Issues(mock_client)
        result = list(issues_api.get_issues(asset_id="test-asset-id", changed_after=dt))

        assert len(result) == 2
        assert route.calls.last.request.url.params["changedAfter"] == "2025-01-15T12:00:00.000Z"

    @respx.mock
    def test_get_issues_with_changed_before(self, mock_client):
        """get_issues should pass changedBefore parameter to API."""
        from datetime import datetime, timezone

        issues_data = make_bare_issues(2)
        route = respx.get(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response(issues_data, count=2, type_name="BareIssue"))
        )

        dt = datetime(2025, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        issues_api = Issues(mock_client)
        result = list(issues_api.get_issues(asset_id="test-asset-id", changed_before=dt))

        assert len(result) == 2
        assert route.calls.last.request.url.params["changedBefore"] == "2025-06-01T00:00:00.000Z"


class TestCreateIssue:
    """Tests for Issues.create_issue()."""

    @respx.mock
    def test_create_issue_success(self, mock_client):
        """create_issue should POST and return the created Issue."""
        issue_data = make_issue(title="New Issue")
        respx.post(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response([issue_data], count=1, type_name="Issue"))
        )

        issues_api = Issues(mock_client)
        new_issue = IssueCreate(
            asset_id="00000000-0000-0000-0000-000000000001",
            title="New Issue",
            category_desc="Maintenance",
            issue_class_type_desc="Mechanical",
        )
        result = issues_api.create_issue(new_issue)

        assert isinstance(result, Issue)
        assert result.title == "New Issue"

    @respx.mock
    def test_create_issue_no_results_raises(self, mock_client):
        """create_issue should raise APIError when API returns no results."""
        respx.post(f"{BASE_URL}/v1/issues").mock(
            return_value=Response(200, json=make_api_response([], count=0, type_name="Issue"))
        )

        issues_api = Issues(mock_client)
        new_issue = IssueCreate(
            asset_id="00000000-0000-0000-0000-000000000001",
            title="Orphan Issue",
            category_desc="Maintenance",
            issue_class_type_desc="Mechanical",
        )
        with pytest.raises(APIError, match="Failed to retrieve created issue details"):
            issues_api.create_issue(new_issue)


class TestPatchIssue:
    """Tests for Issues.patch_issue()."""

    @respx.mock
    def test_patch_issue_success(self, mock_client):
        """patch_issue should PATCH and return the updated Issue."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        issue_data = make_issue(issue_id=issue_id, title="Updated Title")
        respx.patch(f"{BASE_URL}/v1/issues/{issue_id}").mock(
            return_value=Response(200, json=make_api_response([issue_data], count=1, type_name="Issue"))
        )

        issues_api = Issues(mock_client)
        result = issues_api.patch_issue(issue_id, IssuePatch(title="Updated Title"))

        assert isinstance(result, Issue)
        assert result.title == "Updated Title"

    @respx.mock
    def test_patch_issue_no_results_raises(self, mock_client):
        """patch_issue should raise APIError when API returns no results."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        respx.patch(f"{BASE_URL}/v1/issues/{issue_id}").mock(
            return_value=Response(200, json=make_api_response([], count=0, type_name="Issue"))
        )

        issues_api = Issues(mock_client)
        with pytest.raises(APIError, match="No result returned when patching"):
            issues_api.patch_issue(issue_id, IssuePatch(title="Updated Title"))


class TestDiscussionEntries:
    """Tests for Issues.get_discussion_entries()."""

    @respx.mock
    def test_get_discussion_entries(self, mock_client):
        """get_discussion_entries should return paginated discussion entries."""
        issue_id = "11111111-1111-1111-1111-111111111111"
        entries_data = make_discussion_entries(3)
        respx.get(f"{BASE_URL}/v1/issues/{issue_id}/discussionentries").mock(
            return_value=Response(
                200, json=make_api_response(entries_data, count=3, type_name="IssueDiscussionEntryDetails")
            )
        )

        issues_api = Issues(mock_client)
        result = list(issues_api.get_discussion_entries(issue_id))

        assert len(result) == 3
        assert all(isinstance(e, IssueDiscussionEntryDetails) for e in result)


class TestResolutionStatuses:
    """Tests for Issues.get_resolution_statuses()."""

    @respx.mock
    def test_get_resolution_statuses(self, mock_client):
        """get_resolution_statuses should return statuses filtered by category."""
        statuses_data = [
            {"ResolutionStatus": "Monitoring", "DisplayOrder": 1},
            {"ResolutionStatus": "Resolved", "DisplayOrder": 2},
        ]
        route = respx.get(f"{BASE_URL}/v1/issues/resolutionstatuses").mock(
            return_value=Response(
                200, json=make_api_response(statuses_data, count=2, type_name="IssueResolutionStatus")
            )
        )

        issues_api = Issues(mock_client)
        result = list(issues_api.get_resolution_statuses(category_id=5))

        assert len(result) == 2
        assert all(isinstance(s, IssueResolutionStatus) for s in result)
        assert route.calls.last.request.url.params["categoryId"] == "5"
