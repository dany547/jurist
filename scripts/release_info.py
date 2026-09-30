#!/usr/bin/env python3
"""Release metadata for CI: the current version and its CHANGELOG notes.

    python3 scripts/release_info.py version   # 0.1.7 (from pyproject.toml)
    python3 scripts/release_info.py notes     # body of "## 0.1.7 — ..." in CHANGELOG.md

Exits non-zero when the CHANGELOG has no section for the current version, so a
version bump without release notes fails CI instead of publishing an empty release.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def current_version(root: Path = ROOT) -> str:
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("release_info: no version in pyproject.toml")
    return match.group(1)


def release_notes(version: str, root: Path = ROOT) -> str:
    lines = (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    heading = re.compile(rf"^##\s+{re.escape(version)}(\s|$)")
    start = next((i for i, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        raise SystemExit(f"release_info: CHANGELOG.md has no '## {version}' section")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    notes = "\n".join(lines[start + 1:end]).strip()
    if not notes:
        raise SystemExit(f"release_info: CHANGELOG.md section '## {version}' is empty")
    return notes


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {"version", "notes"}:
        print(__doc__, file=sys.stderr)
        return 2
    version = current_version()
    print(version if argv[1] == "version" else release_notes(version))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
