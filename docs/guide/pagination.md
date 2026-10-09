# Pagination

Methods that list things (`get_top`, `get_children`, `get_issues`, `get_tags_list`, `get_models`,
and so on) return **lazy iterators**. Pages are fetched as you iterate, so:

- you can stop early without downloading everything;
- nothing is fetched until you start iterating.

## Common patterns

=== "Sync"

    ```python
    from itertools import islice

    # Everything, as a list
    assets = list(client.assets.get_top())

    # Just the first 10
    first_ten = list(islice(client.assets.get_top(), 10))

    # Just the first one
    first = next(iter(client.assets.get_top()), None)
    ```

=== "Async"

    ```python
    # Everything, as a list
    assets = [a async for a in client.assets.get_top()]

    # Just the first 10
    first_ten = []
    async for a in client.assets.get_top():
        first_ten.append(a)
        if len(first_ten) == 10:
            break

    # Just the first one
    first = await anext(aiter(client.assets.get_top()), None)
    ```

## Page size

Paginated methods take `skip` and `take` arguments. `skip` sets the starting offset and `take`
sets how many items each request fetches. The iterator keeps requesting pages until the API runs
out of results, so `take` controls the number of round trips, not the total returned. The
defaults suit most uses.
