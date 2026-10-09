# API reference

Generated from the docstrings in the source.

- **[Clients](clients.md)**: `AtonixClient`, `AsyncAtonixClient`, and `AtonixEnvironment`.
- **[Resources](resources.md)**: the sync resource classes behind `client.assets`, `client.issues`,
  `client.models`, and `client.process_data`.
- **[Async resources](async-resources.md)**: their async counterparts.
- **[Object models](object-models.md)**: the Pydantic models returned and accepted by the API.
- **[Exceptions](exceptions.md)**: everything the library raises.

You don't construct resource classes yourself; reach them through a client's attributes.
