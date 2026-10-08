# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Tests for scripts/changelog_section.py (used by the release workflows)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "changelog_section.py"
_spec = importlib.util.spec_from_file_location("changelog_section", SCRIPT)
assert _spec is not None and _spec.loader is not None
changelog_section = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changelog_section)

CHANGELOG = """\
# Changelog

Intro text.

## [Unreleased]

### Added
- New thing.

## [0.2.0] - 2026-01-02

### Fixed
- A bug.

## [0.1.0] - 2026-01-01

- Initial release.

[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD
[0.2.0]: https://example.invalid/compare/v0.1.0...v0.2.0
"""


class TestExtractSection:
    def test_unreleased(self):
        assert changelog_section.extract_section(CHANGELOG, "Unreleased") == "### Added\n- New thing."

    def test_version_with_date(self):
        assert changelog_section.extract_section(CHANGELOG, "0.2.0") == "### Fixed\n- A bug."

    def test_v_prefix_is_ignored(self):
        assert changelog_section.extract_section(CHANGELOG, "v0.2.0") == "### Fixed\n- A bug."

    def test_last_section_stops_at_link_references(self):
        assert changelog_section.extract_section(CHANGELOG, "0.1.0") == "- Initial release."

    def test_missing_section(self):
        assert changelog_section.extract_section(CHANGELOG, "9.9.9") is None

    def test_empty_section(self):
        text = "## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n\n- Initial release.\n"
        assert changelog_section.extract_section(text, "Unreleased") == ""


class TestMain:
    @pytest.fixture
    def changelog(self, tmp_path: Path) -> Path:
        path = tmp_path / "CHANGELOG.md"
        path.write_text(CHANGELOG, encoding="utf-8")
        return path

    def test_prints_section(self, changelog: Path, capsys: pytest.CaptureFixture[str]):
        assert changelog_section.main(["0.2.0", "--changelog", str(changelog)]) == 0
        assert capsys.readouterr().out.strip() == "### Fixed\n- A bug."

    def test_missing_section_fails(self, changelog: Path, capsys: pytest.CaptureFixture[str]):
        assert changelog_section.main(["9.9.9", "--changelog", str(changelog)]) == 1
        assert "not found" in capsys.readouterr().err

    def test_empty_section_fails(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
        path = tmp_path / "CHANGELOG.md"
        path.write_text("## [Unreleased]\n\n## [0.1.0] - 2026-01-01\n- x\n", encoding="utf-8")
        assert changelog_section.main(["Unreleased", "--changelog", str(path)]) == 1
        assert "is empty" in capsys.readouterr().err
