#!/usr/bin/env python3
"""Corpus-driven fetcher for the jurist v1 corpus.

Downloads every act listed in sources/corpus.yaml from official sources into
exactly the locations scripts/ingest_corpus.py reads:

  RO -> raw/ro/<TIP>_<NUMAR>_<AN>.html
        Portal Legislativ SOAP (scripts/fetch_ro.py) for discovery/metadata,
        paginated Search + client-side TipAct selection, then the official
        consolidated HTML at LinkHtml. The SOAP `Text` (original published
        form) is NEVER stored as canonical text; the portal search UI is
        NEVER scraped.

  EU -> ingest/eu/<celex>.html + raw/eu/<celex>.html + ingest/eu/MANIFEST.json
        Publications Office Cellar only (EUR-Lex HTML is behind a WAF).
        Optional fetch.consolidated key in corpus.yaml pins a consolidated
        CELEX (e.g. 02011L0083-20250901); without it the base CELEX is
        downloaded. Every response must pass scripts/content_gate.py BEFORE
        saving; a gate failure never overwrites existing files.

Offline-testable helpers: tip_act_matches/pick_ro_result (TipAct matching),
ro_filename (filename mapping), select_celex (consolidated selection),
ro_stable_text (volatile portal-marker homogenization),
upsert_manifest (atomic manifest replace-in-place), parse_consolidations
(--list-consolidations parsing). Unit tests: tests/test_fetch_corpus.py.

Usage:
    python3 scripts/fetch_corpus.py [--only ID[,ID]] [--jurisdiction RO|EU]
                                    [--dry-run]
    python3 scripts/fetch_corpus.py --list-consolidations 32011L0083
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import yaml  # noqa: E402

import content_gate  # noqa: E402  (scripts/content_gate.py, imported not edited)
import fetch_ro  # noqa: E402  (scripts/fetch_ro.py, imported not edited)

CORPUS_PATH = ROOT / "sources" / "corpus.yaml"
EU_INGEST_DIR = ROOT / "ingest" / "eu"
MANIFEST_PATH = EU_INGEST_DIR / "MANIFEST.json"

CELLAR_CELEX_URL = "https://publications.europa.eu/resource/celex/{}"

USER_AGENT = fetch_ro.USER_AGENT  # browser UA: the portal WAF 403s urllib's default

ATTEMPTS = 3            # retries per request (spec: retries 3)
MAX_RO_PAGES = 10       # Search returns 10 results/page and cannot filter TipAct
RO_PAGE_SIZE = 10

# Manifest entry schema — keep identical to the entries already in
# ingest/eu/MANIFEST.json.
MANIFEST_KEYS = ("status", "celex_base", "celex_downloaded", "is_consolidated",
                 "url", "sha256", "bytes", "articole_gasite")

# Accepted TipAct spellings per corpus.yaml fetch.tip (keys folded lowercase),
# diacritic/cedilla insensitive (Portal Legislativ returns the full name, e.g.
# "ORDONANȚĂ DE URGENȚĂ", not "OUG").
TIP_ALIASES: dict[str, tuple[str, ...]] = {
    "lege": ("lege",),
    "oug": ("ordonanta de urgenta", "oug"),
    "og": ("ordonanta", "og"),
    "hg": ("hotarare", "hg"),
}

_FOLD = str.maketrans({"ș": "s", "ț": "t", "ă": "a", "â": "a", "î": "i",
                       "ş": "s", "ţ": "t",  # cedilla variants (Windows-1250 legacy)
                       "Ș": "s", "Ț": "t", "Ă": "a", "Â": "a", "Î": "i",
                       "Ş": "s", "Ţ": "t",
                       # Portal rows start with a UTF-8 BOM on some documents;
                       # the zero-width marker must not defeat prefix matching.
                       "\ufeff": "", "\xa0": " "})

# Portal Legislativ embeds a per-response nonce in the printable-form URL
# (href=/Public/FormaPrintabila/<token>) and serves CRLF or LF endings
# interchangeably; everything else is stable. Homogenizing both makes sha256
# change-detection reproducible across polls (§21) — verified live: two
# downloads of OUG 34/2014 differ ONLY in these two elements.
PRINT_TOKEN_RE = re.compile(r"/Public/FormaPrintabila/[0-9A-Za-z]+")


class FetchError(Exception):
    """Expected fetch failure (selection, gate, HTTP); reported, not fatal."""


def fold(value: str | None) -> str:
    """Lowercase + strip + fold Romanian diacritics (comma AND cedilla)."""
    return (value or "").translate(_FOLD).lower().strip()


def tip_act_matches(tipact: str | None, tip: str) -> bool:
    """True if a SOAP TipAct value matches the corpus.yaml fetch.tip token."""
    folded = fold(tipact)
    aliases = TIP_ALIASES.get(fold(tip))
    if aliases is None:  # unknown token: compare literally, folded
        return folded == fold(tip)
    return folded in aliases


def _ro_identity(title: str | None) -> str | None:
    """The 'nr. <number> din <day> <month> <year>' signature of a portal title."""
    m = re.search(r"nr\.?\s*\d+\s+din\s+\d{1,2}\s+[a-z]+\s+\d{4}", fold(title or ""))
    return m.group(0) if m else None


def _portal_doc_id(link: str | None) -> int:
    """Numeric DetaliiDocument id of a LinkHtml (-1 when absent)."""
    m = re.search(r"/DetaliiDocument/(\d+)", (link or "").strip())
    return int(m.group(1)) if m else -1


def pick_ro_result(results: list[dict[str, str]], tip: str, year: int,
                   numar: int | str | None = None) -> dict[str, str]:
    """Select the single SOAP result of the requested type.

    Search(SearchAn, SearchNumar) cannot filter TipAct server-side: for
    2004/506 it returns a HOTĂRÂRE (ballot papers), a DECRET and only then
    the LEGE. Deterministic narrowing chain before any pick — ambiguity after
    it is an error, never a silent first-result pick (same rule as
    fetch_ro.select_act):
      1. TipAct matches the requested type exactly (tip_act_matches);
      2. Titlu starts with the act type ("Legea nr. ...",
         "Ordonanța de urgență nr. ...") — an act that only MENTIONS the
         number in its title loses;
      3. Titlu carries the act's OWN identity — "nr. <numar> din <day> <month>
         <year>" — so a later act that merely CITES the number/year in its
         subject ("LEGE nr. 50 din 17 aprilie 2026 privind aprobarea
         Ordonanţei de urgenţă a Guvernului nr. 38/2024", "LEGE nr. 214 din
         10 decembrie 2025 pentru aprobarea OUG nr. 75/2024") loses, and an
         unrelated same-number act (OUG 34/2017) cannot win. Applied only when
         it leaves at least one candidate, so titles without a full date
         ("Legea nr. 506 din 2004") fall through to the generic steps below;
      4. Titlu mentions the year;
      5. Titlu mentions the number (when `numar` is given);
      6. candidates sharing one and the same 'nr. X din <date>' identity are
         manifestations of the SAME act (HG 947/2000 is returned both as
         DetaliiDocument/24730 and as its republished form 97219): the newest
         portal document id wins, deterministically.
    """
    cands = [r for r in results if tip_act_matches(r.get("TipAct"), tip)]
    if not cands:
        seen = sorted({(r.get("TipAct") or "?").strip() for r in results})
        raise FetchError(f"no TipAct {tip!r} among {len(results)} result(s); "
                         f"types returned: {seen}")
    folded_tip = fold(tip)
    aliases = TIP_ALIASES.get(folded_tip, (folded_tip,))
    starts = [r for r in cands if fold(r.get("Titlu")).startswith(aliases)]
    if starts:
        cands = starts
    if len(cands) > 1 and numar is not None:
        own_identity = (rf"nr\.?\s*{re.escape(str(numar))}"
                        rf"\s+din\s+\d{{1,2}}\s+[a-z]+\s+{year}\b")
        ident = [r for r in cands
                 if re.search(own_identity, fold(r.get("Titlu") or ""))]
        if ident:
            cands = ident
    if len(cands) > 1:
        year_hits = [r for r in cands
                     if re.search(rf"\b{year}\b", r.get("Titlu") or "")]
        if year_hits:
            cands = year_hits
    if numar is not None and len(cands) > 1:
        num = re.escape(str(numar))
        num_hits = [r for r in cands
                    if re.search(rf"\b{num}\b", r.get("Titlu") or "")]
        if num_hits:
            cands = num_hits
    if len(cands) > 1:
        sigs = {_ro_identity(r.get("Titlu")) for r in cands}
        if len(sigs) == 1 and None not in sigs:
            cands = [max(cands, key=lambda r: _portal_doc_id(r.get("LinkHtml")))]
    if len(cands) > 1:
        titles = [((r.get("Titlu") or "")[:80]) for r in cands]
        raise FetchError(f"ambiguous: {len(cands)} acts of type {tip!r} for {year}; {titles}")
    act = cands[0]
    if not (act.get("LinkHtml") or "").strip():
        raise FetchError(f"selected {tip} {year} carries no LinkHtml")
    return act


def ro_stable_text(text: str) -> str:
    """Portal HTML with per-response volatile elements homogenized (the
    FormaPrintabila nonce, CRLF line endings).

    Applied BEFORE hashing and storing RO snapshots so equal legal content
    yields equal bytes/checksums; a future new volatile marker only degrades
    to a safe refetch (status 'fetched'), never to a false 'unchanged'.
    """
    return PRINT_TOKEN_RE.sub("/Public/FormaPrintabila/STABLE",
                              text.replace("\r\n", "\n"))


def ro_filename(tip: str, numar, an) -> str:
    """raw/ro filename expected by ingest_corpus._ro_filename_to_meta."""
    return f"{str(tip).upper()}_{numar}_{an}.html"


def select_celex(fetch_spec: dict) -> tuple[str, bool]:
    """(celex_to_download, is_consolidated): fetch.consolidated pins a
    consolidated CELEX; otherwise the base CELEX is downloaded."""
    celex = str(fetch_spec["celex"])
    downloaded = str(fetch_spec.get("consolidated") or celex)
    return downloaded, downloaded != celex


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_corpus(path: Path = CORPUS_PATH) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    acts = data.get("acts") or []
    return [a for a in acts if isinstance(a, dict) and a.get("id")]


def read_manifest(path: Path = MANIFEST_PATH) -> list[dict]:
    if not path.exists():
        return []
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, list):
        raise FetchError(f"{path} is not a JSON list")
    return manifest


def upsert_manifest(entry: dict, path: Path = MANIFEST_PATH) -> list[dict]:
    """Replace the entry for the same celex_base in place (no duplicates).

    Writes atomically (tmp file + os.replace) so a crash mid-write can never
    leave a truncated MANIFEST.json behind.
    """
    manifest = read_manifest(path)
    for i, existing in enumerate(manifest):
        if existing.get("celex_base") == entry["celex_base"]:
            manifest[i] = entry
            break
    else:
        manifest.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    os.replace(tmp, path)
    return manifest


def manifest_entry_for(celex_base: str, path: Path = MANIFEST_PATH) -> dict | None:
    for entry in read_manifest(path):
        if entry.get("celex_base") == celex_base:
            return entry
    return None


# ── networking ──────────────────────────────────────────────────────────

def _nap() -> None:
    """Polite pause: 1-2 s between official requests."""
    time.sleep(random.uniform(1.0, 2.0))


def _retry(fn, *args, attempts: int = ATTEMPTS, **kwargs):
    """Retry a SOAP/metadata call up to 3 times."""
    for attempt in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception:
            if attempt >= attempts:
                raise
            _nap()


def _http_get(url: str, headers: dict[str, str], *,
              attempts: int = ATTEMPTS, timeout: int = 120) -> bytes:
    """GET with browser UA and retries on transient failures.

    Cellar answers 202 (document generation queued) with an empty body —
    treated as transient, like 404/408/429/5xx and network errors.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT, **headers})
            with urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                if resp.getcode() == 202:
                    raise HTTPError(url, 202, "document generation queued",
                                    resp.headers, None)
            return data
        except Exception as exc:  # noqa: BLE001 — classify then retry
            code = getattr(exc, "code", None)
            transient = (code in (202, 403, 404, 408, 429, 500, 502, 503, 504)
                         or isinstance(exc, (TimeoutError, OSError)))
            last = exc
            if transient and attempt < attempts:
                _nap()
                continue
            raise
    raise last if last else FetchError("unreachable")


