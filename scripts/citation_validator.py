"""CLI wrapper for the deterministic, zero-LLM citation validator.

Retrieval-log scoping: validation considers only rows logged in the current
session. The session id is the ``JURIST_SESSION`` environment variable when
set, else ``current``; override per run with ``--session``.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import JuristEngine


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("--db", type=Path, default=Path("data/legal.db"))
    parser.add_argument("--as-of", dest="as_of")
    parser.add_argument("--session", default=os.environ.get("JURIST_SESSION") or "current",
                        help="retrieval-log session id (default: $JURIST_SESSION or 'current')")
    parser.add_argument("--retrieved", action="append", default=[], help="canonical citation retrieved earlier in the session")
    args = parser.parse_args()
    engine = JuristEngine(args.db, seed=False, session=args.session)
    try:
        engine.retrieval_log = [{"provision_id": citation} for citation in args.retrieved]
        result = engine.validate_citations(args.draft.read_text(encoding="utf-8"), args.as_of)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
