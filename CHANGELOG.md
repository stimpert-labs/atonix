# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `Issues.create_discussion_entry()` (sync and async) adds a discussion entry to an issue and
  returns the new `IssueDiscussionEntry`, including an `AttachmentUpload` link for each file
  named in `attachment_files`. (#23)
- The package now ships a `py.typed` marker (PEP 561), so `mypy` and `pyright` pick up its type
  hints. (#26)
- `allow_insecure` client option to opt in to a plain `http://` custom environment URL. (#20)

### Fixed
- Requests with a JSON body are now serialized once, and the signature is computed from the
  exact body text that is sent (`Content-Type: application/json`). Before, httpx re-serialized
  the body, so the signed and sent body could differ (always with httpx 0.27, and for non-ASCII
  bodies with 0.28). The bytes sent are unchanged from httpx 0.28's `json=` encoding. (#13)
- Request signing now encodes the challenge string the way the Atonix auth spec does (.NET
  `Encoding.ASCII`, so each non-ASCII character becomes `?`) instead of raising
  `UnicodeEncodeError`. Non-ASCII query values and JSON bodies now sign correctly. (#12)
- `max_retries=0` no longer makes `request()` return `None` without sending anything. Every
  request is attempted at least once, and a negative `max_retries` raises `ValueError`. (#15)
- `Asset.create_date` and `Asset.change_date` are now optional, so a null date no longer breaks
  asset iteration mid-page. (#21)
- `Issues.delete_keywords()` now sends the request body as an array of `IssueKeyword` objects
  (`[{"KeywordDesc": ...}]`), as the API spec defines, instead of bare strings. It also accepts
  `IssueKeyword` objects, and an empty list no longer sends a request. (#27)

### Changed
- **Breaking:** custom environment URLs must use `https://`. `http://` URLs raise `ValueError`
  unless `allow_insecure=True` is passed, and malformed URLs (no scheme or host) are rejected. (#20)
- The `cryptography` requirement no longer has an upper bound (now `cryptography>=48.0.1`), so
  installing `atonix` no longer blocks newer `cryptography` releases in your environment.
- The docs site moved from pdoc to Material for MkDocs. It has a quick start, an authentication
  guide, a "Sync or async?" page, per-resource usage examples with sync/async tabs, pagination
  and error-handling guides, and an API reference grouped into clients, resources, async
  resources, object models, and exceptions.

## [0.6.0] - 2026-10-08

### Added
- `get_data_for_range` (sync and async) now splits reads over the 250,000-point limit into
  sub-queries, by tag group and, when one tag alone is over the limit, by time window, then
  reassembles the per-tag series. Pass `chunk=False` to keep the old strict behavior. (#31)
- `QuerySizeError` (exported from `atonix`) is raised for oversized reads when `chunk=False`.
  It carries `limit`, `tag_count`, `timestamps_per_tag` and `total_points`. It subclasses
  both `AtonixError` and `ValueError`, so existing `except ValueError` handlers still catch it.

## [0.5.3] - 2026-10-08

### Fixed
- Version bumps (`bump-my-version`) now also update the project version recorded in
  `uv.lock`, and CI now runs `uv sync --locked` so a stale lockfile fails the build
  instead of the release workflow.
- updated dependencies for release and ci workflows

## [0.5.2] - 2026-10-08

v0.5.2 was tagged but never released due to issues with ci pipelines

### Added
- API reference documentation is now published to GitHub Pages at
  <https://atonix.stimpert-labs.dev> on each release (`.github/workflows/docs.yml`).

### Fixed
- Resolved the pre-existing mypy baseline in `atonix/base.py`, `atonix/models.py`, and
  `atonix/processdata.py`; the CI `type-check` job is now blocking.
- `get_data_for_range` no longer raises `TypeError` when a tag result omits `HttpCode`.
- `write_tag_data` now raises a descriptive `ValueError` (instead of `TypeError`) when a
  `TagData` entry is missing `timestamps` or `values`.

## [0.5.1] - 2026-10-08

### Fixed
- Updated `AtonixEnvironment` base URLs to the new Prometheus APM hosts:
  `US` → `https://api-us.pgapm.io`, `INDIA` → `https://api-in.pgapm.io`.

## [0.5.0] - 2026-10-07

First open-source release.

### Changed
- **Relicensed under the GNU Lesser General Public License v3.0 or later (LGPL-3.0-or-later).**
  License texts ship as `COPYING` (GPL-3.0) and `COPYING.LESSER` (LGPL-3.0), with a `NOTICE` file
  containing the no-warranty disclaimer and trademark/non-affiliation statement.
- Project moved to [stimpert-labs/atonix](https://github.com/stimpert-labs/atonix).
- README, CONTRIBUTING, and SECURITY updated for public, community-maintained development;
  contributions now require a DCO sign-off (`git commit -s`).
- Added `SUPPORT.md` (best-effort community support) and `AGENTS.md` (development guide).
- Polished `pyproject.toml` metadata (PEP 639 SPDX license expression, classifiers, keywords, URLs).
- Applied `ruff --fix` and `ruff format` across the tree (import ordering, removed unused imports,
  replaced a `lambda` assignment with a `def`, removed an unused local). No behavioral changes.

### Added
- Pre-commit configuration mirroring CI lint/format checks.
- GitHub Actions CI pipeline (ruff, mypy, pytest matrix on Python 3.10–3.13, build, pip-audit).
- CodeQL workflow for Python static analysis.
- Dependabot configuration for `pip` and `github-actions` ecosystems.
- Pull request template and issue templates.
- `bump-my-version` configuration for coordinated version bumps.
- Dormant PyPI release workflow wired for Trusted Publishers (OIDC).

### Known issues
- mypy currently reports ~15 pre-existing errors in `atonix/base.py`, `atonix/models.py`,
  and `atonix/processdata.py`. The CI `type-check` job is non-blocking until these are
  resolved.

## [0.4.5] - 2025-01-01

### Added
- Batched `TagData` writes — `write_tag_data` now packs multiple entries per POST.

### Changed
- Expanded the ruff ruleset to include `S`, `RUF`, and `SIM` checks.
- Documentation updates covering clock-sync auth requirements.

### Fixed
- Avoid logging full request/response payloads to prevent leaking sensitive data.
- Trimmed verbose `processdata` debug logs.
- Removed a double layer of retries that amplified transient failures.
- Corrected an optional type annotation on `tag_id`.

### Security
- Bumped `cryptography` to a patched release.

[Unreleased]: https://github.com/stimpert-labs/atonix/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/stimpert-labs/atonix/compare/v0.5.3...v0.6.0
[0.5.3]: https://github.com/stimpert-labs/atonix/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/stimpert-labs/atonix/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/stimpert-labs/atonix/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/stimpert-labs/atonix/releases/tag/v0.5.0
