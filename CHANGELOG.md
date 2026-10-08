# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/stimpert-labs/atonix/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/stimpert-labs/atonix/releases/tag/v0.5.0
