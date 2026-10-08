# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Process Data Query Example - Atonix Python Client

This example demonstrates:
- Finding process data servers
- Listing available tags
- Querying time-series data for a date range
- Working with different archives (time resolutions)
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from atonix import AtonixClient
from atonix.object_models.processdata import Server

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main example function."""
    try:
        # Initialize client
        logger.info("Initializing Atonix client...")
        client = AtonixClient()

        if not os.getenv("SERVER_ID"):
            logger.info("SERVER_ID environment variable not set. Fetching available servers...")
            # Example 1: List available servers
            servers = list(client.process_data.get_servers())
            logger.info(f"Found {len(servers)} server(s)")

            if not servers:
                logger.warning("No servers found. Exiting.")
                return
            # Use the first server
            server = servers[0]
        else:
            server = Server(server_id=os.getenv("SERVER_ID"), name="testing", asset_id="testing")

        logger.info(f"Using server: {server.name} (ID: {server.server_id})")

        # Example 2: List available archives (time resolutions)
        logger.info(f"Fetching available archives for '{server.name}'...")
        archives = list(client.process_data.get_archives(server.server_id))
        logger.info(f"Found {len(archives)} archive(s):")
        for archive in archives:
            logger.info(f"  - {archive.name} (interval: {archive.interval} seconds)")

        # Example 3: Get tags list
        logger.info(f"Fetching tags for server '{server.name}'...")
        tags = list(client.process_data.get_tags_list(server.server_id))
        logger.info(f"Found {len(tags)} tag(s)")

        # Show first few tags
        for i, tag in enumerate(tags[:5], 1):
            logger.info(f"  {i}. {tag.name} - {tag.description}")

        if not tags:
            logger.warning("No tags found. Cannot query data.")
            return

        # Example 4: Efficiently get first 75 tags using islice (lazy loading)
        from itertools import islice

        logger.info("Fetching first 75 tags efficiently...")
        # Note: This will only fetch enough pages to get 75 items (e.g. 2 pages if take=50)
        first_75_tags = list(islice(client.process_data.get_tags_list(server.server_id), 75))
        logger.info(f"Retrieved {len(first_75_tags)} tags (lazy loaded)")

        # Example 5: Query time-series data
        # Select a few tags to query
        selected_tags = tags[:3]  # First 3 tags
        tag_ids = [tag.tag_id for tag in selected_tags]

        # Define time range (last hour)
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=1)

        logger.info(f"Querying data for {len(tag_ids)} tag(s)...")
        logger.info(f"  Time range: {start_time} to {end_time}")
        logger.info(f"  Tags: {[t.name for t in selected_tags]}")

        # Query using 1-minute archive
        data = client.process_data.get_data_for_range(
            server_id=server.server_id,
            start_time=start_time,
            end_time=end_time,
            tag_ids=tag_ids,
            archive="1min",  # Use 1-minute resolution
        )

        logger.info(f"Received data for {len(data)} tag(s):")
        for tag_data in data:
            # Find the corresponding tag name
            tag_name = next((t.name for t in selected_tags if t.tag_id == tag_data.tag_id), "Unknown")
            logger.info(f"  {tag_name}: {len(tag_data.values)} data points")

            # Show first and last values
            if tag_data.values:
                logger.info(f"    First value: {tag_data.values[0]} at {tag_data.timestamps[0]}")
                logger.info(f"    Last value: {tag_data.values[-1]} at {tag_data.timestamps[-1]}")

        # Example 5: Get tag details
        if tags:
            first_tag = tags[0]
            logger.info(f"Getting detailed information for tag '{first_tag.name}'...")
            first_tag = client.process_data.get_tag_details(first_tag.tag_id)
            logger.info(f"  Source: {first_tag.source}")
            logger.info(f"  Engineering Units: {first_tag.eng_unit}")
            logger.info(f"  Last Modified: {first_tag.change_date}")

        logger.info("✓ All examples completed successfully!")

    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
