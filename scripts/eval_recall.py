"""Run the hand-written retrieval regression set and report recall@10."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import JuristEngine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=Path("tests/eval_questions_40.tsv"))
    parser.add_argument("--db", type=Path, default=Path("data/legal.db"))
    parser.add_argument("--threshold", type=float, default=0.9)
    args = parser.parse_args()
    engine = JuristEngine(args.db, seed=False)
    try:
        if engine.conn.execute("SELECT COUNT(*) FROM acts").fetchone()[0] == 0:
            print(json.dumps({"ok": False, "error": "empty database; refuse to seed fixtures for eval"}, ensure_ascii=False))
            return 2
        total = covered = 0
        failures = []
        with args.questions.open(encoding="utf-8", newline="") as stream:
            for row in csv.reader(stream, delimiter="\t"):
                if not row or row[0].startswith("#") or len(row) < 2:
                    continue
                total += 1
                expected = {item.strip() for item in row[1].split(",") if item.strip()}
                result = engine.legal_search(row[0], limit=10)
                found = {hit["provision_id"] for hit in result.get("results", [])}
                if expected & found:
                    covered += 1
                else:
                    failures.append({
                        "question": row[0],
                        "expected": sorted(expected),
                        "found": sorted(found),
                        "routed_domains": result.get("routed_domains", []),
                    })
        recall = covered / total if total else 0.0
        output = {"total": total, "covered": covered, "recall_at_10": round(recall, 4), "threshold": args.threshold, "passed": recall >= args.threshold, "failures": failures}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if output["passed"] else 1
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
