"""Apply sources/tags.tsv and validate domain coverage.

Usage:
    python3 scripts/tag_domains.py           # apply + validate against data/legal.db
    python3 scripts/tag_domains.py --check   # validate only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import JuristEngine, fold

ROOT = Path(__file__).resolve().parents[1]
ROUTING = ROOT / "sources" / "routing_keywords.tsv"
CORPUS = ROOT / "sources" / "corpus.yaml"


def _corpus_act_domains() -> set[str]:
    tags: set[str] = set()
    if not CORPUS.exists():
        return tags
    current: list[str] | None = None
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- id:"):
            current = []
        elif current is not None and stripped.startswith("domains:"):
            rest = stripped.split(":", 1)[1].strip()
            if rest.startswith("["):
                for item in rest.strip("[]").split(","):
                    tag = fold(item.strip().strip("'\""))
                    if tag:
                        tags.add(tag)
                current = None
    return tags


def _routing_targets() -> set[str]:
    targets: set[str] = set()
    if not ROUTING.exists():
        return targets
    for line in ROUTING.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 2:
            targets.update(fold(x) for x in fields[1].split(",") if fold(x))
    return targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("data/legal.db"))
    parser.add_argument("--check", action="store_true", help="validate only, do not apply tags.tsv")
    args = parser.parse_args()
    engine = JuristEngine(args.db, seed=False)
    try:
        applied = None if args.check else engine.apply_tags()
        missing_acts = [r[0] for r in engine.conn.execute(
            "SELECT id FROM acts WHERE NOT EXISTS (SELECT 1 FROM act_domains d WHERE d.act_id=acts.id)"
        )]
        provision_tags = engine.conn.execute("SELECT COUNT(*) FROM provision_domains").fetchone()[0]
        corpus_tags = _corpus_act_domains()
        db_tags = {r[0] for r in engine.conn.execute("SELECT tag FROM domains")}
        known = corpus_tags | db_tags
        extra_routing = sorted(_routing_targets() - known)
        result = {
            "valid": not missing_acts and not extra_routing and provision_tags > 0,
            "applied": applied,
            "missing_act_domains": missing_acts,
            "provision_domain_rows": provision_tags,
            "routing_targets_not_in_corpus": extra_routing,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1
    finally:
        engine.close()


if __name__ == "__main__":
    raise SystemExit(main())
