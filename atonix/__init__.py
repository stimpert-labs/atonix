"""
Atonix Python Client
--------------------
Unofficial Python client for the Prometheus APM (formerly AtonixOI) API.
Not affiliated with, endorsed by, or supported by Prometheus Group.

Copyright (c) 2023-2026 Kolton Stimpert

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details. You should have received a copy of the GNU Lesser General Public
License along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("atonix")
except PackageNotFoundError:
    __version__ = "unknown"

__author__ = "Kolton Stimpert"
__copyright__ = "Copyright (c) 2023-2026 Kolton Stimpert"
__license__ = "LGPL-3.0-or-later"

from atonix.assets import Assets, AsyncAssets
from atonix.client import AsyncAtonixClient, AtonixClient, AtonixEnvironment
from atonix.exceptions import (
    APIError,
    AtonixError,
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    QuerySizeError,
    RateLimitError,
    ServerError,
)
from atonix.issues import AsyncIssues, Issues
from atonix.models import AsyncModels, Models
from atonix.processdata import AsyncProcessData, ProcessData

__all__ = [
    "APIError",
    "Assets",
    "AsyncAssets",
    "AsyncAtonixClient",
    "AsyncIssues",
    "AsyncModels",
    "AsyncProcessData",
    "AtonixClient",
    "AtonixEnvironment",
    "AtonixError",
    "AuthenticationError",
    "Issues",
    "Models",
    "NotFoundError",
    "PermissionDeniedError",
    "ProcessData",
    "QuerySizeError",
    "RateLimitError",
    "ServerError",
    "__author__",
    "__copyright__",
    "__license__",
    "__version__",
]
