# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any

from atonix.base import AsyncBaseResource, BaseResource, Op, Pager, _first_result, _to_utc_ms_str, call, single
from atonix.object_models.issues import (
    BareIssue,
    Issue,
    IssueCreate,
    IssueDiscussionEntry,
    IssueDiscussionEntryCreate,
    IssueDiscussionEntryDetails,
    IssueKeyword,
    IssuePatch,
    IssueResolutionStatus,
)

logger = logging.getLogger(__name__)


def _keywords_body(keywords: list[str | IssueKeyword]) -> list[dict[str, str]]:
    """Build the DELETE /keywords body: an array of IssueKeyword objects, per the spec."""
    return [{"KeywordDesc": kw.keyword_desc if isinstance(kw, IssueKeyword) else kw} for kw in keywords]


# --- Shared request logic (used by both Issues and AsyncIssues) ---


def _issues(
    asset_id: str,
    include_descendants: bool,
    status: str | None,
    changed_after: datetime | None,
    changed_before: datetime | None,
    skip: int,
    take: int,
) -> Pager[BareIssue]:
    params: dict[str, Any] = {
        "assetId": asset_id,
        "includeDescendants": str(include_descendants).lower(),
    }
    if status:
        params["status"] = status
    if changed_after:
        params["changedAfter"] = _to_utc_ms_str(changed_after)
    if changed_before:
        params["changedBefore"] = _to_utc_ms_str(changed_before)
    return Pager("/v1/issues", BareIssue, params=params, skip=skip, take=take)


def _issue(issue_id: str) -> Op[Issue]:
    return single(f"/v1/issues/{issue_id}", Issue)


def _create_issue(issue: IssueCreate) -> Op[Issue]:
    logger.debug("Creating issue: %s", issue.title)
    data = yield from call("POST", "/v1/issues", json=issue.model_dump(by_alias=True, exclude_none=True))
    return _first_result(Issue, data, "Failed to retrieve created issue details from response")


def _patch_issue(issue_id: str, patch: IssuePatch) -> Op[Issue]:
    logger.debug("Patching issue %s", issue_id)
    data = yield from call("PATCH", f"/v1/issues/{issue_id}", json=patch.model_dump(by_alias=True, exclude_none=True))
    return _first_result(Issue, data, f"No result returned when patching issue {issue_id}")


def _keywords(issue_id: str, skip: int, take: int) -> Pager[IssueKeyword]:
    return Pager(f"/v1/issues/{issue_id}/keywords", IssueKeyword, skip=skip, take=take)


def _add_keyword(issue_id: str, keyword_desc: str) -> Op[IssueKeyword]:
    logger.debug("Adding keyword '%s' to issue %s", keyword_desc, issue_id)
    data = yield from call("POST", f"/v1/issues/{issue_id}/keywords", json={"KeywordDesc": keyword_desc})
    return _first_result(IssueKeyword, data, f"No result returned when adding keyword to issue {issue_id}")


def _delete_keywords(issue_id: str, keywords: list[str | IssueKeyword]) -> Op[None]:
    if not keywords:
        return
    body = _keywords_body(keywords)
    logger.debug("Deleting keywords from issue %s: %s", issue_id, body)
    yield from call("DELETE", f"/v1/issues/{issue_id}/keywords", json=body)


def _create_discussion_entry(issue_id: str, entry: IssueDiscussionEntryCreate) -> Op[IssueDiscussionEntry]:
    logger.debug("Creating discussion entry on issue %s: %s", issue_id, entry.title)
    data = yield from call(
        "POST",
        f"/v1/issues/{issue_id}/discussionentries",
        json=entry.model_dump(by_alias=True, exclude_none=True),
    )
    return _first_result(
        IssueDiscussionEntry, data, f"No result returned when creating discussion entry on issue {issue_id}"
    )


def _discussion_entries(issue_id: str, skip: int, take: int) -> Pager[IssueDiscussionEntryDetails]:
    return Pager(f"/v1/issues/{issue_id}/discussionentries", IssueDiscussionEntryDetails, skip=skip, take=take)


