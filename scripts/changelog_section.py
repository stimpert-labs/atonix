# SPDX-License-Identifier: LGPL-3.0-or-later
# Copyright (c) 2023-2026 Kolton Stimpert
"""Print one section of ``CHANGELOG.md``.

Used by the release workflows to check that ``[Unreleased]`` has entries and
to build PR bodies and GitHub Release notes::

    python scripts/changelog_section.py Unreleased
    python scripts/changelog_section.py 0.6.0
    python scripts/changelog_section.py v0.6.0 --changelog path/to/CHANGELOG.md

Exits with status 1 if the section is missing or has no content.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HEADING = re.compile(r"^## \[(?P<name>[^\]]+)\]")
LINK_REFERENCE = re.compile(r"^\[[^\]]+\]:\s")


def extract_section(text: str, name: str) -> str | None:
    """Return the body of the ``## [name]`` section, or ``None`` if absent.

    The body runs until the next ``## [`` heading or the trailing link
    reference definitions, and is stripped of surrounding blank lines.
    """
    name = name.removeprefix("v")
    body: list[str] = []
    found = False
    for line in text.splitlines():
        match = HEADING.match(line)
        if match:
            if found:
                break
            found = match.group("name") == name
            continue
        if found:
            if LINK_REFERENCE.match(line):
                break
            body.append(line)
    if not found:
        return None
    return "\n".join(body).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("section", help='Version (e.g. "0.6.0" or "v0.6.0") or "Unreleased".')
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    args = parser.parse_args(argv)

    section = extract_section(args.changelog.read_text(encoding="utf-8"), args.section)
    if section is None:
        print(f"error: section [{args.section}] not found in {args.changelog}", file=sys.stderr)
        return 1
    if not section:
        print(f"error: section [{args.section}] in {args.changelog} is empty", file=sys.stderr)
        return 1
    print(section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
