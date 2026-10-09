# Sync or async?

`atonix` ships two clients: [`AtonixClient`][atonix.AtonixClient] and
[`AsyncAtonixClient`][atonix.AsyncAtonixClient]. They take the same constructor arguments, read
the same environment variables, and have the same methods with the same names and return types.
The only difference is how you call them.

## Use the sync client when...

- you're writing a script, notebook, scheduled job, or CLI tool;
- calls happen one after another and each depends on the last (walk a hierarchy, then query its
  tags);
- the rest of your code is synchronous (pandas, Flask, Django views, and so on).

**If you're unsure, start here.** It's the simplest to read and debug, and you can switch later.

## Use the async client when...

- your application already runs an event loop (FastAPI, aiohttp, an async worker or bot); calling
  the sync client there would block the loop;
- you want to send many **independent** requests at once, such as fetching details for hundreds
  of assets or reading several servers in parallel.

!!! info "Async doesn't parallelize on its own"
    The async client doesn't run requests concurrently for you. A loop of `await` calls is no
    faster than the sync client. The speedup comes from running calls together with
    `asyncio.gather` or a `TaskGroup`.

## How the async API differs

| Kind of method                         | Sync                               | Async                                    |
| -------------------------------------- | ---------------------------------- | ---------------------------------------- |
| Returns one object or a list           | `client.issues.get_issue(id)`      | `await client.issues.get_issue(id)`      |
| Paginated (returns an iterator)        | `for a in client.assets.get_top()` | `async for a in client.assets.get_top()` |
| Closing the client                     | `with` / `client.close()`          | `async with` / `await client.aclose()`   |

## Example: concurrent fetches

```python
import asyncio

from atonix import AsyncAtonixClient


async def main(asset_ids: list[str]):
    async with AsyncAtonixClient() as client:
        details = await asyncio.gather(*(client.assets.get_asset_details(asset_id) for asset_id in asset_ids))
        for d in details:
            print(d.abbrev, d.asset_type_name)


asyncio.run(main(["asset-guid-1", "asset-guid-2", "asset-guid-3"]))
```

## Limiting concurrency

Very wide fan-out can trip the API's rate limit. Rate-limited requests are retried, but it's
better not to hit the limit at all. Cap the number of requests in flight with a semaphore:

```python
async def main(asset_ids: list[str], limit: int = 10):
    sem = asyncio.Semaphore(limit)

    async with AsyncAtonixClient() as client:

        async def fetch(asset_id: str):
            async with sem:
                return await client.assets.get_asset_details(asset_id)

        return await asyncio.gather(*(fetch(a) for a in asset_ids))
```

## Collecting an async iterator

There's no built-in `list()` for async iterators; use a comprehension:

```python
assets = [asset async for asset in client.assets.get_top()]
```
