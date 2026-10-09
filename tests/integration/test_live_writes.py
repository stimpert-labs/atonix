# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Integration tests that write to the live Atonix API.

These modify a real issue, so they are opt-in on top of the credentials
needed by the read-only tests (see test_live_api.py):

    ATONIX_TEST_ISSUE_ID: GUID of a throwaway issue the tests may modify.
        Without it, every test here is skipped.
    ATONIX_LIVE_PERMANENT_WRITES: Set to "1" to also run tests whose writes
        cannot be undone through the API (discussion entries have no delete
        endpoint, so each run leaves one behind on the test issue).

Run with:
    export ATONIX_TEST_ISSUE_ID="<issue-guid>"
    uv run pytest tests/integration/test_live_writes.py -m integration -v
"""

import os
import uuid

import pytest

from atonix.object_models.issues import IssueDiscussionEntryCreate

pytestmark = pytest.mark.integration

permanent_writes = pytest.mark.skipif(
    os.environ.get("ATONIX_LIVE_PERMANENT_WRITES") != "1",
    reason="ATONIX_LIVE_PERMANENT_WRITES != 1; skipping a write the API cannot undo",
)


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TestLiveIssueWrites:
    """Write round-trips against a throwaway issue."""

    def test_keyword_add_and_delete(self, live_client, test_issue_id):
        """A keyword added via add_keyword is removed by delete_keywords (cleans up after itself)."""
        keyword = _unique("atonix-live-test")

        live_client.issues.add_keyword(test_issue_id, keyword)
        try:
            present = {k.keyword_desc for k in live_client.issues.get_keywords(test_issue_id)}
            assert keyword in present
        finally:
            live_client.issues.delete_keywords(test_issue_id, [keyword])

        remaining = {k.keyword_desc for k in live_client.issues.get_keywords(test_issue_id)}
        assert keyword not in remaining, f"delete_keywords did not remove {keyword!r}; remove it manually"

    @permanent_writes
    def test_create_discussion_entry(self, live_client, test_issue_id):
        """create_discussion_entry posts an entry that get_discussion_entries then returns."""
        title = _unique("atonix live test")
        entry = live_client.issues.create_discussion_entry(
            test_issue_id,
            IssueDiscussionEntryCreate(
                title=title, contents="Created by the atonix integration suite. Safe to ignore."
            ),
        )

        assert entry.title == title
        assert any(e.title == title for e in live_client.issues.get_discussion_entries(test_issue_id))
