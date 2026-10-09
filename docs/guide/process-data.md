# Process data

The [`ProcessData`][atonix.ProcessData] resource (`client.process_data`) covers historian
servers, tags, and time-series reads and writes.

## Servers, tags, and archives

=== "Sync"

    ```python
    from itertools import islice

    server = next(iter(client.process_data.get_servers()))

    # First 5 tags, without fetching the whole list.
    tags = list(islice(client.process_data.get_tags_list(server.server_id), 5))

    for archive in client.process_data.get_archives(server.server_id):
        print(archive.name, archive.interval)
    ```

=== "Async"

    ```python
    server = await anext(aiter(client.process_data.get_servers()))

    tags = []
    async for tag in client.process_data.get_tags_list(server.server_id):
        tags.append(tag)
        if len(tags) == 5:
            break

    async for archive in client.process_data.get_archives(server.server_id):
        print(archive.name, archive.interval)
    ```

!!! note
    `anext` and `aiter` are built in from Python 3.10.

## Reading data

[`get_data_for_range`][atonix.ProcessData.get_data_for_range] returns one
[`TagData`][atonix.object_models.processdata.TagData] per tag.

=== "Sync"

    ```python
    from datetime import datetime, timedelta, timezone

    end = datetime.now(timezone.utc)
    results = client.process_data.get_data_for_range(
        server_id=server.server_id,
        start_time=end - timedelta(hours=1),
        end_time=end,
        tag_ids=[t.tag_id for t in tags],
        archive="1min",
    )
    for series in results:
        print(series.tag_id, len(series.values))
    ```

=== "Async"

    ```python
    from datetime import datetime, timedelta, timezone

    end = datetime.now(timezone.utc)
    results = await client.process_data.get_data_for_range(
        server_id=server.server_id,
        start_time=end - timedelta(hours=1),
        end_time=end,
        tag_ids=[t.tag_id for t in tags],
        archive="1min",
    )
    for series in results:
        print(series.tag_id, len(series.values))
    ```

### Large reads

The API caps a single query at 250,000 tag × timestamp points. Bigger reads are split
automatically, by tag group and, when one tag alone is over the limit, by time window. The
per-tag series are stitched back together before they're returned.

Pass `chunk=False` to raise [`QuerySizeError`][atonix.QuerySizeError] instead:

```python
from atonix import QuerySizeError

try:
    client.process_data.get_data_for_range(server_id, start, end, tag_ids, "1min", chunk=False)
except QuerySizeError as e:
    print(e.limit, e.tag_count, e.timestamps_per_tag, e.total_points)
```

## Writing data

!!! warning
    Writes change data in a live tenant. Try them against a non-production environment first.
    You're responsible for any data you write with this library.

[`write_tag_data`][atonix.ProcessData.write_tag_data] takes a list of `TagData` and batches it
to stay under the API's per-call limit (about 30,000 points).

=== "Sync"

    ```python
    from datetime import datetime, timezone

    from atonix.object_models.processdata import TagData

    data = [
        TagData(tag_id="tag-guid", timestamps=[datetime.now(timezone.utc)], values=[10.5], statuses=[0]),
    ]
    client.process_data.write_tag_data(server_id=server.server_id, archive="1min", data=data)
    ```

=== "Async"

    ```python
    await client.process_data.write_tag_data(server_id=server.server_id, archive="1min", data=data)
    ```

## Logging payloads

DEBUG logs only include short summaries (tag and point counts) by default. Set
`ATONIX_LOG_PAYLOADS=1` to log full request and response payloads while debugging.
