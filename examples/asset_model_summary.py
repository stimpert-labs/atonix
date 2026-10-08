# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Asset-Centric Model Summary Example - Atonix Python Client

This example demonstrates how to retrieve model information at the asset level:
- Listing all models for an asset (including child assets)
- Getting the alert states for all models in an asset hierarchy
- Retrieving all model actions for an asset within a specific timeframe
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from atonix import AtonixClient

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    """Main example function."""
    try:
        # Initialize the client
        logger.info("Initializing Atonix client...")
        client = AtonixClient()

        # 1. Choose an asset
        if os.getenv("ASSET_ID"):
            target_asset = client.assets.get_asset_details(os.getenv("ASSET_ID"))
        else:
            logger.info("Fetching top-level assets...")
            top_assets = list(client.assets.get_top())

            if not top_assets:
                logger.warning("No assets found. Cannot proceed.")
                return
            target_asset = top_assets[0]

        logger.info(target_asset)
        logger.info(f"Targeting asset: {target_asset.abbrev} (ID: {target_asset.id})")

        # 2. Get ALL models for this asset and its descendants
        try:
            logger.info(f"Fetching all models for '{target_asset.abbrev}' and children...")
            all_models = list(client.models.get_models(target_asset.id, include_descendants=True))
            logger.info(f"Found {len(all_models)} total model(s) in hierarchy")
        except Exception as e:
            logger.error(f"Failed to fetch models: {e}")
            all_models = []

        # 3. Get states for all models in the asset hierarchy
        # This endpoint is unique to this example and demonstrates bulk state retrieval
        try:
            logger.info("Retrieving states for all models in asset hierarchy...")
            model_states = list(client.models.get_model_states_by_asset(target_asset.id, include_descendants=True))
            logger.info(f"Retrieved states for {len(model_states)} model(s)")

            # Summarize states
            active_count = sum(1 for s in model_states if s.active)
            alert_count = sum(1 for s in model_states if s.active_alerts)

            logger.info("Model Summary:")
            logger.info(f"  - Total processed: {len(model_states)}")
            logger.info(f"  - Currently Running (Active): {active_count}")
            logger.info(f"  - Models with Active Alerts: {alert_count}")
        except Exception as e:
            logger.error(f"Failed to fetch model states (bulk): {e}")

        # 4. Get all actions for the asset hierarchy in a date range
        try:
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=7)  # Last week

            logger.info(f"\nRetrieving all model actions in hierarchy since {start_date.date()}...")
            asset_actions = list(
                client.models.get_model_actions_by_asset(
                    target_asset.id, changed_after=start_date, changed_before=end_date, include_descendants=True
                )
            )

            logger.info(f"Found {len(asset_actions)} total actions across all models")

            # Display the first few actions
            for i, action in enumerate(asset_actions[:10], 1):
                logger.info(f"  {i}. Model ID: {action.model_id}")
                logger.info(f"     Action: {action.action_type} by {action.changed_by}")
                logger.info(f"     Date: {action.change_date}, Note: {action.action_note[:50]}...")
        except Exception as e:
            logger.error(f"Failed to fetch actions (bulk): {e}")

        logger.info("\n✓ Asset-centric model example completed!")

    except Exception as e:
        logger.error(f"Fatal error occurred: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
