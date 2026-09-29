"""Shared text normalisation for ingestion and query tests."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import fold, normalize  # noqa: F401

__all__ = ["normalize", "fold"]

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    args = parser.parse_args()
    print(normalize(args.text))
