"""Safe update entry point.

Network fetch is intentionally separate and opt-in. Running this command on an
unchanged local database is a complete no-op, which is the Stage H gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import JuristEngine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/legal.db"))
    parser.add_argument("--network", action="store_true", help="reserved; run source fetchers explicitly")
    args = parser.parse_args()
    engine = JuristEngine(args.db)
    try:
        result = engine.update()
        if args.network:
            result["warnings"].append("FETCHERS_MUST_BE_RUN_EXPLICITLY")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
