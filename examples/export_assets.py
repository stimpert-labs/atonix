# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
import csv
import logging

from atonix import AtonixClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Initializing Atonix client...")
    client = AtonixClient()

    logger.info("Fetching top-level assets...")
    top_assets = list(client.assets.get_top())

    if not top_assets:
        logger.error("No top-level assets found.")
        return

    # User requested "the top asset"
    top_asset = top_assets[0]
    logger.info(f"Selected top asset: {top_asset.abbrev} (ID: {top_asset.id})")

    logger.info("Fetching all descendant children...")
    descendants = client.assets.get_children(top_asset.id, include_descendants=True)
    all_assets = [top_asset, *descendants]

    logger.info(f"Total assets fetched (including top asset): {len(all_assets)}")

    csv_file = "assets.csv"
    logger.info(f"Writing data to {csv_file}...")

    # Dynamically get the fields from the Asset pydantic model properties
    fields = list(all_assets[0].model_fields.keys())

    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for asset in all_assets:
            writer.writerow(asset.model_dump(mode="json"))

    logger.info("Finished writing to CSV.")


if __name__ == "__main__":
    main()
