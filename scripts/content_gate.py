#!/usr/bin/env python3
"""Content gate for downloaded legislation text.

Rejects content that is not real legal text BEFORE anything is saved into
ingest/ or raw/:
  - RDF dumps from the Cellar ontology (rdf:RDF / xmlns:rdf);
  - text with no article structure (regex `Articolul\\s+\\d`);
  - text shorter than MIN_LENGTH characters.

Usage (module):
    from content_gate import check
    ok, reason = check(content, "eu")

Usage (CLI):
    python3 scripts/content_gate.py <file> [--kind eu|ro]
    -> prints {"file": ..., "ok": ..., "reason": ...} and exits 0/1.
"""
import argparse
import json
import re

MIN_LENGTH = 5000
RDF_TAG = "<rdf:RDF"
RDF_NS = "xmlns:rdf"
ARTICLE_RE = re.compile(r"Articolul\s+\d", re.IGNORECASE)
OJ_LANDING_MARK = "Official Journal of the European Union"


def check(content: str, kind: str) -> tuple[bool, str]:
    """Validate downloaded content. Returns (ok, reason)."""
    if kind not in ("eu", "ro"):
        return False, "bad kind: expected 'eu' or 'ro'"
    if content.lstrip().startswith(RDF_TAG) or RDF_NS in content[:500]:
        return False, "RDF dump (Cellar ontology), not legal text"
    n_articles = len(ARTICLE_RE.findall(content))
    # EUR-Lex rate limiting serves an OJ landing page (~10-20 KB) instead of
    # the act; reject it explicitly so it is never saved as valid legal text.
    if (10000 <= len(content) <= 20000 and OJ_LANDING_MARK in content
            and n_articles == 0):
        return False, "RATE_LIMITED_LANDING_PAGE"
    if len(content) < MIN_LENGTH:
        return False, f"too short: {len(content)} < {MIN_LENGTH} chars"
    if n_articles == 0:
        return False, "no article structure: regex 'Articolul\\s+\\d' not found"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate downloaded legislation content.")
    ap.add_argument("file", help="file to check")
    ap.add_argument("--kind", choices=("eu", "ro"), default="eu")
    args = ap.parse_args()
    try:
        with open(args.file, encoding="utf-8", errors="replace") as f:
            content = f.read()
    except OSError as e:
        print(json.dumps({"file": args.file, "ok": False, "reason": f"unreadable: {e}"}))
        return 1
    ok, reason = check(content, args.kind)
    print(json.dumps({"file": args.file, "ok": ok, "reason": reason}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
