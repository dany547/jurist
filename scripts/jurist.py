"""Executable wrapper for installations that prefer scripts/jurist.py."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
