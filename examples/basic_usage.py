# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Basic Usage Example - Atonix Python Client

This example demonstrates:
- Connecting to the Atonix API
- Retrieving top-level assets
- Getting asset details
- Navigating the asset hierarchy
"""

import logging

from atonix import AtonixClient

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main example function."""
    try:
        # Initialize the client
        # This automatically loads credentials from environment variables:
        # - ATONIX_API_KEY
        # - ATONIX_PRIVATE_KEY_PATH
        # - ATONIX_PRIVATE_KEY_PASSWORD (optional)
        logger.info("Initializing Atonix client...")
        client = AtonixClient()
        version = client.__version__ if hasattr(client, "__version__") else "unknown"
        logger.info(f"Connected to Atonix (library version: {version})")

        # Example 1: Get top-level assets
        logger.info("Fetching top-level assets...")
        top_assets = list(client.assets.get_top())
        logger.info(f"Found {len(top_assets)} top-level assets")

        # Display top-level assets
        for i, asset in enumerate(top_assets[:5], 1):  # Show first 5
            logger.info(f"  {i}. {asset.abbrev} (ID: {asset.id})")

        # Example 2: Get details for a specific asset
        if top_assets:
            first_asset = top_assets[0]
            logger.info(f"Getting details for '{first_asset.abbrev}'...")
            details = client.assets.get_asset_details(first_asset.id)
            logger.info(f"  Type: {details.asset_type_name}")
            logger.info(f"  Created: {details.create_date}")
            logger.info(f"  Modified: {details.change_date}")

            # Example 3: Get child assets
            logger.info(f"Fetching children of '{first_asset.abbrev}'...")
            children = list(client.assets.get_children(first_asset.id))
            logger.info(f"Found {len(children)} direct children")

            if children:
                for i, child in enumerate(children[:3], 1):  # Show first 3
                    logger.info(f"  {i}. {child.abbrev} (Type: {child.asset_type_name})")

            # Example 4: Get a slice of children (efficiently)
            from itertools import islice

            logger.info("Fetching first 2 children (efficient slice)...")
            first_two = list(islice(client.assets.get_children(first_asset.id), 2))
            logger.info(f"Retrieved {len(first_two)} children using islice")

            # Example 5: Get all descendants (recursive)
            logger.info(f"\nFetching ALL descendants of '{first_asset.abbrev}'...")
            all_descendants = client.assets.get_children(first_asset.id, include_descendants=True)
            logger.info(f"Found {len(all_descendants)} total descendants (recursive)")

    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
