# Models

The [`Models`][atonix.Models] resource (`client.models`) reads model configuration, current alert
state, and the action history for models attached to assets.

## Listing models

=== "Sync"

    ```python
    for model in client.models.get_models("asset-guid", include_descendants=True):
        print(model.name)
    ```

=== "Async"

    ```python
    async for model in client.models.get_models("asset-guid", include_descendants=True):
        print(model.name)
    ```

## One model with everything attached

[`get_model`][atonix.Models.get_model] takes a model ID (or a `Model` you already have) and can
fetch its configuration, alert state, and recent actions in one call.

=== "Sync"

    ```python
    model = client.models.get_model("model-guid", include_config=True, include_state=True, include_actions=True)
    ```

=== "Async"

    ```python
    model = await client.models.get_model("model-guid", include_config=True, include_state=True, include_actions=True)
    ```

```python
if model.config:
    print("Active:", model.config.active)

if model.alert_state:
    print("Alerts:", ", ".join(model.alert_state.active_alerts))

if model.actions:
    for action in model.actions:
        print(action.change_date, action.action_type, action.action_note)
```

## State and actions across an asset

To check many models at once, query by asset instead of model by model:

=== "Sync"

    ```python
    for state in client.models.get_model_states_by_asset("asset-guid", include_descendants=True):
        if state.active_alerts:
            print(state.model_id, state.active_alerts)
    ```

=== "Async"

    ```python
    async for state in client.models.get_model_states_by_asset("asset-guid", include_descendants=True):
        if state.active_alerts:
            print(state.model_id, state.active_alerts)
    ```

[`get_model_actions_by_asset`][atonix.Models.get_model_actions_by_asset] works the same way for
action history.
