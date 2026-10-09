r"""
An **unofficial**, type-safe Python client for the Prometheus APM (formerly AtonixOI) API.

> **Note:** This is an independent community project. It is not affiliated with, endorsed by, or
> supported by Prometheus Group, and is provided "as is", without warranty of any kind.

`atonix` wraps the Assets, Issues, Models, and Process Data APIs behind a small set of resource
objects. It handles request signing, pagination, retries, and error mapping for you, and returns
[Pydantic v2](https://docs.pydantic.dev/) models instead of raw JSON.

- **Typed responses**: every call returns Pydantic models from `atonix.object_models`.
- **Automatic pagination**: list endpoints return iterators that fetch pages as you consume them.
- **Retries**: transient errors (429, 5xx) are retried with backoff.
- **Sync and async**: `AtonixClient` and `AsyncAtonixClient` expose the same API.

Source, issues, and runnable examples live on
[GitHub](https://github.com/stimpert-labs/atonix).

## Installation

```bash
pip install atonix
```

Python 3.10 or newer is required.

## Quick start

1. Get an **API key** and the matching **RSA private key** (PEM) from your Prometheus APM tenant.
2. Put them in the environment:

    ```bash
    export ATONIX_API_KEY="your-api-key"
    export ATONIX_PRIVATE_KEY_PATH="/path/to/private_key.pem"
    export ATONIX_PRIVATE_KEY_PASSWORD="your-password"  # only if the key is encrypted
    ```

3. Create a client and make a call:

    ```python
    from atonix import AtonixClient

    with AtonixClient() as client:
        for asset in client.assets.get_top():
            print(asset.abbrev, asset.id)
    ```

The client exposes one attribute per API area:

| Attribute             | Sync class    | Async class        | Covers                                   |
| --------------------- | ------------- | ------------------ | ---------------------------------------- |
| `client.assets`       | `Assets`      | `AsyncAssets`      | Asset hierarchy and details              |
| `client.issues`       | `Issues`      | `AsyncIssues`      | Issues, keywords, and issue creation     |
| `client.models`       | `Models`      | `AsyncModels`      | Model configuration, alert state, actions|
| `client.process_data` | `ProcessData` | `AsyncProcessData` | Servers, tags, time-series reads/writes  |

## Sync or async?

Both clients take the same constructor arguments, read the same environment variables, and have
the same methods with the same names and return types. Pick the one that fits your program.

**Use `AtonixClient` (sync) when:**

- You're writing a script, notebook, scheduled job, or CLI tool.
- Calls run one after another, and each depends on the last (walk a hierarchy, then query its tags).
- The rest of your code is synchronous (pandas, Flask, Django views, etc.).

If you're not sure, start here. It's the simplest to read and debug.

**Use `AsyncAtonixClient` when:**

- Your application already runs an event loop (FastAPI, aiohttp, an async worker or bot).
- You want to issue many independent requests at once, such as fetching details for hundreds of
  assets or reading several servers in parallel. The client doesn't parallelize for you; you
  get the speedup by running calls together with `asyncio.gather` or a `TaskGroup`.

How the async API differs:

- Methods that return one object or a list are coroutines: `await client.issues.get_issue(...)`.
- Paginated methods return async iterators: `async for asset in client.assets.get_top(): ...`.
- Close the client with `async with` or `await client.aclose()` instead of `close()`.

```python
import asyncio

from atonix import AsyncAtonixClient


async def main(asset_ids: list[str]):
    async with AsyncAtonixClient() as client:
        # Fetch all asset details concurrently instead of one at a time.
        details = await asyncio.gather(
            *(client.assets.get_asset_details(asset_id) for asset_id in asset_ids)
        )
        for d in details:
            print(d.asset_type_name)


asyncio.run(main(["asset-guid-1", "asset-guid-2"]))
```

Be considerate with concurrency: very wide fan-out can trip the API's rate limit. Cap it with an
`asyncio.Semaphore` if you're running hundreds of requests at once.

## Authentication

Requests are signed with your RSA private key. The client finds the key in this order:

1. The `private_key` argument (an already-loaded `cryptography` key object).
2. `ATONIX_PRIVATE_KEY`: the PEM contents (literal `\n` sequences are converted to newlines).
3. `ATONIX_PRIVATE_KEY_PATH`: a path to the PEM file.

For an encrypted key loaded from the environment, give the password with the
`private_key_password` argument or `ATONIX_PRIVATE_KEY_PASSWORD`. If you load the key yourself,
decrypt it at load time and don't pass a password to the client:

```python
from cryptography.hazmat.primitives import serialization

from atonix import AtonixClient

with open("path/to/private_key.pem", "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

client = AtonixClient(api_key="YOUR_API_KEY", private_key=private_key)
```

### Environment variables

| Variable                      | Purpose                                                                 |
| ----------------------------- | ----------------------------------------------------------------------- |
| `ATONIX_API_KEY`              | API key, used when `api_key` isn't passed.                              |
| `ATONIX_PRIVATE_KEY`          | PEM contents. Takes precedence over `ATONIX_PRIVATE_KEY_PATH`.          |
| `ATONIX_PRIVATE_KEY_PATH`     | Path to the PEM file.                                                   |
| `ATONIX_PRIVATE_KEY_PASSWORD` | Password for an encrypted key (optional).                               |
| `ATONIX_LOG_PAYLOADS`         | Set to `1`/`true` to log full time-series payloads at DEBUG (off by default). |

### Other client options

- `environment`: an `AtonixEnvironment` (`US`, the default, or `INDIA`) or a custom base URL.
- `timeout`: per-request timeout in seconds (default 30).
- `max_retries`: retries for 429 and 5xx responses (default 3).

### Clock synchronization

Every request carries a millisecond UTC timestamp, and the server rejects requests whose clock
is too far off. Keep the host's clock synced (NTP, `chrony`, `w32tm`). A skewed clock shows up as
an `AuthenticationError`; when the client suspects skew, it adds a hint to the error message.

## Usage examples

The snippets below use a sync `client`. With `AsyncAtonixClient`, add `await` to single-result
calls and use `async for` on iterators.

### Assets

```python
asset_id = "00000000-0000-0000-0000-000000000000"

details = client.assets.get_asset_details(asset_id)
print(details.asset_type_name)

for child in client.assets.get_children(asset_id, include_descendants=True):
    print(child.abbrev)
```

### Process data

```python
from datetime import datetime, timedelta, timezone
from itertools import islice

server = next(iter(client.process_data.get_servers()))
tag_ids = [t.tag_id for t in islice(client.process_data.get_tags_list(server.server_id), 5)]

end = datetime.now(timezone.utc)
results = client.process_data.get_data_for_range(
    server_id=server.server_id,
    start_time=end - timedelta(hours=1),
    end_time=end,
    tag_ids=tag_ids,
    archive="1min",
)
for series in results:
    print(series.tag_id, len(series.values))
```

Large reads are split automatically: a query over 250,000 tag x timestamp points is broken into
sub-queries and the results are stitched back together. Pass `chunk=False` to raise
`QuerySizeError` instead.

Writes take `atonix.object_models.processdata.TagData` objects and are batched to stay under
the API's per-call limit:

```python
from atonix.object_models.processdata import TagData

data = [TagData(tag_id="tag-guid", timestamps=[datetime.now(timezone.utc)], values=[10.5], statuses=[0])]
client.process_data.write_tag_data(server_id=server.server_id, archive="1min", data=data)
```

> **Warning:** write methods (`write_tag_data`, `create_issue`, and similar) change data in a live
> tenant. Try them against a non-production environment first.

### Issues

```python
from atonix.object_models.issues import IssueCreate

for issue in client.issues.get_issues(asset_id="asset-guid", status="open", include_descendants=True):
    print(issue.title)

issue = client.issues.get_issue("issue-guid")

new_issue = client.issues.create_issue(
    IssueCreate(
        asset_id="asset-guid",
        title="High vibration on pump 1",
        category_desc="Maintenance",
        issue_class_type_desc="Mechanical",
        priority="High",
    )
)
```

### Models

```python
model = client.models.get_model("model-guid", include_config=True, include_state=True, include_actions=True)

if model.alert_state:
    print(", ".join(model.alert_state.active_alerts))
```

## Pagination

List methods (`get_top`, `get_children`, `get_issues`, `get_tags_list`, ...) return lazy
iterators. Pages are fetched as you iterate, so you can stop early without downloading
everything. Wrap the result in `list(...)` when you need the full set, or use
`itertools.islice` to take the first few.

## Error handling

All exceptions derive from `AtonixError`, so one `except` catches everything the library raises.
HTTP errors map to specific subclasses:

| Exception               | Raised for                                          |
| ----------------------- | --------------------------------------------------- |
| `AuthenticationError`   | 401: bad key, bad signature, or clock skew          |
| `PermissionDeniedError` | 403                                                 |
| `NotFoundError`         | 404                                                 |
| `RateLimitError`        | 429 after all retries                               |
| `ServerError`           | 5xx after all retries                               |
| `APIError`              | Other non-success responses and network failures    |
| `QuerySizeError`        | A process data read over the point limit with `chunk=False` |

```python
from atonix import AtonixError, NotFoundError

try:
    client.assets.get_asset_details("00000000-0000-0000-0000-000000000000")
except NotFoundError:
    print("No such asset")
except AtonixError as e:
    print(f"Atonix call failed: {e}")
```

## License

Copyright (c) 2023-2026 Kolton Stimpert.

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

# Order controls the API reference: clients first, then resources (sync, then async), then errors.
__all__ = [  # noqa: RUF022
    # Clients
    "AtonixClient",
    "AsyncAtonixClient",
    "AtonixEnvironment",
    # Sync resources
    "Assets",
    "Issues",
    "Models",
    "ProcessData",
    # Async resources
    "AsyncAssets",
    "AsyncIssues",
    "AsyncModels",
    "AsyncProcessData",
    # Exceptions
    "AtonixError",
    "APIError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "QuerySizeError",
    "__author__",
    "__copyright__",
    "__license__",
    "__version__",
]
