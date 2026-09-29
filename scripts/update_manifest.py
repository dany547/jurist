"""Refresh manifest checksums for immutable raw snapshots without fetching."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, default=Path("raw"))
    parser.add_argument("--manifest", type=Path, default=Path("data/manifest.json"))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8")) if args.manifest.exists() else {"skill": "jurist", "schema_version": 1, "sources": {}, "acts": {}}
    entries = {}
    for path in sorted(args.raw_dir.rglob("*")) if args.raw_dir.exists() else []:
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries[str(path)] = {"path": str(path), "checksum": digest, "size": path.stat().st_size}
    manifest["built_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest["raw_snapshots"] = entries
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "UPDATED", "snapshots": len(entries), "manifest": str(args.manifest)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
