# Issues

The [`Issues`][atonix.Issues] resource (`client.issues`) lists, creates, and updates issues and
their keywords and discussion entries.

## Listing issues

=== "Sync"

    ```python
    from datetime import datetime, timezone

    for issue in client.issues.get_issues(
        asset_id="asset-guid",
        status="open",
        include_descendants=True,
        changed_after=datetime(2025, 1, 1, tzinfo=timezone.utc),
    ):
        print(issue.title)
    ```

=== "Async"

    ```python
    from datetime import datetime, timezone

    async for issue in client.issues.get_issues(
        asset_id="asset-guid",
        status="open",
        include_descendants=True,
        changed_after=datetime(2025, 1, 1, tzinfo=timezone.utc),
    ):
        print(issue.title)
    ```

## Getting one issue

=== "Sync"

    ```python
    issue = client.issues.get_issue("issue-guid")
    print(issue.title, issue.issue_status)
    ```

=== "Async"

    ```python
    issue = await client.issues.get_issue("issue-guid")
    print(issue.title, issue.issue_status)
    ```

## Creating and updating

!!! warning
    These calls change data in a live tenant. Try them against a non-production environment first.

Build an [`IssueCreate`][atonix.object_models.issues.IssueCreate] to create an issue, and an
[`IssuePatch`][atonix.object_models.issues.IssuePatch] to change one. Fields left out of a patch
aren't touched.

=== "Sync"

    ```python
    from atonix.object_models.issues import IssueCreate, IssuePatch

    issue = client.issues.create_issue(
        IssueCreate(
            asset_id="asset-guid",
            title="High vibration on pump 1",
            category_desc="Maintenance",
            issue_class_type_desc="Mechanical",
            priority="High",
        )
    )

    client.issues.patch_issue(issue.id, IssuePatch(priority="Low"))
    ```

=== "Async"

    ```python
    from atonix.object_models.issues import IssueCreate, IssuePatch

    issue = await client.issues.create_issue(
        IssueCreate(
            asset_id="asset-guid",
            title="High vibration on pump 1",
            category_desc="Maintenance",
            issue_class_type_desc="Mechanical",
            priority="High",
        )
    )

    await client.issues.patch_issue(issue.id, IssuePatch(priority="Low"))
    ```

## Keywords and discussion

=== "Sync"

    ```python
    from atonix.object_models.issues import IssueDiscussionEntryCreate

    client.issues.add_keyword("issue-guid", "vibration")

    for kw in client.issues.get_keywords("issue-guid"):
        print(kw.keyword_desc)

    for entry in client.issues.get_discussion_entries("issue-guid"):
        print(entry.title)

    # Accepts keyword strings or IssueKeyword objects from get_keywords().
    client.issues.delete_keywords("issue-guid", ["vibration"])

    entry = client.issues.create_discussion_entry(
        "issue-guid",
        IssueDiscussionEntryCreate(title="Inspection", contents="Bearing replaced."),
    )
    ```

=== "Async"

    ```python
    from atonix.object_models.issues import IssueDiscussionEntryCreate

    await client.issues.add_keyword("issue-guid", "vibration")

    async for kw in client.issues.get_keywords("issue-guid"):
        print(kw.keyword_desc)

    async for entry in client.issues.get_discussion_entries("issue-guid"):
        print(entry.title)

    await client.issues.delete_keywords("issue-guid", ["vibration"])

    entry = await client.issues.create_discussion_entry(
        "issue-guid",
        IssueDiscussionEntryCreate(title="Inspection", contents="Bearing replaced."),
    )
    ```

To attach files, list their names in `attachment_files`. The created entry's
`attachment_uploads` then holds a temporary upload link (`temporary_link`, URL-encoded) per
file. The client doesn't upload the files for you. Existing attachments come back on
`get_discussion_entries()` as `attachments`, each with a temporary download link.
