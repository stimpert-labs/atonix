# Contributing to Atonix Python Client

Thank you for your interest in contributing to the Atonix Python client library! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager

If you don't have `uv` installed:

```bash
# On Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# On macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Initial Setup

1. [Fork the repository](https://github.com/stimpert-labs/atonix/fork) to your own GitHub account.

2. Clone your fork and add the upstream remote:
   ```bash
   git clone https://github.com/<your-username>/atonix.git
   cd atonix
   git remote add upstream https://github.com/stimpert-labs/atonix.git
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

This will install all runtime dependencies plus development tools (pytest, mypy, ruff, etc.).

---

## Code Quality Standards

### Linting and Formatting

We use [Ruff](https://docs.astral.sh/ruff/) for linting and code formatting.

**Before committing**, ensure your code passes linting:

```bash
uv run ruff check .
```

To auto-fix many issues:

```bash
uv run ruff check --fix .
```

### Configuration

Ruff is configured in `pyproject.toml`:
- Line length: 120 characters
- Target: Python 3.10+
- Selected rules: `E`, `F`, `I`, `B`, `UP`, `S`, `RUF`, `SIM`

### Pre-commit hooks

The repository ships a [`pre-commit`](https://pre-commit.com/) config that runs
the same lint and format checks as CI. Install the hooks once after cloning:

```bash
uv run pre-commit install
```

Then every `git commit` will auto-run ruff, ruff-format, and standard hygiene
hooks. To run all hooks on the whole tree:

```bash
uv run pre-commit run --all-files
```

---

## Type Checking

We use [mypy](https://mypy.readthedocs.io/) for static type checking.

Run type checks:

```bash
uv run mypy atonix
```

**Requirements**:
- All public APIs must have type hints
- Use modern type syntax: `str | None` instead of `Optional[str]`
- Include `from __future__ import annotations` at the top of files

---

## Testing

### Running Tests

Run the full test suite:

```bash
uv run pytest tests/
```

Run with coverage report:

```bash
uv run pytest tests/ --cov=atonix --cov-report=term-missing
```

Run specific test file:

```bash
uv run pytest tests/test_assets.py -v
```

### Writing Tests

- Use `respx` for mocking HTTP requests (httpx)
- Place test fixtures in `tests/conftest.py`
- Follow existing test patterns
- Aim for >85% code coverage
- Test both success and error scenarios

#### Example Test Structure

```python
import respx
from httpx import Response
from tests.conftest import BASE_URL, make_api_response


class TestMyFeature:
    @respx.mock
    def test_my_function(self, mock_client):
        # Mock the API response
        respx.get(f"{BASE_URL}/v1/endpoint").mock(return_value=Response(200, json=make_api_response([...])))

        # Test your code
        result = mock_client.my_feature.my_function()

        # Assertions
        assert len(result) == expected_count
```

---

## Code Style Guidelines

### General Principles

1. **Type Safety**: Use type hints everywhere
2. **Readability**: Code should be self-documenting
3. **DRY**: Don't repeat yourself - use base classes and helpers
4. **Descriptive Names**: Use clear, descriptive variable and function names

### Pydantic Models

- Place in `atonix/object_models/`
- Use `BaseModel` from pydantic
- Match field names to API spec (use `Field(alias=...)` if needed)
- Include docstrings for complex models

### Resource Classes

- Inherit from `BaseResource`
- Use `_get_paginated()` for paginated endpoints
- Use `_get_single()` for single-item endpoints
- Include comprehensive docstrings with Google-style formatting

#### Example

```python
def get_items(self, asset_id: str, skip: int = 0, take: int = 500) -> list[Item]:
    """
    Retrieve items for an asset.

    Args:
        asset_id: The unique identifier (GUID) of the asset.
        skip: Number of items to skip for pagination.
        take: Number of items to retrieve per page.

    Returns:
        A list of Item objects.
    """
    params = {"assetId": asset_id}
    return self._get_paginated("/v1/items", Item, params=params, skip=skip, take=take)
```

---

## Pull Request Process

### Workflow

Contributions are accepted through pull requests from forks. Direct pushes to `main` are not allowed.

1. Sync your fork with upstream and create a topic branch:
   ```bash
   git fetch upstream
   git checkout -b feature/add-xyz upstream/main
   ```
2. Make your changes, committing with a sign-off (`git commit -s`).
3. Push the branch to your fork:
   ```bash
   git push -u origin feature/add-xyz
   ```
4. Open a pull request from your fork's branch against `stimpert-labs/atonix:main`.
5. CI runs automatically. For first-time contributors, a maintainer must approve the workflow run before it starts.
6. A code owner (see [`.github/CODEOWNERS`](.github/CODEOWNERS)) reviews the PR. All required checks must pass and the PR must be approved before it can be merged.

To keep your branch current while the PR is open, rebase on upstream:

```bash
git fetch upstream
git rebase upstream/main
git push --force-with-lease
```

Maintainers with write access may push branches directly to this repository instead of using a fork, but changes still land through a reviewed pull request.

### Before Submitting

1. **Tests pass**: `uv run pytest tests/`
2. **Linting passes**: `uv run ruff check .`
3. **Type checking passes**: `uv run mypy atonix`
4. **Coverage maintained**: Aim for no decrease in coverage

### PR Guidelines

1. **Branch naming**: Use descriptive names like `feature/add-xyz` or `fix/issue-123`
2. **Commit messages**: Use clear, descriptive messages
   - Format: `<type>: <description>`
   - Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
   - Example: `feat: add support for model configuration updates`

3. **Sign-off (DCO)**: Every commit must be signed off — see [Developer Certificate of Origin](#developer-certificate-of-origin-dco).

4. **Description**: Include:
   - What changes were made
   - Why the changes were needed
   - Any breaking changes
   - Testing performed

5. **Size**: Keep PRs focused and reasonably sized

---

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def my_function(param1: str, param2: int = 0) -> bool:
    """
    Brief description of what the function does.

    Longer explanation if needed, describing behavior,
    edge cases, or important implementation details.

    Args:
        param1: Description of param1.
        param2: Description of param2 (default: 0).

    Returns:
        Description of return value.

    Raises:
        ValueError: When param1 is empty.
        APIError: When the API request fails.
    """
```

### Update README

If adding new features:
- Add usage examples to `README.md`
- Keep examples clear and concise
- Show the most common use case

### Docs Site

The docs are built with [MkDocs](https://www.mkdocs.org/) and
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). Guide pages are Markdown in
`docs/`, and the API reference is generated from docstrings by
[mkdocstrings](https://mkdocstrings.github.io/). The nav is defined in `mkdocs.yml`.

```bash
uv run mkdocs serve           # live preview at http://127.0.0.1:8000
uv run mkdocs build --strict  # what CI runs; warnings fail the build
```

When adding a public class, add it to the matching page under `docs/reference/`.

---

## Building the Package

We use `uv` to build distribution artifacts (wheel and source distribution).

```bash
uv build
```

The build artifacts are placed in the `dist/` directory:
- `atonix-{version}.tar.gz` (source distribution)
- `atonix-{version}-py3-none-any.whl` (wheel)

For development, install the package in editable mode:

```bash
uv sync
# or
uv pip install -e .
```

### Verifying an Installation

After building or installing the package, you can run the smoke test at
`scripts/verify_install.py` to confirm the install is healthy. It checks that
the package and its `cryptography` dependency import cleanly and that
`AtonixClient` instantiates with all resource attributes wired up. No network
calls or real credentials are involved.

```bash
uv run python scripts/verify_install.py
```

The script exits non-zero on failure, so it's also suitable for use as a CI
smoke-test step.

---

## Release Process

### How changes reach users

`main` is the only long-lived branch and is always releasable. Every change lands
through a squash-merged PR, and anything user-visible adds an entry under
`## [Unreleased]` in `CHANGELOG.md`. That section, plus its compare link at the
bottom of the file, is the list of what's merged but not yet released.

Nothing reaches PyPI until a **release PR** changes the version in
`pyproject.toml`. When that PR merges, `.github/workflows/release.yml`:

1. sees a version that has no `vX.Y.Z` tag yet,
2. builds the sdist and wheel and runs `twine check`,
3. publishes to PyPI (Trusted Publisher, `pypi` environment),
4. creates the `vX.Y.Z` tag and a GitHub Release using that version's changelog
   section as the notes,
5. deploys the API docs (`docs.yml`).

The tag is created only after PyPI accepts the upload, so a tag always means a
published release. Other changes to `pyproject.toml`, such as Dependabot updates,
leave the version alone, and the workflow skips them. Don't push `v*` tags or run
`uv publish` by hand.

There are no `develop`, release, or hotfix branches. Fixes go to `main` and ship
as a patch release. If a 1.x line ever needs backports, create a maintenance
branch from its tag at that point.

### Versioning

We follow [Semantic Versioning](https://semver.org/). While we're on `0.x`:

- **Patch** (`0.6.0` → `0.6.1`): bug fixes and security fixes only.
- **Minor** (`0.6.0` → `0.7.0`): new features, *and* any breaking change.
  Breaking changes must be called out in the changelog. Users should pin
  `atonix~=0.6` to get fixes without breaking changes.
- **Major** (`1.0.0`): once the public API has gone through a few minor
  releases without breaking changes.

### When to release

Release when there's something user-visible in `[Unreleased]`, not on a schedule:

- **Bug and security fixes:** release a patch as soon as the fix merges.
- **Features:** release when the feature is done, or batch related ones. Don't
  leave user-visible entries unreleased for more than about two weeks.
- **Dependency, CI, docs, and test-only changes:** these don't need a release on
  their own.

### Cutting a release

Replace `minor` with `patch` or `major` as needed.

1. **Update `main` and check what's unreleased.** Read `## [Unreleased]` in
   `CHANGELOG.md` and edit it on `main` first (through a normal PR) if anything
   is missing or unclear. It becomes the release notes as written.
   ```bash
   git switch main
   git pull
   uv run bump-my-version show-bump        # shows the patch / minor / major options
   ```

2. **For releases that change API behavior, run the integration tests** against
   your tenant. CI can't run these, and they're the main check that the release
   works against a real API.
   ```bash
   export ATONIX_API_KEY=...               # your API key
   export ATONIX_PRIVATE_KEY_PATH=...      # path to your PEM private key
   export ATONIX_ENVIRONMENT=US            # optional, defaults to US
   uv run pytest tests/integration -m integration
   ```

3. **Create the release branch and bump the version.** `bump-my-version` updates
   `pyproject.toml`, `uv.lock`, and `CHANGELOG.md` (renames `[Unreleased]` to the
   version and date, and updates the compare links). It needs a clean working tree.
   ```bash
   VERSION="$(uv run bump-my-version show new_version --increment minor)"
   git switch -c "release/v$VERSION"
   uv run bump-my-version bump minor
   git diff                                # check the version and changelog edits
   git commit -s -am "Release v$VERSION"
   git push -u origin "release/v$VERSION"
   ```

4. **Open the PR** titled `Release vX.Y.Z` (GitHub prints a link after the push,
   or use `gh pr create --fill`). Wait for CI, then squash-merge it.

5. **Watch it publish.** Open **Actions → Release**. If the `pypi` environment
   requires approval, approve the deployment. When the run finishes, check:
   - <https://pypi.org/project/atonix/> shows the new version,
   - the GitHub Release `vX.Y.Z` exists with the changelog notes,
   - <https://atonix.stimpert-labs.dev> shows the new docs.

6. **Clean up the release branch:**
   ```bash
   git switch main
   git pull
   git branch -D "release/v$VERSION"
   git push origin --delete "release/v$VERSION"   # skip if GitHub already deleted it
   ```

### If something goes wrong

- **A job failed for a transient reason** (network, PyPI outage): re-run the
  failed jobs from the Actions page. Publishing skips files already on PyPI, so
  re-running is safe.
- **The build or publish failed because of a problem in the repo:** fix it in a
  normal PR. Merging that PR won't release by itself unless it touches
  `pyproject.toml`, so afterwards run **Actions → Release → Run workflow** on
  `main`. It releases the current version if that version isn't tagged yet.
- **A broken version reached PyPI:** PyPI files can't be replaced. Yank the
  version on PyPI (Manage project → Releases → Options → Yank), fix the problem
  on `main`, and release a new patch.
- **Docs didn't deploy:** run **Actions → Docs → Run workflow** on `main`.

### Repository settings the release depends on

- The `pypi` and `github-pages` environments must allow deployments from the
  `main` branch (Settings → Environments → Deployment branches and tags).
- PyPI's Trusted Publisher for `atonix` must point at this repository, the
  workflow file `release.yml`, and the environment `pypi`.
- If you add a ruleset that restricts creating `v*` tags, make sure the release
  workflow can still create them, or the "Tag and create GitHub Release" job fails
  after publishing (re-run it once the ruleset is fixed).

### Dependency bounds

`atonix` is a library, so the dependency ranges in `pyproject.toml` are what
users' installers have to satisfy:

- Use a minimum version only (`httpx>=0.27.0`). Don't add upper caps; they cause
  install conflicts for users and force a release every time a dependency ships
  a new version.
- Raise a minimum only when `atonix` needs the newer version (a feature it uses,
  or a security fix in that dependency), and note it in the changelog.
- Dependabot uses `versioning-strategy: widen`, so it updates `uv.lock` (what CI
  tests against) without raising those minimums.

---

## Getting Help

- Check existing issues for similar problems
- Review the [AGENTS.md](AGENTS.md) development guide
- Consult the Swagger/OpenAPI documentation available from your own Prometheus APM tenant
- See [SUPPORT.md](SUPPORT.md) — support is best-effort with no guaranteed response time

Do **not** include credentials, private keys, tenant URLs, customer names, or real plant/asset data in
issues, pull requests, tests, or fixtures. Use synthetic identifiers.

---

## Developer Certificate of Origin (DCO)

This project uses the [Developer Certificate of Origin 1.1](https://developercertificate.org/) instead
of a CLA. By signing off a commit you certify that you wrote the contribution, or otherwise have the
right to submit it under the project's license (for example, that your employer permits it).

Sign off every commit by adding a `Signed-off-by` trailer:

```bash
git commit -s -m "fix: handle empty tag list"
```

This appends `Signed-off-by: Your Name <you@example.com>` using your git `user.name` and `user.email`.
Pull requests containing commits without a sign-off cannot be merged.

---

## License

By contributing, you agree that your contributions will be licensed under the
**GNU Lesser General Public License v3.0 or later** (`LGPL-3.0-or-later`), the same license as the
project. See [COPYING.LESSER](COPYING.LESSER) and [COPYING](COPYING).

New source files should start with:

```python
# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
```

Contributors retain copyright to their contributions; you may add your own copyright line beneath the
existing one in files you substantially modify.
