# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import Any

from atonix.base import AsyncBaseResource, BaseResource, _to_utc_ms_str
from atonix.object_models.assets import Asset

logger = logging.getLogger(__name__)


class Assets(BaseResource):
    """Interface for the Atonix Assets API."""

    def get_top(self, skip: int = 0, take: int = 50) -> Iterator[Asset]:
        """
        Retrieve top level of available assets.

        Automatically handles pagination starting from the skip offset.

        Args:
            skip: Number of assets to skip for initial offset.
            take: Number of assets to retrieve per API page.

        Yields:
            Asset objects one by one.
        """
        logger.debug("Fetching top-level assets...")
        return self._get_paginated("/v1/assets", Asset, skip=skip, take=take)

    def get_asset_details(self, asset_id: str) -> Asset:
        """
        Get the details for a single asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.

        Returns:
            An Asset object.

        Raises:
            NotFoundError: If the asset does not exist.
            APIError: On unexpected API failure.
        """
        return self._get_single(f"/v1/assets/{asset_id}", Asset)

    def get_children(
        self,
        asset_id: str,
        include_descendants: bool = False,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        include_self: bool = False,
        skip: int = 0,
        take: int = 500,
    ) -> Iterator[Asset]:
        """
        Get the children assets of a given parent asset.

        Offers various filters including descendant recursion and date-based modification filters.
        Automatically handles pagination.

        Args:
            asset_id: The unique identifier (GUID) of the parent asset.
            include_descendants: Whether to include all levels of children (recursive).
            changed_after: Filter assets modified after this date (ISO 8601).
            changed_before: Filter assets modified before this date (ISO 8601).
            include_self: Whether to include the parent asset in the result.
            skip: Number of assets to skip for initial offset.
            take: Number of assets to retrieve per API page (max 500).

        Yields:
            Asset objects one by one.
        """
        logger.debug("Fetching children for asset %s (include_descendants=%s)", asset_id, include_descendants)

        params: dict[str, Any] = {
            "includeDescendants": str(include_descendants).lower(),
            "includeSelf": str(include_self).lower(),
        }
        if changed_after:
            params["changedAfter"] = _to_utc_ms_str(changed_after)
        if changed_before:
            params["changedBefore"] = _to_utc_ms_str(changed_before)

        return self._get_paginated(f"/v1/assets/{asset_id}/assets", Asset, params=params, skip=skip, take=take)


class AsyncAssets(AsyncBaseResource):
    """Async interface for the Atonix Assets API."""

    def get_top(self, skip: int = 0, take: int = 50) -> AsyncIterator[Asset]:
        """
        Retrieve top level of available assets.

        Args:
            skip: Number of assets to skip for initial offset.
            take: Number of assets to retrieve per API page.

        Returns:
            An async iterator of Asset objects.
        """
        return self._get_paginated("/v1/assets", Asset, skip=skip, take=take)

    async def get_asset_details(self, asset_id: str) -> Asset:
        """
        Get the details for a single asset.

        Args:
            asset_id: The unique identifier (GUID) of the asset.

        Returns:
            An Asset object.

        Raises:
            NotFoundError: If the asset does not exist.
            APIError: On unexpected API failure.
        """
        return await self._get_single(f"/v1/assets/{asset_id}", Asset)

    def get_children(
        self,
        asset_id: str,
        include_descendants: bool = False,
        changed_after: datetime | None = None,
        changed_before: datetime | None = None,
        include_self: bool = False,
        skip: int = 0,
        take: int = 500,
    ) -> AsyncIterator[Asset]:
        """
        Get the children assets of a given parent asset.

        Args:
            asset_id: The unique identifier (GUID) of the parent asset.
            include_descendants: Whether to include all levels of children (recursive).
            changed_after: Filter assets modified after this date (ISO 8601).
            changed_before: Filter assets modified before this date (ISO 8601).
            include_self: Whether to include the parent asset in the result.
            skip: Number of assets to skip for initial offset.
            take: Number of assets to retrieve per API page (max 500).

        Returns:
            An async iterator of Asset objects.
        """
        params: dict[str, Any] = {
            "includeDescendants": str(include_descendants).lower(),
            "includeSelf": str(include_self).lower(),
        }
        if changed_after:
            params["changedAfter"] = _to_utc_ms_str(changed_after)
        if changed_before:
            params["changedBefore"] = _to_utc_ms_str(changed_before)

        return self._get_paginated(f"/v1/assets/{asset_id}/assets", Asset, params=params, skip=skip, take=take)
