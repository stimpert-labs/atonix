# Error handling

Everything the library raises derives from [`AtonixError`][atonix.AtonixError], so one `except`
catches it all. HTTP failures map to specific subclasses:

| Exception                                                 | Raised for                                                      |
| --------------------------------------------------------- | --------------------------------------------------------------- |
| [`AuthenticationError`][atonix.AuthenticationError]       | 401: bad API key, bad signature, or [clock skew](../getting-started/authentication.md#clock-synchronization) |
| [`PermissionDeniedError`][atonix.PermissionDeniedError]   | 403                                                             |
| [`NotFoundError`][atonix.NotFoundError]                   | 404                                                             |
| [`RateLimitError`][atonix.RateLimitError]                 | 429, after all retries                                          |
| [`ServerError`][atonix.ServerError]                       | 5xx, after all retries                                          |
| [`APIError`][atonix.APIError]                             | Other non-success responses and network failures                |
| [`QuerySizeError`][atonix.QuerySizeError]                 | A process data read over the point limit with `chunk=False`     |

```python
from atonix import AtonixError, NotFoundError

try:
    details = client.assets.get_asset_details("asset-guid")
except NotFoundError:
    details = None
except AtonixError as e:
    print(f"Atonix call failed: {e}")
    raise
```

## Retries

429 and 5xx responses are retried with backoff before an exception is raised. Set the number of
attempts with `max_retries` on the client (default 3; `0` or `1` turns retries off). Every request is
attempted at least once.

## Inspecting `APIError`

[`APIError`][atonix.APIError] carries the HTTP status and raw body when there is one:

```python
from atonix import APIError

try:
    ...
except APIError as e:
    print(e.status_code, e.response_content)
```

## `QuerySizeError` and `ValueError`

[`QuerySizeError`][atonix.QuerySizeError] also subclasses `ValueError`, so older code that caught
`ValueError` for oversized reads keeps working.
