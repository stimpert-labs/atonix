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
    client.issues.add_keyword("issue-guid", "vibration")

    for kw in client.issues.get_keywords("issue-guid"):
        print(kw.keyword_desc)

    for entry in client.issues.get_discussion_entries("issue-guid"):
        print(entry.title)
    ```

=== "Async"

    ```python
    await client.issues.add_keyword("issue-guid", "vibration")

    async for kw in client.issues.get_keywords("issue-guid"):
        print(kw.keyword_desc)

    async for entry in client.issues.get_discussion_entries("issue-guid"):
        print(entry.title)
    ```
