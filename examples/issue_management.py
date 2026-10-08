# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Issue Management Example - Atonix Python Client

This example demonstrates:
- Listing issues for an asset
- Getting issue details
- Creating new issues
- Updating existing issues
- Working with issue keywords
"""

import logging
import os

from atonix import AtonixClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main example function."""
    try:
        # Initialize client
        logger.info("Initializing Atonix client...")
        client = AtonixClient()

        # First, we need to get an asset to work with
        if os.getenv("ASSET_ID"):
            target_asset = client.assets.get_asset_details(os.getenv("ASSET_ID"))
        else:
            logger.info("Fetching top-level assets...")
            top_assets = list(client.assets.get_top(take=10))
            if not top_assets:
                logger.warning("No assets found. Cannot proceed.")
                return
            target_asset = top_assets[0]

        # Use the first asset
        logger.info(f"Using asset: {target_asset.abbrev} (ID: {target_asset.id})")

        # Example 1: List issues for the asset
        logger.info(f"Fetching issues for '{target_asset.abbrev}'...")
        issues = list(client.issues.get_issues(asset_id=target_asset.id))
        logger.info(f"Found {len(issues)} issue(s)")

        # Display issues
        for i, issue in enumerate(issues[:5], 1):  # Show first 5
            logger.info(f"  {i}. {issue.title} (ID: {issue.id})")

        # Example 2: Get full details for a specific issue
        if issues:
            first_issue = issues[0]
            logger.info(f"Getting details for issue: '{first_issue.title}'...")
            issue_details = client.issues.get_issue(first_issue.id)
            logger.info(f"  Status: {issue_details.issue_status}")
            logger.info(f"  Priority: {issue_details.priority}")
            logger.info(f"  Category: {issue_details.category_desc}")
            logger.info(f"  Created by: {issue_details.created_by}")
            logger.info(f"  Created: {issue_details.create_date}")

            # Example 3: Get keywords for the issue
            logger.info(f"Fetching keywords for issue '{first_issue.title}'...")
            keywords = list(client.issues.get_keywords(first_issue.id))
            if keywords:
                logger.info(f"  Keywords: {', '.join([k.keyword_desc for k in keywords])}")
            else:
                logger.info("  No keywords found")

            # # Example 4: Add a keyword to the issue
            # logger.info("Adding keyword 'Example' to issue...")
            # try:
            #     new_keyword = client.issues.add_keyword(first_issue.id, "Example")
            #     logger.info(f"  ✓ Added keyword: {new_keyword.keyword_desc}")
            # except Exception as e:
            #     logger.warning(f"  Could not add keyword (may already exist): {e}")

            # # Example 5: Get discussion entries
            # logger.info("Fetching discussion entries for issue...")
            # discussions = client.issues.get_discussion_entries(first_issue.id)
            # logger.info(f"Found {len(discussions)} discussion entry/entries")
            # for i, entry in enumerate(discussions[:3], 1):
            #     logger.info(f"  {i}. {entry.title} - {entry.created_by}")

        # # Example 6: Create a new issue
        # logger.info(f"Creating a new issue for asset '{asset.abbrev}'...")
        # new_issue_data = IssueCreate(
        #     asset_id=asset.id,
        #     title="Example Issue - Performance Degradation",
        #     category_desc="Performance",
        #     issue_class_type_desc="Operational",
        #     priority="Medium",
        #     short_summary="Equipment showing signs of reduced efficiency",
        #     full_summary="The equipment has been operating below optimal performance levels. "
        #                 "Investigation needed to determine root cause."
        # )

        # try:
        #     created_issue = client.issues.create_issue(new_issue_data)
        #     logger.info(f"  ✓ Created issue: {created_issue.title} (ID: {created_issue.id})")

        #     # Example 7: Update the issue we just created
        #     logger.info("Updating issue priority...")
        #     issue_update = IssuePatch(
        #         priority="High",
        #         full_summary=created_issue.full_summary + " Update: Marked as high priority."
        #     )

        #     updated_issue = client.issues.patch_issue(created_issue.id, issue_update)
        #     logger.info(f"  ✓ Updated issue priority to: {updated_issue.priority}")

        # except Exception as e:
        #     logger.error(f"  Could not create/update issue: {e}")

        # Example 8: Filter issues by status
        logger.info("Fetching only 'Open' issues...")
        open_issues = list(client.issues.get_issues(asset_id=target_asset.id, status="Open"))
        logger.info(f"Found {len(open_issues)} open issue(s)")

        # Example 9: Include issues from child assets
        logger.info("Fetching issues including descendants...")
        all_issues = list(client.issues.get_issues(asset_id=target_asset.id, include_descendants=True))
        logger.info(f"Found {len(all_issues)} total issue(s) (including children)")

        # Example 10: Filter issues by date range
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        logger.info(f"Fetching issues changed after {cutoff.date()}...")
        recent_issues = list(
            client.issues.get_issues(
                asset_id=target_asset.id,
                changed_after=cutoff,
            )
        )
        logger.info(f"Found {len(recent_issues)} recently changed issue(s)")

        logger.info("✓ All examples completed successfully!")

    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
