# Atonix Python Client

An **unofficial**, type-safe Python client for the Prometheus APM (formerly AtonixOI) API.

> [!IMPORTANT]
> This is an independent community project. It is **not affiliated with, endorsed by, or supported by
> Prometheus Group.** It is provided **"as is", without warranty of any kind — use at your own risk.**
> See [Disclaimer](#disclaimer).

[![CI](https://github.com/stimpert-labs/atonix/actions/workflows/ci.yml/badge.svg)](https://github.com/stimpert-labs/atonix/actions/workflows/ci.yml)
[![Docs](https://github.com/stimpert-labs/atonix/actions/workflows/docs.yml/badge.svg)](https://atonix.stimpert-labs.dev)
[![CodeQL](https://github.com/stimpert-labs/atonix/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/stimpert-labs/atonix/security/code-scanning)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: LGPL v3+](https://img.shields.io/badge/license-LGPL--3.0--or--later-blue)](COPYING.LESSER)
<!-- [![PyPI version](https://img.shields.io/pypi/v/atonix.svg)](https://pypi.org/project/atonix/) -->


## Overview

The `atonix` library provides a developer-friendly interface to interact with Prometheus APM (formerly AtonixOI) Assets, Issues, Models, and Process Data. It is built with modern Python practices in mind, featuring:

- **Type Safety**: Typed responses using [Pydantic v2](https://docs.pydantic.dev/).
- **Automatic Retries**: Built-in retries for transient errors (429, 5xx) via `httpx`.
- **Lightweight**: Minimal dependencies.
- **Request Signing**: RSA-based authentication helper built-in.
- **Convenient**: Support for environment-based configuration.
- **Async Support**: Full async/await API via `AsyncAtonixClient` alongside the synchronous `AtonixClient`.

## Installation

Install the package via pip:

```bash
pip install atonix
```

## Usage

### Authentication

To authenticate, you need your **API Key** and your **RSA Private Key** (PEM format). The client accepts the key in three ways, summarized below.

#### Option A — Load the private key yourself

Use this when you want to control how the PEM is read (e.g. fetched from a secrets manager). The password — if the key is encrypted — is consumed by `load_pem_private_key` at load time, so you do **not** pass `private_key_password` to `AtonixClient`.

```python
from atonix import AtonixClient
from cryptography.hazmat.primitives import serialization

with open("path/to/private_key.pem", "rb") as key_file:
    private_key = serialization.load_pem_private_key(
        key_file.read(),
        password=b"your-password-if-encrypted",  # or None for an unencrypted key
    )

client = AtonixClient(
    api_key="YOUR_API_KEY_HERE",
    private_key=private_key,
)
```

#### Option B — Let the client load the key from a file path

The client reads the file path from the `ATONIX_PRIVATE_KEY_PATH` environment variable. There is no `private_key_path` constructor argument; the env var is the only way to supply a path. The password may come from either the `private_key_password` argument or the `ATONIX_PRIVATE_KEY_PASSWORD` env var.

```bash
export ATONIX_PRIVATE_KEY_PATH=/path/to/private_key.pem
# Optional, only if the key is encrypted:
export ATONIX_PRIVATE_KEY_PASSWORD=your-password
```

```python
from atonix import AtonixClient

# api_key may also come from ATONIX_API_KEY.
client = AtonixClient(api_key="YOUR_API_KEY_HERE")

# Or, if you'd rather pass the password in code instead of via env:
client = AtonixClient(
    api_key="YOUR_API_KEY_HERE",
    private_key_password="your-password",
)
```

#### Option C — Provide the PEM contents via environment variable

Set `ATONIX_PRIVATE_KEY` to the full PEM contents (literal `\n` sequences are converted to newlines). This is checked **before** `ATONIX_PRIVATE_KEY_PATH`, so don't set both. The password rules are the same as Option B.

```bash
export ATONIX_PRIVATE_KEY="$(cat /path/to/private_key.pem)"
# Optional:
export ATONIX_PRIVATE_KEY_PASSWORD=your-password
```

```python
from atonix import AtonixClient
client = AtonixClient(api_key="YOUR_API_KEY_HERE")
```

#### Environment variable reference
- `ATONIX_API_KEY`: Your API key (used when `api_key` is not passed explicitly).
- `ATONIX_PRIVATE_KEY`: RSA private key **contents** (PEM format). Takes precedence over `ATONIX_PRIVATE_KEY_PATH`.
- `ATONIX_PRIVATE_KEY_PATH`: Path to your private key file.
- `ATONIX_PRIVATE_KEY_PASSWORD`: Password for an encrypted private key (optional).
- `ATONIX_LOG_PAYLOADS`: When set to `1`/`true`/`yes`/`on` (case-insensitive), full time-series API payloads are logged at DEBUG. Off by default — DEBUG logs only include short summaries (tag/point counts) so production logs don't fill up with raw process values.

With all of these set, construction is simply:

```python
from atonix import AtonixClient
client = AtonixClient()
```

#### 3. Clock Synchronization

Every authenticated request is signed with a **millisecond UTC timestamp** that is
embedded in the `x-atx-auth` header (`api_key:timestamp:signature`). The Atonix
server rejects requests whose timestamp is outside its allowed skew window, so
the host running this client **must keep its system clock synchronized** with
UTC — typically via NTP (`w32tm`/`chrony`/`ntpd`) or your platform's time
service.

A skewed clock (e.g. a VM that has been suspended, a container with a stale
clock, or a host where time sync is disabled) presents as a 401
`AuthenticationError`. When the client detects symptoms of clock skew on a
401 — either skew-related keywords in the server message or a mismatch between
the response `Date` header and local time — it appends a hint to the raised
exception's message instructing you to verify your system clock.

The client does **not** auto-correct the timestamp from server time, because
doing so would defeat the replay protection the timestamp provides.

### Assets API

Navigate the asset hierarchy with ease.

```python
# List top-level assets (automatically paginated generator)
for asset in client.assets.get_top():
    print(f"{asset.abbrev} ({asset.id})")

# Get Asset Details
asset_id = "00000000-0000-0000-0000-000000000000"
details = client.assets.get_asset_details(asset_id)
print(f"Asset Type: {details.asset_type_name}")

# Get Children (supports include_descendants, changed_after, etc.)
# Returns an iterator; iterate directly, or wrap in list(...) if you need random access.
for child in client.assets.get_children(asset_id, include_descendants=True):
    print(child.abbrev)
```

### Process Data API

Query time-series data efficiently with automatic handling of Atonix's specific response structures.

```python
from datetime import datetime, timedelta, timezone
from itertools import islice

# Find a server (get_servers() returns an iterator; pull the first one).
server = next(iter(client.process_data.get_servers()))
server_id = server.server_id

# Get the first 5 tags without materializing the full list.
tag_ids = [t.tag_id for t in islice(client.process_data.get_tags_list(server_id), 5)]

# Query Data — returns a list of TagData objects
end_time = datetime.now(timezone.utc)
start_time = end_time - timedelta(hours=1)

results = client.process_data.get_data_for_range(
    server_id=server_id,
    start_time=start_time,
    end_time=end_time,
    tag_ids=tag_ids,
    archive="1min"
)

for result in results:
    print(f"Tag {result.tag_id}: {len(result.values)} points found.")
```

#### Writing Data

> [!WARNING]
> Write operations (`write_tag_data`, `create_issue`, and similar) modify data in a live APM tenant.
> Validate against a non-production environment first. You are solely responsible for any data you
> write through this library.

The library supports writing data using `TagData` objects. 
It automatically handles chunking to respect API limits (approx. 30k points per call).

```python
from atonix.object_models.processdata import TagData

new_data = [
    TagData(
        tag_id="tag-guid-1",
        timestamps=[datetime.now(timezone.utc)],
        values=[10.5],
        statuses=[0]
    )
]

client.process_data.write_tag_data(
    server_id=server_id,
    archive="1min",
    data=new_data
)
```

### Issues API

```python
# List issues for an asset
issues = client.issues.get_issues(asset_id="asset-guid")

# Filter by status, descendants, and date range
from datetime import datetime, timezone
recent_issues = client.issues.get_issues(
    asset_id="asset-guid",
    status="open",
    include_descendants=True,
    changed_after=datetime(2025, 1, 1, tzinfo=timezone.utc),
)
for issue in recent_issues:
    print(issue.title)

# Get full details of a specific issue
issue = client.issues.get_issue(issue_id="issue-guid")
print(f"Issue {issue.title} is currently {issue.issue_status}")

# Create a new issue
from atonix.object_models.issues import IssueCreate
new_issue_data = IssueCreate(
    asset_id="asset-guid",
    title="High Vibration on Pump 1",
    category_desc="Maintenance",
    issue_class_type_desc="Mechanical",
    priority="High"
)
new_issue = client.issues.create_issue(new_issue_data)
```

### Models API

```python
# List models for an asset
models = client.models.get_models(asset_id="asset-guid")

# Get a specific Model with full details (Config, State, Actions)
model = client.models.get_model(
    "model-guid",
    include_config=True,
    include_state=True,
    include_actions=True
)

print(f"Model: {model.name}")

# Access nested configuration
if model.config:
    print(f"Active: {model.config.active}")

# Access current alert state
if model.alert_state:
    print(f"Active Alerts: {', '.join(model.alert_state.active_alerts)}")

# Access recent actions
if model.actions:
    print(f"Recent Actions: {len(model.actions)}")
```

### Async Usage

All API resources are also available via `AsyncAtonixClient`, which uses `httpx.AsyncClient` under the hood and supports Python's `async`/`await` syntax. The async client accepts identical constructor arguments and environment variables as the sync client.

```python
import asyncio
from atonix import AsyncAtonixClient

async def main():
    async with AsyncAtonixClient() as client:
        # Async iteration over paginated results
        async for asset in client.assets.get_top():
            print(asset.abbrev)

        # Await single-object fetches
        issue = await client.issues.get_issue("issue-guid")
        print(issue.title)

        # Await list results
        results = await client.process_data.get_data_for_range(
            server_id="server-guid",
            start_time=...,
            end_time=...,
            tag_ids=["tag-guid"],
            archive="1min",
        )

asyncio.run(main())
```

## Documentation

API reference documentation for the latest release is published at **<https://atonix.stimpert-labs.dev>**.

Comprehensive docstrings are provided for all public methods. You can also generate the HTML documentation locally using `pdoc`:

```bash
uv run pdoc atonix -o ./docs --docformat google
```

## Error Handling

Standardized exceptions are raised based on HTTP status codes:
- `AuthenticationError` (401)
- `PermissionDeniedError` (403)
- `NotFoundError` (404)
- `RateLimitError` (429)
- `ServerError` (5xx)

If a 401 looks like it was caused by clock skew (skew-related keywords in the
server's error message, or a mismatch between the response `Date` header and
the local clock greater than 60 seconds), the raised `AuthenticationError`
includes a hint reminding you to sync the system clock via NTP. See
[Clock Synchronization](#3-clock-synchronization) above.

## Development

The project uses `uv` for dependency management and `respx` for HTTP mocking in tests.

### Running Tests

```bash
uv run pytest tests/
```

### Implementation Details
The library relies on a `BaseResource` providing generic `_get_paginated` and `_get_single` methods, ensuring consistent behavior across all API areas. Authentication and request signing are handled centrally by the `Auth` class using `cryptography`.

## Contributing & Support

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). All commits must be signed off
under the [Developer Certificate of Origin](https://developercertificate.org/) (`git commit -s`).
Support is best-effort only; see [SUPPORT.md](SUPPORT.md). Report security issues privately per
[SECURITY.md](SECURITY.md).

## Disclaimer

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.
**You use it entirely at your own risk.** The author and contributors make no guarantees about its
correctness, quality, security, availability, or continued compatibility with the Prometheus APM API, and
shall not be liable for any claim, damages, loss of data, or other liability — including any impact on
operational, plant, or asset systems, or on process data read or written through this library — arising
from, out of, or in connection with the software or its use. See sections 15 and 16 of the
[GNU GPL v3](COPYING), incorporated by the [GNU LGPL v3](COPYING.LESSER).

This is an independent project and is not affiliated with, endorsed by, sponsored by, or supported by
Prometheus Group. "Atonix", "AtonixOI", "Prometheus", and "Prometheus APM" are names or marks of their
respective owners and are used only to describe the API this library interoperates with.

## License

Copyright (c) 2023-2026 Kolton Stimpert.

`atonix` is free software: you can redistribute it and/or modify it under the terms of the
**GNU Lesser General Public License v3.0 or (at your option) any later version** (`LGPL-3.0-or-later`).
See [COPYING.LESSER](COPYING.LESSER), [COPYING](COPYING), and [NOTICE](NOTICE).

In practice, you may use `atonix` as a library in proprietary or open-source applications. If you
distribute a modified version of `atonix` itself, those modifications must be released under the LGPL.
