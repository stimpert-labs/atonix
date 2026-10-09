# Assets

The [`Assets`][atonix.Assets] resource (`client.assets`) navigates the asset hierarchy.

## Top-level assets

=== "Sync"

    ```python
    for asset in client.assets.get_top():
        print(asset.abbrev, asset.id)
    ```

=== "Async"

    ```python
    async for asset in client.assets.get_top():
        print(asset.abbrev, asset.id)
    ```

## Asset details

=== "Sync"

    ```python
    details = client.assets.get_asset_details("asset-guid")
    print(details.asset_type_name, details.change_date)
    ```

=== "Async"

    ```python
    details = await client.assets.get_asset_details("asset-guid")
    print(details.asset_type_name, details.change_date)
    ```

## Children and descendants

`get_children` returns direct children by default. Pass `include_descendants=True` for the whole
subtree.

=== "Sync"

    ```python
    for child in client.assets.get_children("asset-guid", include_descendants=True):
        print(child.abbrev)
    ```

=== "Async"

    ```python
    async for child in client.assets.get_children("asset-guid", include_descendants=True):
        print(child.abbrev)
    ```

See the [`Assets` reference][atonix.Assets] for all filters, such as `changed_after`.
