"""scripts/release_info.py: version and CHANGELOG notes used by the CI release job."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import release_info as ri  # noqa: E402


def test_current_version_has_changelog_notes():
    version = ri.current_version()
    assert version.count(".") == 2
    assert ri.release_notes(version).startswith("- ")


def test_notes_stop_at_next_section(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n', encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 1.2.0 — 2026-10-01\n\n- nou\n\n## 1.1.0 — 2026-09-01\n\n- vechi\n", encoding="utf-8")
    assert ri.current_version(tmp_path) == "1.2.0"
    assert ri.release_notes("1.2.0", tmp_path) == "- nou"
    assert ri.release_notes("1.1.0", tmp_path) == "- vechi"


def test_missing_section_fails(tmp_path):
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## 1.0.0\n\n- x\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        ri.release_notes("1.0.1", tmp_path)
