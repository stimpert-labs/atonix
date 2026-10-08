# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Model Detailed Info Example - Atonix Python Client

This example demonstrates how to drill down into a specific model's details:
- Listing models for an asset
- Retrieving a model's current alert state
- Retrieving a model's configuration
- Retrieving recent actions (events) for a model
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
        target_asset_id = os.getenv("ASSET_ID")
        if target_asset_id:
            logger.info(f"Fetching details for asset ID: {target_asset_id}")
            target_asset = client.assets.get_asset_details(target_asset_id)
        else:
            logger.info("ASSET_ID not set, fetching top-level assets...")
            top_assets = list(client.assets.get_top())
            if not top_assets:
                logger.warning("No assets found. Cannot proceed.")
                return
            target_asset = top_assets[0]

        logger.info(f"Targeting asset: {target_asset.abbrev} (ID: {target_asset.id})")

        # 2. Get models for this asset
        logger.info(f"Fetching models for '{target_asset.abbrev}'...")
        models = list(client.models.get_models(target_asset.id, include_descendants=True))
        logger.info(f"Found {len(models)} model(s)")

        if not models:
            logger.info("No models found for this asset.")
            return

        # Display the models
        for i, model in enumerate(models[:5], 1):
            logger.info(f"  {i}. {model.name} (ID: {model.model_id})")

        # Example 2.5: Efficiently get first 10 models using islice
        from itertools import islice

        logger.info("Fetching first 10 models efficiently...")
        first_10_models = list(islice(client.models.get_models(target_asset.id, include_descendants=True), 10))
        logger.info(f"Retrieved {len(first_10_models)} models via slice")

        # 3. Select a model to investigate
        selected_model = models[0]
        model_id = selected_model.model_id
        logger.info(f"\n--- Investigating Model: {selected_model.name} ---")

        # 4. Get current state
        logger.info("Retrieving model state...")
        state = client.models.get_model_state(model_id)
        logger.info(f"  Active Status: {state.active}")
        logger.info(f"  Evaluation Time: {state.evaluation_time}")
        if state.active_alerts:
            logger.info(f"  Active Alerts: {', '.join(state.active_alerts)}")
        logger.info(f"  Actual: {state.actual}, Expected: {state.expected}")

        # 5. Get model configuration
        logger.info("Retrieving model configuration...")
        config = client.models.get_model_config(model_id)
        logger.info(f"  Configuration Type: {type(config).__name__}")
        logger.info(f"  Model Type: {config.model_type}")

        if hasattr(config, "inputs"):
            logger.info(f"  Inputs: {len(config.inputs)}")

        # 6. Get recent actions
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)

        logger.info(f"Retrieving actions since {start_date.date()}...")
        actions = list(client.models.get_model_actions(model_id, changed_after=start_date))
        logger.info(f"Found {len(actions)} recent action(s)")

        for i, action in enumerate(actions[:3], 1):
            logger.info(f"  {i}. [{action.change_date}] {action.action_type}: {action.action_note}")

        logger.info("\n✓ Model investigation example completed!")

    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