def _resolution_statuses(category_id: int) -> Pager[IssueResolutionStatus]:
    return Pager("/v1/issues/resolutionstatuses", IssueResolutionStatus, params={"categoryId": category_id})


# --- Public resources ---


class Issues(BaseResource):
    """Interface for the Atonix Issues API."""

    def get_issues(
        self,
        asset_id: str,
        include_descendants: bool = False,
        status: str | None = None,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        skip: int = 0,
        take: int = 500,
    ) -> Iterator[BareIssue]:
        """
        List issues for a specific asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            include_descendants: Whether to include issues from child assets.
            status: Filter by issue status (e.g., 'open', 'closed').
            changed_after: Filter issues changed on or after this date.
            changed_before: Filter issues changed on or before this date.
            skip: Number of issues to skip for initial offset.
            take: Number of issues to retrieve per API page (max 500).

        Yields:
            BareIssue objects one by one.
        """
        return self._iterate(_issues(asset_id, include_descendants, status, changed_after, changed_before, skip, take))

    def get_issue(self, issue_id: str) -> Issue:
        """
        Get full details for a single issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.

        Returns:
            An Issue object.
        """
        return self._run(_issue(issue_id))

    def create_issue(self, issue: IssueCreate) -> Issue:
        """
        Create a new issue.

        Args:
            issue: An IssueCreate object containing the issue details.

        Returns:
            The created Issue object (full details).
        """
        return self._run(_create_issue(issue))

    def patch_issue(self, issue_id: str, patch: IssuePatch) -> Issue:
        """
        Update an existing issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            patch: An IssuePatch object containing the fields to update.

        Returns:
            The updated Issue object.
        """
        return self._run(_patch_issue(issue_id, patch))

    def get_keywords(self, issue_id: str, skip: int = 0, take: int = 50) -> Iterator[IssueKeyword]:
        """
        Get keywords associated with an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            skip: Number of keywords to skip for initial offset.
            take: Number of keywords to retrieve per API page.

        Yields:
            IssueKeyword objects one by one.
        """
        return self._iterate(_keywords(issue_id, skip, take))

    def add_keyword(self, issue_id: str, keyword_desc: str) -> IssueKeyword:
        """
        Add a keyword to an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            keyword_desc: The text of the keyword to add.

        Returns:
            The created IssueKeyword object.
        """
        return self._run(_add_keyword(issue_id, keyword_desc))

    def delete_keywords(self, issue_id: str, keywords: list[str | IssueKeyword]) -> None:
        """
        Delete keywords from an issue.

        The API takes the keywords as a JSON array in the DELETE request body;
        it has no per-keyword or query-string variant.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            keywords: Keyword descriptions, or IssueKeyword objects (e.g. from
                ``get_keywords``), to remove. An empty list sends no request.
        """
        self._run(_delete_keywords(issue_id, keywords))

    def create_discussion_entry(self, issue_id: str, entry: IssueDiscussionEntryCreate) -> IssueDiscussionEntry:
        """
        Add a discussion entry to an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            entry: An IssueDiscussionEntryCreate object with the entry details.

        Returns:
            The created IssueDiscussionEntry. If ``entry.attachment_files`` was
            set, its ``attachment_uploads`` holds a temporary upload link per file.
        """
        return self._run(_create_discussion_entry(issue_id, entry))

    def get_discussion_entries(
        self, issue_id: str, skip: int = 0, take: int = 50
    ) -> Iterator[IssueDiscussionEntryDetails]:
        """
        Get discussion entries for an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            skip: Number of entries to skip.
            take: Number of entries to retrieve per page.

        Yields:
            IssueDiscussionEntryDetails objects one by one.
        """
        return self._iterate(_discussion_entries(issue_id, skip, take))

    def get_resolution_statuses(self, category_id: int) -> Iterator[IssueResolutionStatus]:
        """
        List of resolution statuses for a specific Category Id.

        Args:
            category_id: The category ID to filter by.

        Yields:
            IssueResolutionStatus objects one by one.
        """
        return self._iterate(_resolution_statuses(category_id))