def _search_all_pages(token: str, year: int, number: int) -> list[dict[str, str]]:
    """Paginate SOAP Search (10 results/page, TipAct not filterable server-side).

    Up to 10 pages; stops when a page is short or repeats rows already seen.
    """
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for page in range(1, MAX_RO_PAGES + 1):
        batch = _retry(fetch_ro.search, token, year, number,
                       page=page, page_size=RO_PAGE_SIZE)
        new = 0
        for row in batch:
            key = (row.get("TipAct", ""), row.get("Numar", ""),
                   row.get("LinkHtml", ""), row.get("Titlu", ""))
            if key not in seen:
                seen.add(key)
                rows.append(row)
                new += 1
        if len(batch) < RO_PAGE_SIZE or new == 0:
            break
        if page < MAX_RO_PAGES:
            _nap()
    return rows


# ── fetchers ────────────────────────────────────────────────────────────

def fetch_ro_act(act: dict, *, root: Path = ROOT) -> dict:
    """SOAP discovery (paginated, TipAct selected client-side) + LinkHtml HTML."""
    spec = act.get("fetch") or {}
    tip = str(spec.get("tip", "")).upper()
    numar = spec.get("numar")
    an = spec.get("an")
    rel_path = f"raw/ro/{ro_filename(tip, numar, an)}"
    out = {"id": act["id"], "jurisdiction": "RO", "status": "failed",
           "path": rel_path, "sha256": None, "source_url": None,
           "data_vigoare": None}
    try:
        if not (tip and numar and an):
            raise FetchError(f"incomplete SOAP fetch spec: {spec!r}")
        token = _retry(fetch_ro.get_token)
        rows = _search_all_pages(token, int(an), int(numar))
        selected = pick_ro_result(rows, tip, int(an), numar=int(numar))
        link = selected["LinkHtml"].strip()
        _nap()  # polite pause between the SOAP calls and the HTML request
        data = _http_get(link, {})
        # Decode-safe write: raw bytes must be valid UTF-8 for ingest_corpus.
        text = ro_stable_text(data.decode("utf-8", errors="replace"))
        ok, reason = content_gate.check(text, "ro")
        if not ok:
            raise FetchError(f"content gate: {reason}")
        data = text.encode("utf-8")
        sha = sha256_bytes(data)
        path = root / "raw" / "ro" / ro_filename(tip, numar, an)
        existing = path.read_text(encoding="utf-8") if path.exists() else None
        if existing is not None and sha256_bytes(
                ro_stable_text(existing).encode("utf-8")) == sha:
            status = "unchanged"          # same stable text → do not rewrite
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            status = "fetched"
        out.update(status=status, sha256=sha, source_url=link,
                   data_vigoare=(selected.get("DataVigoare") or "").strip() or None)
    except Exception as exc:  # noqa: BLE001 — reported per act, never fatal
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def fetch_eu_act(act: dict, *, root: Path = ROOT) -> dict:
    """Cellar XHTML download, content-gated before saving, manifest upsert."""
    spec = act.get("fetch") or {}
    celex_base = str(spec.get("celex") or "")
    rel_path = ""
    out = {"id": act["id"], "jurisdiction": "EU", "status": "failed",
           "path": None, "sha256": None, "source_url": None,
           "data_vigoare": None}
    try:
        if not celex_base:
            raise FetchError(f"incomplete cellar fetch spec: {spec!r}")
        downloaded, is_consolidated = select_celex(spec)
        url = CELLAR_CELEX_URL.format(downloaded)
        rel_path = f"ingest/eu/{downloaded}.html"
        out["path"] = rel_path
        data = _http_get(url, {"Accept": "application/xhtml+xml",
                               "Accept-Language": "ron"})
        text = data.decode("utf-8", errors="replace")
        ok, reason = content_gate.check(text, "eu")
        if not ok:
            # Gate failure → nothing written, existing files untouched.
            raise FetchError(f"content gate: {reason}")
        data = text.encode("utf-8")
        sha = sha256_bytes(data)
        ingest_file = root / "ingest" / "eu" / f"{downloaded}.html"
        raw_file = root / "raw" / "eu" / f"{downloaded}.html"
        manifest_path = root / "ingest" / "eu" / "MANIFEST.json"
        existing_sha = sha256_file(ingest_file) if ingest_file.exists() else None

        entry = {
            "status": "ok",
            "celex_base": celex_base,
            "celex_downloaded": downloaded,
            "is_consolidated": is_consolidated,
            "url": url,
            "sha256": sha,
            "bytes": len(data),
            "articole_gasite": len(content_gate.ARTICLE_RE.findall(text)),
        }
        manifest_entry = manifest_entry_for(celex_base, manifest_path)
        manifest_current = (manifest_entry is not None
                            and manifest_entry.get("celex_downloaded") == downloaded
                            and manifest_entry.get("sha256") == sha
                            and manifest_entry.get("status") == "ok")

        if existing_sha == sha:
            status = "unchanged"          # same sha256 → do not rewrite
            if not raw_file.exists():
                raw_file.parent.mkdir(parents=True, exist_ok=True)
                raw_file.write_bytes(data)  # audit copy was missing
            if not manifest_current:
                upsert_manifest(entry, manifest_path)
        else:
            ingest_file.parent.mkdir(parents=True, exist_ok=True)
            raw_file.parent.mkdir(parents=True, exist_ok=True)
            ingest_file.write_bytes(data)
            raw_file.write_bytes(data)
            upsert_manifest(entry, manifest_path)
            status = "fetched"
        out.update(status=status, sha256=sha, source_url=url)
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def fetch_act(act: dict, *, root: Path = ROOT) -> dict:
    if act["id"].startswith("RO:"):
        return fetch_ro_act(act, root=root)
    return fetch_eu_act(act, root=root)


