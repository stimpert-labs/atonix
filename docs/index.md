# atonix

An **unofficial**, type-safe Python client for the Prometheus APM (formerly AtonixOI) API.

!!! warning "Independent project"
    `atonix` is not affiliated with, endorsed by, or supported by Prometheus Group. It is provided
    "as is", without warranty of any kind. Use it at your own risk.

`atonix` wraps the Assets, Issues, Models, and Process Data APIs behind a small set of resource
objects. It signs requests, follows pagination, retries transient failures, and maps errors to
exceptions, and it returns [Pydantic v2](https://docs.pydantic.dev/) models instead of raw JSON.

- **Typed responses.** Every call returns models from [`atonix.object_models`](reference/object-models.md).
- **Automatic pagination.** List methods return iterators that fetch pages as you consume them.
- **Retries.** 429 and 5xx responses are retried with backoff.
- **Sync and async.** [`AtonixClient`][atonix.AtonixClient] and
  [`AsyncAtonixClient`][atonix.AsyncAtonixClient] have the same methods.

## Installation

```bash
pip install atonix
```

Python 3.10 or newer is required.

## A first call

```python
from atonix import AtonixClient

with AtonixClient() as client:  # credentials come from environment variables
    for asset in client.assets.get_top():
        print(asset.abbrev, asset.id)
```

## Where to go next

<div class="grid cards" markdown>

-   **[Quick start](getting-started/quickstart.md)**

    Set up credentials and make your first request.

-   **[Sync or async?](guide/sync-vs-async.md)**

    Choose between `AtonixClient` and `AsyncAtonixClient`.

-   **[User guide](guide/assets.md)**

    Examples for assets, process data, issues, and models.

-   **[API reference](reference/index.md)**

    Every class, method, and model.

</div>
