"""Diff two parsed snapshots by canonical provision citation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def provisions(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    values = payload.get("provisions", payload.get("result", payload if isinstance(payload, list) else []))
    return {str(item.get("id") or item.get("canonical_citation")): item.get("text", "") for item in values}


def diff(old: dict[str, str], new: dict[str, str]) -> dict[str, list[str]]:
    return {"added": sorted(set(new) - set(old)), "modified": sorted(k for k in set(old) & set(new) if old[k] != new[k]), "removed": sorted(set(old) - set(new))}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    parser.add_argument("--changelog", type=Path)
    args = parser.parse_args()
    result = diff(provisions(args.old), provisions(args.new))
    if args.changelog:
        args.changelog.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"\n## Snapshot diff\n", f"- added: {len(result['added'])}", f"- modified: {len(result['modified'])}", f"- removed: {len(result['removed'])}"]
        for key in result["added"]: lines.append(f"  - added `{key}`")
        for key in result["modified"]: lines.append(f"  - modified `{key}`")
        for key in result["removed"]: lines.append(f"  - removed `{key}`")
        with args.changelog.open("a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
