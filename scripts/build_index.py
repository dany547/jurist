"""Build/rebuild the local SQLite index from deterministic normalized records."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import JuristEngine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/legal.db"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    engine = JuristEngine(args.db)
    try:
        if args.check_only:
            print(json.dumps({"status": "OK", "database": str(args.db), "provisions": engine.conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0]}, ensure_ascii=False))
            return 0
        engine.conn.execute("INSERT OR IGNORE INTO corpus_status(source,last_sync,status,documents,method) VALUES('build',datetime('now'),'built', (SELECT COUNT(*) FROM provisions),'SQLite FTS5')")
        engine.conn.commit()
        print(json.dumps({"status": "BUILT", "database": str(args.db), "provisions": engine.conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0]}, ensure_ascii=False))
        return 0
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
