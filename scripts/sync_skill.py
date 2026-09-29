"""Synchronize the runtime skill copy from this repository.

Only the files and directories listed in ``SYNC_ROOTS`` are considered.  The
script deliberately never removes files from the destination: in particular,
its data/raw directories and any other destination-only artifacts are left
untouched.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil


SYNC_ROOTS = (
    "SKILL.md",
    "AGENTS.md",
    "README.md",
    "pyproject.toml",
    "sources",
    "scripts",
    "jurist",
    "tests",
)
EXCLUDED_PARTS = {"__pycache__", ".git", "data", "raw", "ingest", "docs"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _global_root() -> Path:
    configured = os.environ.get("JURIST_GLOBAL_SKILL")
    return Path(configured).expanduser() if configured else Path.home() / ".claude" / "skills" / "jurist"


def _source_files(root: Path):
    for relative in SYNC_ROOTS:
        source = root / relative
        if source.is_file():
            yield Path(relative)
        elif source.is_dir():
            for path in sorted(source.rglob("*")):
                if path.is_file() and not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
                    yield path.relative_to(root)


def _drift(repo: Path, destination: Path) -> list[tuple[Path, str]]:
    differences: list[tuple[Path, str]] = []
    for relative in _source_files(repo):
        source = repo / relative
        target = destination / relative
        if not target.exists():
            differences.append((relative, "missing"))
        elif not target.is_file() or source.read_bytes() != target.read_bytes():
            differences.append((relative, "different"))
    return differences


def sync(repo: Path, destination: Path, check: bool = False) -> int:
    # A missing global copy is intentionally not an error in check mode: this
    # supports machines where the optional global skill has not been installed.
    if check and not destination.exists():
        return 0

    differences = _drift(repo, destination) if destination.exists() else [
        (relative, "missing") for relative in _source_files(repo)
    ]
    if check:
        for relative, state in differences:
            print(f"{state}: {relative}")
        return 1 if differences else 0

    for relative in _source_files(repo):
        source = repo / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synchronize the global jurist skill copy")
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args(argv)
    return sync(_repo_root(), _global_root(), args.check)


if __name__ == "__main__":
    raise SystemExit(main())