class AsyncIssues(AsyncBaseResource):
    """Async interface for the Atonix Issues API."""

    def get_issues(
        self,
        asset_id: str,
        include_descendants: bool = False,
        status: str | None = None,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        skip: int = 0,
        take: int = 500,
    ) -> AsyncIterator[BareIssue]:
        """
        List issues for a specific asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.
            include_descendants: Whether to include issues from child assets.
            status: Filter by issue status (e.g., 'open', 'closed').
            changed_after: Filter issues changed on or after this date.
            changed_before: Filter issues changed on or before this date.
            skip: Number of issues to skip for initial offset.
            take: Number of issues to retrieve per API page (max 500).

        Returns:
            An async iterator of BareIssue objects.
        """
        return self._iterate(_issues(asset_id, include_descendants, status, changed_after, changed_before, skip, take))

    async def get_issue(self, issue_id: str) -> Issue:
        """
        Get full details for a single issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.

        Returns:
            An Issue object.
        """
        return await self._run(_issue(issue_id))

    async def create_issue(self, issue: IssueCreate) -> Issue:
        """
        Create a new issue.

        Args:
            issue: An IssueCreate object containing the issue details.

        Returns:
            The created Issue object (full details).
        """
        return await self._run(_create_issue(issue))

    async def patch_issue(self, issue_id: str, patch: IssuePatch) -> Issue:
        """
        Update an existing issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            patch: An IssuePatch object containing the fields to update.

        Returns:
            The updated Issue object.
        """
        return await self._run(_patch_issue(issue_id, patch))

    def get_keywords(self, issue_id: str, skip: int = 0, take: int = 50) -> AsyncIterator[IssueKeyword]:
        """
        Get keywords associated with an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            skip: Number of keywords to skip for initial offset.
            take: Number of keywords to retrieve per API page.

        Returns:
            An async iterator of IssueKeyword objects.
        """
        return self._iterate(_keywords(issue_id, skip, take))

    async def add_keyword(self, issue_id: str, keyword_desc: str) -> IssueKeyword:
        """
        Add a keyword to an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            keyword_desc: The text of the keyword to add.

        Returns:
            The created IssueKeyword object.
        """
        return await self._run(_add_keyword(issue_id, keyword_desc))

    async def delete_keywords(self, issue_id: str, keywords: list[str | IssueKeyword]) -> None:
        """
        Delete keywords from an issue.

        The API takes the keywords as a JSON array in the DELETE request body;
        it has no per-keyword or query-string variant.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            keywords: Keyword descriptions, or IssueKeyword objects (e.g. from
                ``get_keywords``), to remove. An empty list sends no request.
        """
        await self._run(_delete_keywords(issue_id, keywords))

    async def create_discussion_entry(self, issue_id: str, entry: IssueDiscussionEntryCreate) -> IssueDiscussionEntry:
        """
        Add a discussion entry to an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            entry: An IssueDiscussionEntryCreate object with the entry details.

        Returns:
            The created IssueDiscussionEntry. If ``entry.attachment_files`` was
            set, its ``attachment_uploads`` holds a temporary upload link per file.
        """
        return await self._run(_create_discussion_entry(issue_id, entry))

    def get_discussion_entries(
        self, issue_id: str, skip: int = 0, take: int = 50
    ) -> AsyncIterator[IssueDiscussionEntryDetails]:
        """
        Get discussion entries for an issue.

        Args:
            issue_id: The unique identifier (GUID) of the issue.
            skip: Number of entries to skip.
            take: Number of entries to retrieve per page.

        Returns:
            An async iterator of IssueDiscussionEntryDetails objects.
        """
        return self._iterate(_discussion_entries(issue_id, skip, take))

    def get_resolution_statuses(self, category_id: int) -> AsyncIterator[IssueResolutionStatus]:
        """
        List of resolution statuses for a specific Category Id.

        Args:
            category_id: The category ID to filter by.

        Returns:
            An async iterator of IssueResolutionStatus objects.
        """
        return self._iterate(_resolution_statuses(category_id))
