# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""
Example workflow for interacting with Atonix Models.

This script demonstrates how to:
1. Fetch a model by ID.
2. Hydrate a Model object with configuration, state, and actions.
3. Access nested properties.
"""

import logging
import os

from atonix import AtonixClient
from atonix.object_models.models import Model

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    # Initialize client (ensure env vars are set)
    # ATONIX_API_KEY, ATONIX_PRIVATE_KEY_PATH (or ATONIX_PRIVATE_KEY)
    try:
        client = AtonixClient()
    except ValueError as e:
        logger.error(f"Failed to initialize client: {e}")
        return

    model_id = os.getenv("MODEL_ID")

    logger.info("--- 1. Simple Retrieval ---")
    # Get basic model info (if you just want the object wrapper)
    model = client.models.get_model(model_id)
    logger.info(f"Model ID: {model.model_id}")

    logger.info("\n--- 2. Full Hydration ---")
    # Fetch everything: Config, State, Actions
    # This makes multiple API calls under the hood
    full_model = client.models.get_model(model_id, include_config=True, include_state=True, include_actions=True)

    logger.info(f"Model: {full_model.model_id}")

    if full_model.config:
        logger.info(f"Config Active: {full_model.config.active}")
        if full_model.config.tag:
            logger.info(f"Target Tag: {full_model.config.tag.name} ({full_model.config.tag.tag_id})")

    if full_model.alert_state:
        logger.info(f"Current Alert State Active: {full_model.alert_state.active}")
        logger.info(f"Active Alerts: {full_model.alert_state.active_alerts}")

    if full_model.actions:
        logger.info(f"Recent Actions found: {len(full_model.actions)}")
        for action in full_model.actions[:3]:
            logger.info(f" - {action.change_date}: {action.action_note}")

    logger.info("\n--- 3. Object-based Hydration ---")
    # You can pass a Model object itself to get_model to "fill it in"
    # Useful if you have a list of light objects and want details for one

    # Simulate a lightweight model object (e.g. from a list)
    light_model = Model(Id=model_id, Name="My Model")

    # Hydrate it
    updated_model = client.models.get_model(light_model, include_state=True)

    logger.info(f"Updated Model: {updated_model.name}")
    if updated_model.alert_state:
        logger.info(f"State retrieved: Active={updated_model.alert_state.active}")


if __name__ == "__main__":
    main()