# ── planning / dry run ──────────────────────────────────────────────────

def filter_acts(acts: list[dict], only: str | None = None,
                jurisdiction: str | None = None) -> tuple[list[dict], list[str]]:
    """Apply --only (comma-separated act ids) and --jurisdiction RO|EU."""
    unknown: list[str] = []
    selected = acts
    if only:
        wanted = [w.strip() for w in only.split(",") if w.strip()]
        ids = {a["id"] for a in acts}
        unknown = [w for w in wanted if w not in ids]
        wanted_set = set(wanted) - set(unknown)
        selected = [a for a in selected if a["id"] in wanted_set]
    if jurisdiction:
        selected = [a for a in selected
                    if a["id"].startswith(jurisdiction.upper() + ":")]
    return selected, unknown


def plan_act(act: dict) -> dict:
    """Dry-run entry: where this act would be fetched from and written to."""
    spec = act.get("fetch") or {}
    if act["id"].startswith("RO:"):
        entry = {"id": act["id"], "jurisdiction": "RO", "status": "planned",
                 "path": f"raw/ro/{ro_filename(spec.get('tip', ''), spec.get('numar'), spec.get('an'))}",
                 "sha256": None, "source_url": None, "data_vigoare": None,
                 "via": "Portal Legislativ SOAP discovery + LinkHtml HTML"}
    else:
        downloaded, _ = select_celex(spec)
        entry = {"id": act["id"], "jurisdiction": "EU", "status": "planned",
                 "path": f"ingest/eu/{downloaded}.html",
                 "sha256": None,
                 "source_url": CELLAR_CELEX_URL.format(downloaded),
                 "data_vigoare": None,
                 "celex": spec.get("celex"), "celex_downloaded": downloaded,
                 "via": "Publications Office Cellar (xhtml, content-gated)"}
    return entry


