"""Structural and temporal validation for a jurist SQLite database."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import JuristEngine


def validate(engine: JuristEngine) -> list[str]:
    errors: list[str] = []
    if engine.conn.execute("SELECT COUNT(*) FROM provisions WHERE trim(text)='' OR text IS NULL").fetchone()[0]:
        errors.append("EMPTY_PROVISION_TEXT")
    if engine.conn.execute("SELECT COUNT(*) FROM provisions p LEFT JOIN acts a ON a.id=p.act_id WHERE a.id IS NULL").fetchone()[0]:
        errors.append("ORPHAN_PROVISION")
    if engine.conn.execute("SELECT COUNT(*) FROM act_versions v LEFT JOIN acts a ON a.id=v.act_id WHERE a.id IS NULL").fetchone()[0]:
        errors.append("ORPHAN_VERSION")
    for row in engine.conn.execute("SELECT valid_from,valid_to,id FROM provisions WHERE valid_from IS NOT NULL AND valid_to IS NOT NULL"):
        if row[0] > row[1]:
            errors.append(f"INVALID_INTERVAL:{row[2]}")
    duplicate = engine.conn.execute("SELECT act_version_id,canonical_citation,COUNT(*) FROM provisions GROUP BY act_version_id,canonical_citation HAVING COUNT(*)>1").fetchone()
    if duplicate:
        errors.append(f"DUPLICATE_CITATION:{duplicate[1]}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/legal.db"))
    args = parser.parse_args()
    engine = JuristEngine(args.db, seed=True)
    try:
        errors = validate(engine)
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False))
        return 0 if not errors else 1
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
