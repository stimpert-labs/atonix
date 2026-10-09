# Quick start

## 1. Install

```bash
pip install atonix
```

## 2. Get credentials

You need two things from your Prometheus APM tenant:

- an **API key**
- the matching **RSA private key** in PEM format

## 3. Set environment variables

=== "Linux / macOS"

    ```bash
    export ATONIX_API_KEY="your-api-key"
    export ATONIX_PRIVATE_KEY_PATH="/path/to/private_key.pem"
    export ATONIX_PRIVATE_KEY_PASSWORD="your-password"  # only if the key is encrypted
    ```

=== "Windows (PowerShell)"

    ```powershell
    $env:ATONIX_API_KEY = "your-api-key"
    $env:ATONIX_PRIVATE_KEY_PATH = "C:\path\to\private_key.pem"
    $env:ATONIX_PRIVATE_KEY_PASSWORD = "your-password"  # only if the key is encrypted
    ```

You can also pass credentials straight to the client. [Authentication](authentication.md) covers
every option.

## 4. Make a request

=== "Sync"

    ```python
    from atonix import AtonixClient

    with AtonixClient() as client:
        for asset in client.assets.get_top():
            print(asset.abbrev, asset.id)
    ```

=== "Async"

    ```python
    import asyncio

    from atonix import AsyncAtonixClient


    async def main():
        async with AsyncAtonixClient() as client:
            async for asset in client.assets.get_top():
                print(asset.abbrev, asset.id)


    asyncio.run(main())
    ```

Using the client as a context manager closes its HTTP connections when you're done. Outside a
`with` block, call `client.close()` (or `await client.aclose()` for async).

## What the client gives you

The client has one attribute per API area:

| Attribute             | Sync class                              | Async class                                       | Covers                                    |
| --------------------- | --------------------------------------- | ------------------------------------------------- | ----------------------------------------- |
| `client.assets`       | [`Assets`][atonix.Assets]               | [`AsyncAssets`][atonix.AsyncAssets]               | Asset hierarchy and details               |
| `client.issues`       | [`Issues`][atonix.Issues]               | [`AsyncIssues`][atonix.AsyncIssues]               | Issues, keywords, discussion entries      |
| `client.models`       | [`Models`][atonix.Models]               | [`AsyncModels`][atonix.AsyncModels]               | Model configuration, alert state, actions |
| `client.process_data` | [`ProcessData`][atonix.ProcessData]     | [`AsyncProcessData`][atonix.AsyncProcessData]     | Servers, tags, time-series reads/writes   |

Next, read [Sync or async?](../guide/sync-vs-async.md) to pick a client, or jump to the
[user guide](../guide/assets.md) for examples.
