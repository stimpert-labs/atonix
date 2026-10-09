# Atonix Python Client Development Guide

This document serves as the primary context for agentic development of the Atonix Python Client. It outlines the project's goals, architecture, and the standards to be followed when extending the library based on API specifications.

## Project Overview

The `atonix` package is an unofficial, modern, type-safe Python client for the Prometheus APM (formerly AtonixOI) APIs. It is not affiliated with Prometheus Group. It aims to provide a developer-friendly interface that abstracts away the complexities of authentication, pagination, and error handling.

### Key Goals
- **Spec-Driven**: All models and client methods should align with the official Swagger documentation.
- **Type Safety**: Use Pydantic models for all request and response objects.
- **Ease of Use**: Provide high-level abstractions (e.g., `client.assets.get_top()`) rather than raw API calls.
- **Modern Python**: Target Python 3.10+ and leverage modern features like type hints and Enums.

---

## API Documentation (Source of Truth)

The authoritative source for the APIs is the Swagger/OpenAPI documentation published by Prometheus APM.
Obtain the spec files from your own Prometheus APM tenant and keep them **outside** this repository —
they are not part of this project and must not be committed.

Key spec files:
- `assets_swagger.json`: Asset hierarchy and details.
- `processdata_swagger.json`: Time-series data retrieval and writing.
- `issues_swagger.json`: Issue management and keywords.
- `models_swagger.json`: Model configurations, state, and alerts.

---

## Project Structure

```text
atonix/
├── atonix/                # Core library source
│   ├── object_models/     # Pydantic models (DTOs)
│   │   ├── common.py      # Shared models (APIResponse, etc.)
│   │   ├── assets.py      # Asset-related models
│   │   ├── issues.py      # Issue-related models
│   │   └── ...
│   ├── client.py          # Main AtonixClient and Auth logic
│   ├── assets.py          # Assets resource implementation
│   ├── issues.py          # Issues resource implementation
│   ├── processdata.py     # ProcessData resource implementation
│   └── models.py          # Models resource implementation
├── docs/                  # MkDocs site (guide + API reference pages)
├── tests/                 # Test suite
├── mkdocs.yml             # Docs site configuration
├── pyproject.toml         # Build and dependency configuration (uv)
└── README.md              # Public documentation and examples
```

---

## Standards & Conventions

### 1. Model Definition (`atonix/object_models/`)
- Always use `Pydantic` models.
- Match field names exactly with the Swagger spec (or use `Field(alias=...)` if necessary, though the project currently seems to use camelCase in params but Snake Case or Camel Case in models depending on the JSON response).
- Use `Optional` and default values where appropriate.
- Shared wrapper: Use `atonix.object_models.common.APIResponse[T]` for standard Atonix API responses.

### 2. Client Implementation (`atonix/<resource>.py`)
- Each major API area (Assets, Issues, etc.) has its own file and class.
- Resource classes are initialized with an instance of `AtonixClient`.
- **Pagination**: Implement automatic pagination for endpoints that support `skip` and `take`.
- **Methods**: Use descriptive names that reflect the action (e.g., `get_children`, `create_issue`).

### 3. Authentication
- Managed centrally in `client.py` using RSA-based signing.
- Developers should not need to worry about auth headers when implementing resource methods.

### 4. Tooling
- **Dependency Management**: `uv`
- **Linting/Formatting**: `ruff`
- **Documentation**: MkDocs + Material + mkdocstrings (`mkdocs.yml`, pages in `docs/`)
- **Testing**: `pytest` with `responses` for HTTP mocking

### 5. Testing Standards

The project maintains a comprehensive test suite to ensure code quality and API compliance.

#### Test Categories
- **Unit Tests** (`tests/`): Mock all external dependencies, test business logic
- **Integration Tests** (`tests/integration/`): Test against live API (use sparingly, marked with `@pytest.mark.integration`)
- **Model Tests** (`tests/test_object_models.py`): Validate Pydantic model parsing and serialization

#### Test Implementation Guidelines
- Use `responses` library to mock HTTP calls in unit tests
- Shared test data factories in `tests/conftest.py`
- Test fixtures should match actual API response schemas
- Cover both success and error scenarios
- Test pagination logic where applicable
- Run tests before committing: `uv run pytest tests/`

#### Test Commands
```bash
# Run all tests
uv run pytest tests/

# Run with coverage
uv run pytest tests/ --cov=atonix

# Run specific test file
uv run pytest tests/test_assets.py -v

# Run integration tests (requires live API access)
uv run pytest tests/integration/ -m integration
```

#### Adding New Tests
When implementing new features:
1. Add corresponding unit tests with mocked responses
2. Update `conftest.py` fixtures if new sample data is needed
3. Ensure test data matches Swagger specifications
4. Test both happy path and error conditions
5. Verify pagination works correctly for list endpoints

---

## Agentic Development Workflow

When tasked with adding a new feature or updating an existing one:

1.  **Read the Spec**: Consult the relevant Swagger `.json` file obtained from your Prometheus APM tenant.
2.  **Define Models**: Create or update Pydantic models in `atonix/object_models/`.
3.  **Implement Resource Methods**: Add the corresponding methods to the resource class (e.g., `atonix/issues.py`).
4.  **Verify**: Ensure types are correct and pagination is handled if applicable.
5.  **Update Docs**: Add examples to the matching `docs/guide/` page (and README if it's a headline feature); add new public classes to `docs/reference/`.

---

## Licensing & Hygiene (for Agent)
- All code is `LGPL-3.0-or-later`. New `.py` files must begin with the SPDX header:
  `# SPDX-License-Identifier: LGPL-3.0-or-later` and `# Copyright (c) 2023-2026 Kolton Stimpert`.
- Never commit credentials, private keys, tenant URLs, customer/plant names, or real tag/asset IDs.
  Use synthetic GUIDs in tests and fixtures.
- Commits must carry a DCO sign-off (`git commit -s`).
