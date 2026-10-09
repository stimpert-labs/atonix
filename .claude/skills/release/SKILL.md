---
name: release
description: Cut an atonix release. Use when asked to release, publish, bump the version, or cut vX.Y.Z. Opens the release PR; merging it publishes to PyPI.
---

# Releasing atonix

The authoritative steps are in **CONTRIBUTING.md → Release Process** (esp. "Cutting a release").
Follow them; this skill only adds the judgment calls an agent needs. If the two disagree,
CONTRIBUTING.md wins; fix this file.

## Before bumping

1. Update `main` (`git fetch origin main`) and branch from it.
2. Read `## [Unreleased]` in `CHANGELOG.md`. It becomes the release notes verbatim, so if it is
   empty, missing entries, or unclear, stop and tell the user; fix it in a separate PR first.
3. Run `uv sync --group dev --locked`, `uv run ruff check .`, and `uv run pytest tests/`.
   Don't release on a red result.

## Picking the bump (0.x rules)

- **minor**: any `**Breaking:**` entry or any new feature under *Added*/*Changed*.
- **patch**: only bug or security fixes.
- **major**: never, unless the user explicitly asks for 1.0.

Preview with `uv run bump-my-version show-bump`. If unsure, ask the user.

## Integration tests

`tests/integration` needs tenant credentials that agent sessions don't have, so they are skipped.
For releases that change API behavior (signing, request bodies, endpoints), say in the PR
"Notes for reviewers" that they were not run and the user should run them before merging.
Don't hide the skip.

## Branch and PR

- Name the branch `release/vX.Y.Z`, even if the session assigns a different branch name. If the
  session is pinned to another branch, ask before pushing a differently named one.
- Run `uv run bump-my-version bump <minor|patch>`, review `git diff` (only `pyproject.toml`,
  `uv.lock`, `.bumpversion.toml`, `CHANGELOG.md` should change), then `git commit -s -am "Release vX.Y.Z"`.
- Open a PR titled `Release vX.Y.Z` using `.github/pull_request_template.md`. Call out breaking
  changes in the summary.

## Hard stops

- **Do not merge the release PR.** Merging is what publishes to PyPI and tags; that is the user's call.
- Never push `v*` tags, run `uv publish`, or edit the version by hand.
- Don't put credentials or tenant details in the PR.

## After the user merges

Point them to the checks in CONTRIBUTING.md step 5 (PyPI page, GitHub Release `vX.Y.Z`, docs site)
and the branch cleanup in step 6. If the workflow fails, see "If something goes wrong" there.
