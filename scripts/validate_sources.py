"""Validate corpus.yaml metadata without fetching legislation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install PyYAML to validate sources/corpus.yaml") from exc

ALLOWED = {"eur-lex.europa.eu", "publications.europa.eu", "legislatie.just.ro", "monitoruloficial.ro", "www.dataprotection.ro", "anpc.ro"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=Path("sources/corpus.yaml"))
    args = parser.parse_args()
    data = yaml.safe_load(args.corpus.read_text(encoding="utf-8"))
    errors = []
    ids = set()
    for act in data.get("acts", []):
        aid = act.get("id")
        if not aid or aid in ids: errors.append(f"duplicate_or_missing_id:{aid}")
        ids.add(aid)
        for key in ("fetch", "authority_class", "version_coverage", "domains", "aliases", "summary_ro", "source"):
            if key not in act: errors.append(f"{aid}:missing:{key}")
        links = list(act.get("source", {}).get("links", [])) + ([act.get("fetch", {}).get("url")] if act.get("fetch", {}).get("url") else [])
        for link in links:
            if urlparse(link).hostname not in ALLOWED: errors.append(f"{aid}:non_official_host:{link}")
    result = {"valid": not errors, "acts": len(ids), "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
