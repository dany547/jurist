#!/usr/bin/env python3
"""Ingest the real parsed corpus into data/legal.db, replacing fixtures.

Reads sources/corpus.yaml for act metadata, parses raw/ro/*.html with
parse_ro_html and ingest/eu/*.html with parse_eu_text, and inserts via
JuristEngine.ingest_snapshot — the official boundary between parse and
runtime.

Usage:
    python3 scripts/ingest_corpus.py --fresh   # delete DB + rebuild
    python3 scripts/ingest_corpus.py           # incremental (skip existing checksums)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
import html as _html
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from jurist.engine import JuristEngine, canonical_citation, fold, normalize

ROOT = Path(__file__).resolve().parents[1]
RO_DIR = ROOT / "raw" / "ro"
EU_DIR = ROOT / "ingest" / "eu"
MANIFEST_PATH = EU_DIR / "MANIFEST.json"
CORPUS_PATH = ROOT / "sources" / "corpus.yaml"
RELATIONS_PATH = ROOT / "sources" / "relations.tsv"
DB_PATH = ROOT / "data" / "legal.db"

_RO_TYPE_MAP = {"LEGE": "LEGE", "OUG": "OUG", "OG": "OG", "HG": "HG"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_eu_celex(celex_base: str) -> tuple[str, int, str]:
    """'32016R0679' → ('REG', 2016, '679')."""
    year = int(celex_base[1:5])
    type_char = celex_base[5]
    number = celex_base[6:].lstrip("0") or "0"
    act_type = {"R": "REG", "L": "DIR", "D": "DEC"}.get(type_char, "ACT")
    return act_type, year, number


def _ro_filename_to_meta(filename: str) -> tuple[str, str, int]:
    """'LEGE_190_2018.html' → ('LEGE', '190', 2018)."""
    stem = filename.rsplit(".", 1)[0]
    parts = stem.split("_")
    prefix = parts[0]
    act_type = _RO_TYPE_MAP.get(prefix, prefix)
    number = parts[1] if len(parts) > 1 else "0"
    year = int(parts[2]) if len(parts) > 2 else 0
    return act_type, number, year


def _safe_summary(entry) -> str:
    if isinstance(entry, dict):
        return entry.get("draft", "")
    return str(entry or "")


def _parse_eu_fallback(html_source: str, *, act_type: str = "REG",
                       number: str = "0", year: int = 0) -> list[dict]:
    """Minimal EU act parser for Romanian XHTML (Articolul N + paragraphs)."""
    try:
        root = ET.fromstring(html_source)
        plain = " ".join(root.itertext())
    except ET.ParseError:
        plain = re.sub(r"<[^>]+>", " ", html_source)
    plain = normalize(_html.unescape(plain))

    recital_re = re.compile(
        r"(?i)(?:^|\s)Considerentul\s+\(?([0-9]+)\)?\s*(.*?)(?=\sConsiderentul\s+\(?[0-9]+|\sArticolul\s+[0-9]+|\Z)")
    article_re = re.compile(
        r"(?i)(?:^|\s)Articolul\s+([0-9]+(?:\([0-9]+\))?)\s*(.*?)(?=\sArticolul\s+[0-9]+|\Z)")
    para_re = re.compile(r"(?m)(?:^|\n)\s*\(\s*([0-9]+)\s*\)")

    provisions: list[dict] = []
    seen_ids: set[str] = set()
    seq = 0

    for m in recital_re.finditer(plain):
        cid = canonical_citation("EU", act_type, number, year, "recital", m.group(1))
        if cid in seen_ids:
            continue
        seen_ids.add(cid)
        seq += 1
        provisions.append({"id": cid, "article": m.group(1), "provision_type": "recital",
                           "citable": 0, "text": normalize(m.group(2)), "sequence": seq})

    offset = seq
    for m in article_re.finditer(plain):
        article = m.group(1).split("(", 1)[0]
        body = normalize(m.group(2))
        paras = list(para_re.finditer(body))
        if paras:
            for i, pm in enumerate(paras):
                pnum = pm.group(1)
                cid = canonical_citation("EU", act_type, number, year, "article", article, pnum)
                if cid in seen_ids:
                    continue
                seen_ids.add(cid)
                seq += 1
                start = pm.end()
                end = paras[i + 1].start() if i + 1 < len(paras) else len(body)
                provisions.append({"id": cid, "article": article, "paragraph": pnum,
                                   "provision_type": "article", "citable": 1,
                                   "text": normalize(body[start:end]), "sequence": offset + seq})
        else:
            cid = canonical_citation("EU", act_type, number, year, "article", article)
            if cid not in seen_ids:
                seen_ids.add(cid)
                seq += 1
                provisions.append({"id": cid, "article": article, "provision_type": "article",
                                   "citable": 1, "text": body, "sequence": offset + seq})

    provisions.sort(key=lambda r: r["sequence"])
    return provisions


def ingest_relations(engine: JuristEngine) -> tuple[int, list[str]]:
    """Insert EU<->RO relations from sources/relations.tsv into act_relations.

    Idempotent (PK source,relation_type,target + INSERT OR IGNORE). Pairs whose
    act IDs are missing from the DB are SKIPPED and reported, not fatal.
    """
    skipped: list[str] = []
    if not RELATIONS_PATH.exists():
        skipped.append(f"relations file not found: {RELATIONS_PATH}")
        return 0, skipped
    known = {r["id"] for r in engine.conn.execute("SELECT id FROM acts")}
    inserted = 0
    for line_no, raw in enumerate(
            RELATIONS_PATH.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            skipped.append(f"relations.tsv:{line_no}: bad format")
            continue
        src, rel, tgt = (p.strip() for p in parts[:3])
        ref = parts[3].strip() if len(parts) > 3 else None
        missing = [a for a in (src, tgt) if a not in known]
        if missing:
            skipped.append(f"relations.tsv:{line_no}: missing acts: {', '.join(missing)}")
            continue
        cur = engine.conn.execute(
            "INSERT OR IGNORE INTO act_relations"
            "(source_act_id,relation_type,target_act_id,source_reference) VALUES(?,?,?,?)",
            (src, rel, tgt, ref))
        inserted += cur.rowcount
    engine.conn.commit()
    return inserted, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest real parsed corpus into data/legal.db")
    parser.add_argument("--fresh", action="store_true", help="Delete and rebuild the database")
    parser.add_argument("--db", type=Path, default=DB_PATH, help="Database path")
    args = parser.parse_args()

    if args.fresh and args.db.exists():
        args.db.unlink()
        print(f"Deleted {args.db}")

    with open(CORPUS_PATH, encoding="utf-8") as f:
        corpus = yaml.safe_load(f)
    act_map = {a["id"]: a for a in corpus.get("acts", [])}

    eu_manifest: list[dict] = []
    if MANIFEST_PATH.exists():
        eu_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    # Check if the official EU parser works.
    eu_parser_ok = False
    try:
        from scripts.parse_eu import parse_eu_html  # noqa: F401
        eu_parser_ok = True
    except Exception as exc:
        print(f"WARNING: parse_eu_html unavailable ({exc}); using fallback EU parser")

    engine = JuristEngine(args.db)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    stats = {"acts": 0, "provisions": 0, "text_bytes": 0, "ro": 0, "eu": 0, "errors": []}

    # ── RO acts ──────────────────────────────────────────────────────────
    if RO_DIR.exists():
        for html_path in sorted(RO_DIR.glob("*.html")):
            act_type, number, year = _ro_filename_to_meta(html_path.name)
            act_id = f"RO:{act_type}:{number}:{year}"
            y = act_map.get(act_id)
            if y is None:
                stats["errors"].append(f"RO: no corpus.yaml entry for {act_id}")
                continue

            html = html_path.read_text(encoding="utf-8")
            checksum = _sha256(html_path)
            source_url = ""
            if y.get("source"):
                links = y["source"].get("links", [])
                if links:
                    source_url = links[0]

            act = {
                "id": act_id, "jurisdiction": "RO", "source_system": "official",
                "act_type": act_type, "number": number, "year": year,
                "title": y.get("title", act_id), "short_title": y.get("short_title"),
                "issuer": y.get("issuer"), "status": "in_force",
                "authority_class": y.get("authority_class", "ro_law"),
                "version_coverage": y.get("version_coverage", "current_only"),
                "language": "ro",
                "scope_provisions": json.dumps(y.get("scope_provisions", []), ensure_ascii=False),
                "summary_ro": _safe_summary(y.get("summary_ro", "")),
                "source_url": source_url, "last_checked": now_iso[:10],
                "aliases": y.get("aliases", []), "domains": y.get("domains", []),
            }
            version = {"source_url": source_url, "checksum": checksum,
                       "retrieved_at": now_iso, "parser_version": "parse_ro_html-1"}

            try:
                from scripts.parse_ro import parse_ro_html
                provisions = parse_ro_html(html, act_type=act_type, number=number, year=year)
            except Exception as exc:
                stats["errors"].append(f"RO parse error {act_id}: {exc}")
                continue

            result = engine.ingest_snapshot(act, version, provisions)
            if result["status"] != "NO_OP":
                stats["acts"] += 1
                stats["provisions"] += result.get("added", len(provisions))
                stats["text_bytes"] += sum(len(p.get("text", "")) for p in provisions)
                stats["ro"] += 1
            for alias in y.get("aliases", []):
                engine.conn.execute("INSERT OR IGNORE INTO aliases(alias,act_id,priority) VALUES(?,?,?)",
                                   (fold(alias), act_id, 10))
            for domain in y.get("domains", []):
                engine._insert_domain(act_id, domain, is_act=True)
            engine.conn.commit()

    # ── EU acts ──────────────────────────────────────────────────────────
    for me in eu_manifest:
        if me.get("status") != "ok":
            continue
        celex_base = me["celex_base"]
        act_type, year, number = _parse_eu_celex(celex_base)
        act_id = f"EU:{act_type}:{year}:{number}"
        y = act_map.get(act_id)
        if y is None:
            stats["errors"].append(f"EU: no corpus.yaml entry for {act_id}")
            continue

        html_file = EU_DIR / f"{me.get('celex_downloaded', celex_base)}.html"
        if not html_file.exists():
            stats["errors"].append(f"EU: file not found {html_file}")
            continue

        html = html_file.read_text(encoding="utf-8")
        checksum = me.get("sha256", _sha256(html_file))
        source_url = me.get("url", "")

        act = {
            "id": act_id, "jurisdiction": "EU", "source_system": "official",
            "act_type": act_type, "number": number, "year": year,
            "title": y.get("title", act_id), "short_title": y.get("short_title"),
            "issuer": y.get("issuer"), "status": "in_force",
            "authority_class": y.get("authority_class", "eu_regulation"),
            "version_coverage": y.get("version_coverage", "point_in_time"),
            "language": "ro",
            "scope_provisions": json.dumps(y.get("scope_provisions", []), ensure_ascii=False),
            "summary_ro": _safe_summary(y.get("summary_ro", "")),
            "source_url": source_url, "last_checked": now_iso[:10],
            "aliases": y.get("aliases", []), "domains": y.get("domains", []),
        }
        version = {"source_url": source_url, "checksum": checksum,
                    "retrieved_at": now_iso, "parser_version": "parse_eu_html-1"}

        provisions: list[dict] = []
        if eu_parser_ok:
            try:
                from scripts.parse_eu import parse_eu_html
                raw_provs = parse_eu_html(html, act_type=act_type, number=number, year=year)
                # Deduplicate (the regex can match the same article multiple times).
                seen: set[str] = set()
                for p in raw_provs:
                    if p["id"] not in seen:
                        seen.add(p["id"])
                        provisions.append(p)
            except Exception as exc:
                stats["errors"].append(f"EU parse error {act_id}: {exc}")
                continue
        if not provisions:
            provisions = _parse_eu_fallback(html, act_type=act_type, number=number, year=year)

        result = engine.ingest_snapshot(act, version, provisions)
        if result["status"] != "NO_OP":
            stats["acts"] += 1
            stats["provisions"] += result.get("added", len(provisions))
            stats["text_bytes"] += sum(len(p.get("text", "")) for p in provisions)
            stats["eu"] += 1
        for alias in y.get("aliases", []):
            engine.conn.execute("INSERT OR IGNORE INTO aliases(alias,act_id,priority) VALUES(?,?,?)",
                               (fold(alias), act_id, 10))
        for domain in y.get("domains", []):
            engine._insert_domain(act_id, domain, is_act=True)
        engine.conn.commit()

    # ── EU <-> RO relations ──────────────────────────────────────────
    rel_inserted, rel_skipped = ingest_relations(engine)

    # ── Provision/act tags (human, sources/tags.tsv) ─────────────────
    tag_stats = engine.apply_tags()

    # ── Corpus status ────────────────────────────────────────────────────
    engine.conn.execute(
        "INSERT OR REPLACE INTO corpus_status(source,last_sync,status,documents,method) VALUES(?,?,?,?,?)",
        ("jurislatie_just_ro", now_iso, "ingested", stats["ro"], "parse_ro_html"))
    engine.conn.execute(
        "INSERT OR REPLACE INTO corpus_status(source,last_sync,status,documents,method) VALUES(?,?,?,?,?)",
        ("eurlex_cellar", now_iso, "ingested", stats["eu"], "parse_eu_text"))
    engine.conn.commit()
    engine.close()

    print(json.dumps({"status": "OK", "acts": stats["acts"], "provisions": stats["provisions"],
                       "text_bytes": stats["text_bytes"], "ro_acts": stats["ro"],
                       "eu_acts": stats["eu"], "relations": rel_inserted,
                       "relations_skipped": rel_skipped,
                       "tags": tag_stats,
                       "errors": stats["errors"]},
                      ensure_ascii=False, indent=2))
    return 0 if not stats["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