def build_plan(acts: list[dict]) -> tuple[list[dict], list[str]]:
    """Dry-run plan + warnings (e.g. manifest pins a consolidated CELEX that
    corpus.yaml does not pin via fetch.consolidated)."""
    warnings: list[str] = []
    plan = []
    for act in acts:
        entry = plan_act(act)
        if entry["jurisdiction"] == "EU":
            spec = act.get("fetch") or {}
            try:
                pinned = manifest_entry_for(spec.get("celex", ""))
            except Exception:  # noqa: BLE001 — a broken manifest must not break --dry-run
                pinned = None
            if (pinned and pinned.get("is_consolidated")
                    and pinned.get("celex_downloaded") != entry["celex_downloaded"]):
                warnings.append(
                    f"{act['id']}: MANIFEST.json pins consolidated "
                    f"{pinned['celex_downloaded']} but corpus.yaml has no "
                    f"fetch.consolidated — a real fetch would switch to "
                    f"{entry['celex_downloaded']} (add fetch.consolidated to keep it)")
        plan.append(entry)
    return plan, warnings


# ── --list-consolidations ───────────────────────────────────────────────

def parse_consolidations(xml_text: str, celex: str,
                         today: str | None = None) -> list[dict]:
    """Extract 0YYYYTNNNN-YYYYMMDD consolidated versions of `celex` from a
    Cellar notice (branch). The notice also mentions consolidated versions of
    amending acts — those are filtered out by the CELEX prefix."""
    celex = celex.strip().upper()
    prefix = "0" + celex[1:]          # 32011L0083 -> 02011L0083
    pattern = re.compile(re.escape(prefix) + r"-(\d{4})(\d{2})(\d{2})")
    today = today or date.today().isoformat()
    found: dict[str, str] = {}
    for m in pattern.finditer(xml_text):
        stamp = m.group(1) + m.group(2) + m.group(3)
        found[f"{prefix}-{stamp}"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return [{"celex_downloaded": c, "date": found[c],
             "in_force_by_today": found[c] <= today}
            for c in sorted(found)]


def list_consolidations(celex: str) -> int:
    celex = celex.strip().upper()
    if not re.fullmatch(r"3\d{4}[A-Z]\d{4}", celex):
        print(json.dumps({"ok": False, "error": f"bad CELEX: {celex!r} "
                           "(expected e.g. 32011L0083)"}))
        return 2
    data = _http_get(CELLAR_CELEX_URL.format(celex),
                     {"Accept": "application/xml;notice=branch",
                      "Accept-Language": "ron"})
    versions = parse_consolidations(data.decode("utf-8", errors="replace"), celex)
    print(json.dumps({
        "ok": True, "celex": celex, "count": len(versions),
        "consolidations": versions,
        "hint": "pin the latest in-force version via fetch.consolidated "
                "in sources/corpus.yaml",
    }, ensure_ascii=False, indent=2))
    return 0


# ── CLI ─────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch every corpus.yaml act from official sources "
                    "(Portal Legislativ SOAP + Cellar).")
    parser.add_argument("--only", metavar="ID[,ID]",
                        help="fetch only these corpus act ids")
    parser.add_argument("--jurisdiction", choices=("RO", "EU"),
                        help="restrict to one jurisdiction")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be fetched; no network")
    parser.add_argument("--list-consolidations", metavar="CELEX",
                        help="list available consolidated versions of a CELEX "
                             "via the Cellar notice (network)")
    args = parser.parse_args(argv)

    if args.list_consolidations:
        return list_consolidations(args.list_consolidations)

    acts, unknown = filter_acts(load_corpus(), args.only, args.jurisdiction)
    if unknown:
        print(json.dumps({"ok": False, "error": "unknown act id(s) in --only",
                          "unknown": unknown}, ensure_ascii=False, indent=2))
        return 2
    if not acts:
        print(json.dumps({"ok": False, "error": "no acts selected",
                          "dry_run": args.dry_run}, ensure_ascii=False, indent=2))
        return 2

    if args.dry_run:
        plan, warnings = build_plan(acts)
        print(json.dumps({"dry_run": True, "count": len(plan),
                          "warnings": warnings, "acts": plan},
                         ensure_ascii=False, indent=2))
        return 0

    results: list[dict] = []
    for i, act in enumerate(acts):
        print(f"[{act['id']}] fetching...", file=sys.stderr)
        result = fetch_act(act)
        results.append(result)
        if i < len(acts) - 1:
            _nap()  # polite pause between acts

    _, warnings = build_plan(acts)
    counts = {s: sum(1 for r in results if r["status"] == s)
              for s in ("fetched", "unchanged", "failed")}
    print(json.dumps({"dry_run": False, "count": len(results),
                      "fetched": counts["fetched"],
                      "unchanged": counts["unchanged"],
                      "failed": counts["failed"],
                      "warnings": warnings, "acts": results},
                     ensure_ascii=False, indent=2))
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
