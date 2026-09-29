"""Deterministic local legal retrieval engine for the jurist skill.

The engine intentionally uses only the Python standard library and SQLite/FTS5.
It is safe to run without downloaded legislation: the bundled fixture is explicitly
marked as demonstrative and every response exposes that limitation.

Session scoping: every read is logged into ``retrieval_log`` under a session id.
The session id is the ``JURIST_SESSION`` environment variable when set, else
``current`` (backward compatible). Citation validation only considers rows of
that session, so drafts are judged against what the same session retrieved.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "legal.db"
SEED = ROOT / "tests" / "fixtures" / "seed.json"
STALE_DAYS = 30

# Romanian legacy cedilla characters are common in Portal Legislativ material.
_CEDILLA_MAP = str.maketrans({"Ş": "Ș", "ş": "ș", "Ţ": "Ț", "ţ": "ț"})


def normalize(value: str | None) -> str:
    """Normalize legal text and queries without destroying Romanian diacritics."""
    value = unicodedata.normalize("NFC", value or "").translate(_CEDILLA_MAP)
    value = value.replace("\ufeff", "")
    return re.sub(r"\s+", " ", value).strip()


def fold(value: str | None) -> str:
    """Case/diacritic-fold a value for aliases and deterministic routing."""
    text = normalize(value).lower()
    return "".join(
        char for char in unicodedata.normalize("NFD", text)
        if unicodedata.category(char) != "Mn"
    )


def _today() -> str:
    return date.today().isoformat()


def _valid_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def _age_days(value: str | None) -> int | None:
    if not _valid_date(value):
        return None
    return max(0, (date.today() - date.fromisoformat(value[:10])).days)


def canonical_citation(
    jurisdiction: str,
    act_type: str,
    number: str,
    year: str | int,
    provision_type: str = "article",
    article: str | None = None,
    paragraph: str | None = None,
    point: str | None = None,
    letter: str | None = None,
) -> str:
    """Format the one canonical citation grammar used by the runtime."""
    # Preserve the official identifier convention used in the corpus: EU
    # CELEX-style IDs are TYPE:YEAR:NUMBER, while Romanian IDs are TYPE:NUMBER:YEAR.
    if jurisdiction.upper() == "EU":
        prefix = f"{jurisdiction.upper()}:{act_type.upper()}:{year}:{number}"
    else:
        prefix = f"{jurisdiction.upper()}:{act_type.upper()}:{number}:{year}"
    kind = provision_type.lower()
    if kind == "article":
        if not article:
            raise ValueError("article is required for an article citation")
        path = ["ART", str(article)]
        if paragraph is not None:
            path += ["P", str(paragraph)]
        if point is not None:
            path += ["POINT", str(point)]
        if letter is not None:
            path += ["L", str(letter)]
    elif kind == "recital":
        path = ["REC", str(article or paragraph or "")]
    elif kind == "annex":
        path = ["ANN", str(article or paragraph or "")]
    elif kind == "preamble":
        path = ["PRE"]
    else:
        raise ValueError(f"unsupported provision_type: {provision_type}")
    return ":".join(prefix.split(":") + path)


def normalize_citation(value: str) -> str:
    """Accept canonical IDs and the legacy compact form, returning canonical form.

    Accepted examples:
      EU:REG:2016:679:ART:6:P:1:L:f
      EU:REG:2016:679:art:6
      RO:LEGE:506:2004:art:4:5  (legacy paragraph shorthand)
    """
    raw = normalize(value).strip().strip("[]()")
    if not raw:
        return raw
    parts = raw.split(":")
    if len(parts) < 5:
        return raw.upper()
    parts[:4] = [parts[0].upper(), parts[1].upper(), parts[2], parts[3]]
    marker = parts[4].upper()
    if marker in {"PRE", "PREAMBLE"}:
        return ":".join(parts[:4] + ["PRE"])
    if marker in {"REC", "RECITAL"}:
        return ":".join(parts[:4] + ["REC"] + parts[5:])
    if marker in {"ANN", "ANNEX"}:
        return ":".join(parts[:4] + ["ANN"] + parts[5:])
    if marker not in {"ART", "ARTICLE"}:
        return ":".join(parts[:4] + [marker] + parts[5:])

    # Old IDs used art:<article>:<paragraph>, while the canonical grammar uses
    # explicit P/L/POINT markers.  Convert both forms deterministically.
    path = ["ART"]
    if len(parts) < 6:
        return ":".join(parts[:4] + path)
    path.append(parts[5])
    rest = parts[6:]
    if rest:
        if rest[0].upper() in {"P", "PARA", "PARAGRAPH"}:
            path += ["P", rest[1]]
            rest = rest[2:]
        elif rest[0].upper() in {"L", "LETTER"}:
            path += ["L", rest[1]]
            rest = rest[2:]
        elif rest[0].upper() in {"POINT", "PT"}:
            path += ["POINT", rest[1]]
            rest = rest[2:]
        else:
            path += ["P", rest[0]]
            rest = rest[1:]
        while rest:
            marker = rest.pop(0).upper()
            if marker in {"L", "LETTER"} and rest:
                path += ["L", rest.pop(0)]
            elif marker in {"POINT", "PT"} and rest:
                path += ["POINT", rest.pop(0)]
            elif marker not in {"P", "PARA", "PARAGRAPH"}:
                path.append(marker)
    return ":".join(parts[:4] + path)


_STOPWORDS = {
    "a", "al", "am", "are", "ca", "ce", "cu", "de", "din", "e", "este", "in", "la",
    "mai", "nu", "o", "or", "pe", "pentru", "sa", "sau", "se", "si", "sunt",
    "un", "and", "of", "the", "to", "for", "on", "at",
}


def _citation_tokens(value: str) -> list[str]:
    return re.findall(r"[\wĂÂÎȘȚăâîșț-]+", fold(value))


class JuristEngine:
    """SQLite-backed retrieval API. One instance owns one session retrieval log."""

    def __init__(self, db_path: str | Path | None = None, seed: bool = False,
                 session: str | None = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.retrieval_log: list[dict[str, Any]] = []
        self.session_id = session or os.environ.get("JURIST_SESSION") or "current"
        self._lemmas = self._load_tsv("lemmas_ro.tsv", self._default_lemmas())
        self._routing = self._load_routing()
        self.create_schema()
        if seed and self.conn.execute("SELECT COUNT(*) FROM acts").fetchone()[0] == 0:
            self.ingest_seed()

    @staticmethod
    def _default_lemmas() -> dict[str, list[str]]:
        return {
            "consimtamant": ["consimtamant", "consimtamantul", "consimtamantului", "acord", "opt-in"],
            "prelucrare": ["prelucrare", "prelucrarii", "prelucreaza", "procesare"],
            "operator": ["operator", "operatorului", "operatori"],
            "imputernicit": ["imputernicit", "imputernicitului", "procesator"],
            "retragere": ["retragere", "retrage", "retragerea", "14 zile"],
            "cookie": ["cookie", "cookies", "echipament terminal", "stocare", "acces"],
            "clauza": ["clauza", "clauze", "clauzelor", "abuziv", "abuzive"],
            "pret": ["pret", "pretul", "preturi", "preturilor"],
            "garantie": ["garantie", "garantii", "conformitate", "remediu"],
            "abonament": ["abonament", "abonamente", "subscription", "reinoire"],
        }

    @staticmethod
    def _default_routing() -> dict[str, set[str]]:
        # Fallback only when routing_keywords.tsv is missing. Targets must be
        # the English v1 tags used on acts in corpus.yaml, not the draft RO list.
        return {
            "cookie": {"cookies"}, "cookies": {"cookies"}, "banner": {"cookies"},
            "echipament terminal": {"cookies"},
            "consimtamant": {"personal_data", "privacy"}, "consent": {"personal_data", "privacy"},
            "retragere": {"withdrawal", "distance_contracts"}, "retur": {"withdrawal", "distance_contracts"},
            "clauze abuzive": {"terms_and_conditions", "contracts"},
            "garantie": {"sales", "conformity"},
            "abonament": {"contracts", "distance_contracts"},
            "pret": {"pricing"}, "consumator": {"consumer"},
        }

    def _load_tsv(self, filename: str, fallback: dict[str, list[str]]) -> dict[str, list[str]]:
        path = ROOT / "sources" / filename
        result = {k: list(v) for k, v in fallback.items()}
        if not path.exists():
            return result
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) >= 2:
                key = fold(fields[0])
                values = [normalize(x) for x in fields[1].split("|") if normalize(x)]
                result[key] = values or [key]
        return result

    def _load_routing(self) -> dict[str, set[str]]:
        path = ROOT / "sources" / "routing_keywords.tsv"
        if not path.exists():
            return self._default_routing()
        result: dict[str, set[str]] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) >= 2:
                result[fold(fields[0])] = {fold(x) for x in fields[1].split(",") if fold(x)}
        return result or self._default_routing()

    def create_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS acts (
                id TEXT PRIMARY KEY,
                jurisdiction TEXT NOT NULL,
                source_system TEXT NOT NULL DEFAULT 'fixture',
                celex TEXT,
                eli TEXT,
                act_type TEXT NOT NULL,
                number TEXT,
                year INTEGER,
                title TEXT NOT NULL,
                short_title TEXT,
                issuer TEXT,
                publication_date TEXT,
                effective_from TEXT,
                status TEXT NOT NULL DEFAULT 'in_force',
                authority_class TEXT NOT NULL DEFAULT 'binding_legislation',
                document_status TEXT,
                version_coverage TEXT NOT NULL DEFAULT 'current_only',
                language TEXT NOT NULL DEFAULT 'ro',
                scope_provisions TEXT NOT NULL DEFAULT '[]',
                summary_ro TEXT,
                provenance TEXT NOT NULL DEFAULT 'official',
                source_url TEXT,
                last_checked TEXT,
                CHECK (version_coverage IN ('point_in_time', 'current_only'))
            );
            CREATE TABLE IF NOT EXISTS act_versions (
                id TEXT PRIMARY KEY,
                act_id TEXT NOT NULL REFERENCES acts(id),
                valid_from TEXT,
                valid_to TEXT,
                version_date TEXT,
                consolidation_date TEXT,
                detected_at TEXT,
                data_vigoare_reported TEXT,
                source_url TEXT NOT NULL,
                checksum TEXT NOT NULL,
                retrieved_at TEXT NOT NULL,
                parser_version TEXT NOT NULL DEFAULT 'seed-1',
                language TEXT NOT NULL DEFAULT 'ro',
                is_consolidated INTEGER NOT NULL DEFAULT 0,
                legally_authentic INTEGER,
                UNIQUE(act_id, checksum)
            );
            CREATE TABLE IF NOT EXISTS provisions (
                id TEXT NOT NULL,
                act_id TEXT NOT NULL REFERENCES acts(id),
                act_version_id TEXT NOT NULL REFERENCES act_versions(id),
                provision_type TEXT NOT NULL DEFAULT 'article',
                citable_as_binding_basis INTEGER NOT NULL DEFAULT 1,
                part TEXT, title_no TEXT, chapter TEXT, section TEXT,
                article TEXT, paragraph TEXT, point TEXT, letter TEXT,
                heading TEXT, text TEXT NOT NULL,
                valid_from TEXT, valid_to TEXT,
                sequence INTEGER NOT NULL DEFAULT 0,
                canonical_citation TEXT NOT NULL,
                UNIQUE(act_version_id, canonical_citation),
                CHECK (provision_type IN ('article', 'recital', 'annex', 'preamble'))
            );
            CREATE TABLE IF NOT EXISTS aliases (
                alias TEXT PRIMARY KEY,
                act_id TEXT NOT NULL REFERENCES acts(id),
                priority INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS act_relations (
                source_act_id TEXT NOT NULL REFERENCES acts(id),
                relation_type TEXT NOT NULL,
                target_act_id TEXT NOT NULL REFERENCES acts(id),
                source_reference TEXT,
                PRIMARY KEY(source_act_id, relation_type, target_act_id)
            );
            CREATE TABLE IF NOT EXISTS domains (tag TEXT PRIMARY KEY, grp TEXT NOT NULL DEFAULT 'general');
            CREATE TABLE IF NOT EXISTS act_domains (act_id TEXT NOT NULL REFERENCES acts(id), tag TEXT NOT NULL REFERENCES domains(tag), PRIMARY KEY(act_id, tag));
            CREATE TABLE IF NOT EXISTS provision_domains (provision_id TEXT NOT NULL, tag TEXT NOT NULL REFERENCES domains(tag), PRIMARY KEY(provision_id, tag));
            CREATE TABLE IF NOT EXISTS authority_ranks (authority_class TEXT PRIMARY KEY, rank INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS corpus_status (source TEXT PRIMARY KEY, last_sync TEXT, status TEXT NOT NULL, documents INTEGER NOT NULL DEFAULT 0, method TEXT);
            CREATE TABLE IF NOT EXISTS retrieval_log (session_id TEXT NOT NULL, provision_id TEXT NOT NULL, act_id TEXT NOT NULL, as_of TEXT, retrieved_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_provisions_actpath ON provisions(act_id, article, paragraph);
            -- FTS hits join provisions by id; without this each search scans the whole table per hit.
            CREATE INDEX IF NOT EXISTS idx_provisions_id ON provisions(id);
            CREATE INDEX IF NOT EXISTS idx_act_versions_act ON act_versions(act_id, valid_from);
            CREATE INDEX IF NOT EXISTS idx_aliases_alias ON aliases(alias);
            CREATE INDEX IF NOT EXISTS idx_acts_status ON acts(status);
            CREATE INDEX IF NOT EXISTS idx_act_domains_tag ON act_domains(tag);
            CREATE INDEX IF NOT EXISTS idx_provision_domains_tag ON provision_domains(tag);
            CREATE INDEX IF NOT EXISTS idx_provision_domains_pid ON provision_domains(provision_id);
            CREATE VIRTUAL TABLE IF NOT EXISTS legislation_fts USING fts5(provision_id UNINDEXED, text, tokenize='unicode61 remove_diacritics 2');
            CREATE VIRTUAL TABLE IF NOT EXISTS case_law_fts USING fts5(provision_id UNINDEXED, text, tokenize='unicode61 remove_diacritics 2');
            CREATE VIRTUAL TABLE IF NOT EXISTS guidance_fts USING fts5(provision_id UNINDEXED, text, tokenize='unicode61 remove_diacritics 2');
            """
        )
        ranks = {
            "binding_legislation": 85, "eu_regulation": 90, "eu_directive": 88,
            "ro_law": 85, "ro_government_ordinance": 80, "case_law": 70,
            "official_guidance": 50, "authority_decision": 45, "informational": 20,
        }
        self.conn.executemany("INSERT OR IGNORE INTO authority_ranks VALUES (?, ?)", ranks.items())
        self.conn.commit()

    def ingest_seed(self) -> None:
        seed = json.loads(SEED.read_text(encoding="utf-8"))
        now = "2025-01-01"
        for act in seed["acts"]:
            aid = act["id"]
            source_url = act.get("source_url", "seed://fixture")
            summary = act.get("summary_ro", act.get("summary", ""))
            scope = json.dumps(act.get("scope_provisions", []), ensure_ascii=False)
            self.conn.execute(
                """INSERT OR IGNORE INTO acts
                (id,jurisdiction,source_system,celex,eli,act_type,number,year,title,short_title,
                 issuer,status,authority_class,version_coverage,language,scope_provisions,summary_ro,
                 provenance,source_url,last_checked) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid, act["jurisdiction"], act.get("source_system", "fixture"), act.get("celex"), act.get("eli"),
                 act["act_type"], act["number"], act["year"], act["title"], act.get("short_title"), act.get("issuer"),
                 act.get("status", "in_force"), act.get("authority_class", "binding_legislation"),
                 act.get("version_coverage", "current_only"), act.get("language", "ro"), scope, summary,
                 'fixture', source_url, act.get("last_checked", now)),
            )
            version_id = f"{aid}:VERSION:{act.get('last_checked', now)}"
            checksum = hashlib.sha256((aid + summary).encode("utf-8")).hexdigest()
            self.conn.execute(
                """INSERT OR IGNORE INTO act_versions
                (id,act_id,valid_from,version_date,source_url,checksum,retrieved_at,parser_version,language,is_consolidated,legally_authentic)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (version_id, aid, act.get("valid_from"), act.get("last_checked", now), source_url, checksum,
                 act.get("last_checked", now), "seed-1", act.get("language", "ro"),
                 1 if act.get("jurisdiction") == "EU" else 0, 0 if act.get("jurisdiction") == "EU" else 1),
            )
            for alias in act.get("aliases", []):
                self.conn.execute("INSERT OR IGNORE INTO aliases(alias,act_id,priority) VALUES(?,?,?)", (fold(alias), aid, 10))
            for domain in act.get("domains", []):
                self._insert_domain(aid, domain, is_act=True)

        for seq, provision in enumerate(seed["provisions"], start=1):
            aid = provision["act_id"]
            act = self.conn.execute("SELECT * FROM acts WHERE id=?", (aid,)).fetchone()
            if not act:
                continue
            version = self.conn.execute("SELECT id FROM act_versions WHERE act_id=? ORDER BY rowid LIMIT 1", (aid,)).fetchone()
            cid = normalize_citation(provision.get("id") or self._provision_citation(act, provision))
            ptype = provision.get("provision_type", "article")
            text = normalize(provision["text"])
            self.conn.execute(
                """INSERT OR IGNORE INTO provisions
                (id,act_id,act_version_id,provision_type,citable_as_binding_basis,article,paragraph,point,letter,
                 heading,text,valid_from,valid_to,sequence,canonical_citation)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, aid, version[0], ptype, int(provision.get("citable", 0 if ptype in {"recital", "preamble"} else 1)),
                 provision.get("article"), provision.get("paragraph"), provision.get("point"), provision.get("letter"),
                 provision.get("heading"), text, provision.get("valid_from", act["effective_from"]), provision.get("valid_to"),
                 provision.get("sequence", seq), cid),
            )
            aliases = [r[0] for r in self.conn.execute("SELECT alias FROM aliases WHERE act_id=?", (aid,))]
            fts_text = " ".join([act["title"], act["short_title"] or "", *aliases, text, *provision.get("domains", [])])
            self.conn.execute("INSERT OR IGNORE INTO legislation_fts(provision_id,text) VALUES(?,?)", (cid, normalize(fts_text)))
            for domain in provision.get("domains", []):
                self._insert_domain(cid, domain, is_act=False)

        for relation in seed.get("relations", []):
            self.conn.execute(
                "INSERT OR IGNORE INTO act_relations(source_act_id,relation_type,target_act_id,source_reference) VALUES(?,?,?,?)",
                (relation["from_id"], relation["relation_type"], relation["to_id"], relation.get("source_reference")),
            )
        self.conn.executemany(
            "INSERT OR IGNORE INTO corpus_status(source,last_sync,status,documents,method) VALUES(?,?,?,?,?)",
            [("legislatie_just_ro", None, "not_downloaded", 0, "SOAP"),
             ("eurlex_cellar", None, "not_downloaded", 0, "CELLAR"),
             ("edpb", None, "excluded_v1", 0, "post-v1"),
             ("anspdcp", None, "excluded_v1", 0, "post-v1")],
        )
        self.conn.commit()

    @staticmethod
    def _provision_citation(act: sqlite3.Row, provision: dict[str, Any]) -> str:
        return canonical_citation(act["jurisdiction"], act["act_type"], act["number"], act["year"],
                                  provision.get("provision_type", "article"), provision.get("article"),
                                  provision.get("paragraph"), provision.get("point"), provision.get("letter"))

    def _insert_domain(self, entity_id: str, domain: str, is_act: bool) -> None:
        domain = fold(domain)
        group = "privacy" if domain in {"cookies", "consimtamant", "temeiuri_legale", "marketing_direct", "drepturi_persoane", "personal_data"} else "ecommerce"
        self.conn.execute("INSERT OR IGNORE INTO domains(tag,grp) VALUES(?,?)", (domain, group))
        table = "act_domains" if is_act else "provision_domains"
        self.conn.execute(f"INSERT OR IGNORE INTO {table}({'act_id' if is_act else 'provision_id'},tag) VALUES(?,?)", (entity_id, domain))

    def _source_for_act(self, act_id: str) -> str | None:
        row = self.conn.execute("SELECT source_url FROM act_versions WHERE act_id=? ORDER BY rowid DESC LIMIT 1", (act_id,)).fetchone()
        return row[0] if row else None

    def _domains_for_act(self, act_id: str) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT tag FROM act_domains WHERE act_id=? ORDER BY tag", (act_id,))]

    def _meta(self, act: sqlite3.Row, as_of: str | None = None, requested: bool = False) -> dict[str, Any]:
        latest = act["last_checked"]
        applicability = "VERIFIED_AS_OF"
        warnings: list[str] = []
        if requested and as_of and act["version_coverage"] == "current_only":
            # A current-only source cannot prove a historical form. The current
            # snapshot is returned, but is explicitly not verified for that date.
            latest_date = latest[:10] if latest else None
            if not latest_date or as_of != latest_date:
                applicability = "NOT_VERIFIED_FOR_DATE"
                warnings.append("NOT_VERIFIED_FOR_DATE")
        if act["provenance"] == "fixture":
            warnings.append("FIXTURE_NOT_OFFICIAL_TEXT")
        if act["status"] != "in_force":
            warnings.append("ACT_NOT_IN_FORCE")
        if act["act_type"] in {"DIR", "DIRECTIVE"} or "directive" in (act["authority_class"] or "").lower():
            warnings.append("DIRECTIVE_NOT_DIRECTLY_APPLICABLE")
        age = _age_days(latest)
        if age is not None and age > STALE_DAYS:
            warnings.append(f"STALE_CORPUS: last checked {latest}")
        earliest_row = self.conn.execute("SELECT MIN(valid_from) FROM act_versions WHERE act_id=? AND valid_from IS NOT NULL", (act["id"],)).fetchone()
        earliest = (earliest_row[0] if earliest_row and earliest_row[0] else None) or act["effective_from"] or latest
        if requested and as_of and act["version_coverage"] == "point_in_time" and earliest and as_of < earliest:
            applicability = "NOT_VERIFIED_FOR_DATE"
            warnings.append("NOT_VERIFIED_FOR_DATE")
        return {
            "status": act["status"],
            "in_force_on_as_of": act["status"] == "in_force" and applicability == "VERIFIED_AS_OF",
            "amended_since": bool(self.conn.execute("SELECT COUNT(*) FROM act_versions WHERE act_id=?", (act["id"],)).fetchone()[0] > 1),
            "version_coverage": act["version_coverage"],
            "applicability": applicability,
            "earliest_version_date": earliest,
            "last_checked": latest,
            "corpus_age_days": age,
            "source_url": act["source_url"] or self._source_for_act(act["id"]),
            "warnings": warnings,
        }

    @staticmethod
    def _envelope(tool: str, as_of: str | None, warnings: Iterable[str] = (), next_action: Any = None, **payload: Any) -> dict[str, Any]:
        warning_list = list(dict.fromkeys(str(w) for w in warnings if w))
        return {"tool": tool, "ok": True, "as_of": as_of or _today(), "warnings": warning_list,
                "next_action": next_action, **payload}

    def _record(self, rows: Iterable[sqlite3.Row], as_of: str | None,
                extra_ids: Iterable[tuple[str, str]] = ()) -> None:
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        recorded: set[tuple[str, str]] = set()
        for row in rows:
            item = {"provision_id": row["id"], "act_id": row["act_id"], "as_of": as_of or _today()}
            if item not in self.retrieval_log:
                self.retrieval_log.append(item)
            self.conn.execute("INSERT INTO retrieval_log VALUES(?,?,?,?,?)",
                              (self.session_id, row["id"], row["act_id"], as_of or _today(), now))
            recorded.add((row["id"], row["act_id"]))
        for provision_id, act_id in extra_ids:
            if (provision_id, act_id) in recorded:
                continue
            item = {"provision_id": provision_id, "act_id": act_id, "as_of": as_of or _today()}
            if item not in self.retrieval_log:
                self.retrieval_log.append(item)
            self.conn.execute("INSERT INTO retrieval_log VALUES(?,?,?,?,?)",
                              (self.session_id, provision_id, act_id, as_of or _today(), now))
        self.conn.commit()

    def _act_match(self, reference: str, jurisdiction: str | None = None) -> list[sqlite3.Row]:
        q = fold(reference)
        args: list[Any] = [q, q, f"%{q}%"]
        sql = """SELECT DISTINCT a.* FROM acts a LEFT JOIN aliases al ON al.act_id=a.id
                 WHERE (al.alias=? OR lower(a.id)=? OR lower(a.title) LIKE ?)"""
        if jurisdiction:
            sql += " AND a.jurisdiction=?"
            args.append(jurisdiction.upper())
        return self.conn.execute(sql, args).fetchall()

    def resolve_act(self, reference: str, jurisdiction: str | None = None, as_of: str | None = None) -> dict[str, Any]:
        matches = []
        warnings: list[str] = []
        for act in self._act_match(reference, jurisdiction):
            meta = self._meta(act, as_of, as_of is not None)
            item = {
                "id": act["id"], "act_id": act["id"], "official_title": act["title"], "short_title": act["short_title"],
                "act_type": act["act_type"], "number": act["number"], "year": act["year"],
                "jurisdiction": act["jurisdiction"], "authority_class": act["authority_class"],
                "authority_rank": self._rank(act["authority_class"]), "domains": self._domains_for_act(act["id"]),
                "scope_provisions": json.loads(act["scope_provisions"] or "[]"),
                "aliases": [r[0] for r in self.conn.execute("SELECT alias FROM aliases WHERE act_id=?", (act["id"],))],
                "summary_ro": act["summary_ro"], "source_url": meta["source_url"],
                **{k: v for k, v in meta.items() if k != "warnings"},
                "transposed_by": self._related_targets(act["id"], "transposed_by"),
                "warnings": meta["warnings"],
            }
            matches.append(item)
            warnings.extend(meta["warnings"])
        status = "OK" if matches else "NO_MATCH_ABOVE_THRESHOLD"
        # resolve never knows the article. A next_action without one sends weak
        # models to `provision --act GDPR` which then fails. Leave it null.
        return self._envelope("jurist resolve", as_of, warnings, None, status=status, matches=matches)

    def _rank(self, authority_class: str) -> int:
        row = self.conn.execute("SELECT rank FROM authority_ranks WHERE authority_class=?", (authority_class,)).fetchone()
        return int(row[0]) if row else 0

    def _route_domains(self, query: str) -> list[str]:
        q = fold(query)
        matched = [(kw, domains) for kw, domains in self._routing.items() if kw and kw in q]
        if not matched:
            return []
        max_words = max(len(kw.split()) for kw, _ in matched)
        found: set[str] = set()
        for kw, domains in matched:
            if len(kw.split()) == max_words:
                found.update(domains)
        return sorted(found)

    def _expanded_match(self, query: str) -> str:
        tokens = _citation_tokens(query)
        terms: list[str] = []
        folded_query = fold(query)
        for token in tokens:
            if len(token) <= 2 or token in _STOPWORDS:
                continue
            values = self._lemmas.get(token, [token])
            terms.extend(fold(value) for value in values)
        for phrase, values in self._lemmas.items():
            if " " in phrase and phrase in folded_query:
                terms.extend(fold(value) for value in values)
        terms = list(dict.fromkeys(t for t in terms if t and len(t) > 2 and t not in _STOPWORDS))
        if not terms:
            return '"__no_match__"'
        # Prefix matching helps inflected Romanian terms while remaining lexical.
        safe = []
        for term in terms:
            if " " in term:
                safe.append('"' + term.replace('"', "") + '"')
            else:
                safe.append('"' + term.replace('"', "") + '"*')
        return " OR ".join(safe)

    def _jurisdiction_filter(self, rows: list[sqlite3.Row], jurisdictions: list[str] | None) -> list[sqlite3.Row]:
        if not jurisdictions:
            return rows
        allowed = {j.upper() for j in jurisdictions}
        return [r for r in rows if r["jurisdiction"].upper() in allowed]

    def _provision_domains(self, provision_id: str) -> set[str]:
        return {r[0] for r in self.conn.execute("SELECT tag FROM provision_domains WHERE provision_id=?", (provision_id,))}

    def _ids_for_domains(self, domains: Iterable[str], *, provisions: bool) -> list[str]:
        found: set[str] = set()
        sql = "SELECT provision_id FROM provision_domains WHERE tag=?" if provisions else "SELECT act_id FROM act_domains WHERE tag=?"
        for domain in domains:
            found.update(r[0] for r in self.conn.execute(sql, (domain,)))
        return sorted(found)

    def _fts_rows(self, table: str, match: str, routed: list[str]) -> list[sqlite3.Row]:
        """Lexical search, scoped to tagged provisions then acts, then unscoped."""

        def run(extra_sql: str = "", extra_args: list[Any] | None = None) -> list[sqlite3.Row]:
            sql = f"""SELECT p.*, a.id AS act_id, a.title AS act_title, a.jurisdiction, a.status,
                      a.authority_class, a.version_coverage, a.last_checked, a.source_url, a.act_type,
                      a.summary_ro, a.effective_from, bm25({table}) AS bm_score
                      FROM {table} f JOIN provisions p ON p.id=f.provision_id
                      JOIN acts a ON a.id=p.act_id WHERE {table} MATCH ?{extra_sql}"""
            return self.conn.execute(sql, [match, *(extra_args or [])]).fetchall()

        if routed:
            tagged = self._ids_for_domains(routed, provisions=True)
            if tagged:
                ph = ",".join("?" for _ in tagged)
                rows = list(run(f" AND p.id IN ({ph})", tagged))
                if len(tagged) <= 40:
                    have = {r["id"] for r in rows}
                    missing = [pid for pid in tagged if pid not in have]
                    if missing:
                        ph2 = ",".join("?" for _ in missing)
                        filled = self.conn.execute(
                            f"""SELECT p.*, a.id AS act_id, a.title AS act_title, a.jurisdiction, a.status,
                               a.authority_class, a.version_coverage, a.last_checked, a.source_url, a.act_type,
                               a.summary_ro, a.effective_from, 99.0 AS bm_score
                               FROM provisions p JOIN acts a ON a.id=p.act_id WHERE p.id IN ({ph2})""",
                            missing,
                        ).fetchall()
                        rows.extend(filled)
                if rows:
                    return rows
            act_ids = self._ids_for_domains(routed, provisions=False)
            if act_ids:
                ph = ",".join("?" for _ in act_ids)
                rows = run(f" AND a.id IN ({ph})", act_ids)
                if rows:
                    return rows
        return run()

    def _outgoing_relations(self, act_id: str, relation_types: list[str] | None = None) -> list[sqlite3.Row]:
        # relations.tsv stores every relation in both directions (transposed_by <->
        # transposes, ...), so the act's outgoing rows already carry the correct
        # direction; reading incoming rows too would list each relation twice.
        sql = """SELECT r.*, a.title AS target_title, a.status AS target_status
                 FROM act_relations r JOIN acts a ON a.id = r.target_act_id
                 WHERE r.source_act_id=?"""
        args: list[Any] = [act_id]
        if relation_types:
            sql += f" AND r.relation_type IN ({','.join('?' for _ in relation_types)})"
            args.extend(relation_types)
        return list(self.conn.execute(sql + " ORDER BY r.relation_type, r.target_act_id", args))

    def _related_targets(self, act_id: str, relation: str | None = None) -> list[dict[str, Any]]:
        return [{"act_id": r["target_act_id"], "title": r["target_title"], "status": r["target_status"],
                 "relation_type": r["relation_type"], "source_reference": r["source_reference"]}
                for r in self._outgoing_relations(act_id, [relation] if relation else None)]

    def _human_reference(self, query: str) -> str | None:
        """Resolve simple human citations such as ``GDPR art. 6`` deterministically."""
        q = fold(query)
        article_match = re.search(r"\bart(?:icolul)?\.?\s*(\d+[a-z]?)", q)
        if not article_match:
            return None
        paragraph_match = re.search(r"\balin(?:iatul)?\.?\s*\(?([0-9]+)\)?", q)
        point_match = re.search(r"\blit(?:era)?\.?\s*\(?([a-z])\)?", q)
        article = article_match.group(1)
        for act in self.conn.execute("SELECT * FROM acts ORDER BY length(title) DESC"):
            aliases = [r[0] for r in self.conn.execute("SELECT alias FROM aliases WHERE act_id=?", (act["id"],))]
            haystack = [fold(act["id"]), fold(act["title"]), fold(act["short_title"]), *aliases]
            if any(alias and alias in q for alias in haystack):
                return canonical_citation(act["jurisdiction"], act["act_type"], act["number"], act["year"], "article", article,
                                          paragraph_match.group(1) if paragraph_match else None,
                                          letter=point_match.group(1) if point_match else None)
        return None

    def legal_search(self, query: str, corpus: str = "legislation", limit: int = 10,
                     as_of: str | None = None, jurisdictions: list[str] | None = None,
                     domains: list[str] | None = None, authority_classes: list[str] | None = None) -> dict[str, Any]:
        if corpus not in {"legislation", "case_law", "guidance"}:
            return self._error("jurist search", "UNSUPPORTED_CORPUS", f"Unknown corpus: {corpus}", as_of)
        limit = max(1, min(int(limit), 100))
        routed = sorted(set(domains or []) | set(self._route_domains(query)))
        # Level 1: a canonical citation in the query bypasses FTS.
        exact_candidates = re.findall(r"(?:RO|EU):[A-Za-z]+:(?:\d{4}:\d+|\d+:\d{4})(?::(?:ART|REC|ANN|PRE|art|recital|annex|preamble))?(?::[A-Za-z0-9.-]+)*", query)
        if corpus == "legislation" and not exact_candidates:
            human = self._human_reference(query)
            if human:
                exact_candidates = [human]
        rows: list[sqlite3.Row] = []
        table = {"legislation": "legislation_fts", "case_law": "case_law_fts", "guidance": "guidance_fts"}[corpus]
        if corpus == "legislation" and exact_candidates:
            ids = [normalize_citation(x) for x in exact_candidates]
            clauses = []
            args: list[Any] = []
            for cid in ids:
                clauses.append("(p.id=? OR p.id LIKE ?)")
                args.extend([cid, cid + ":%"])
            rows = self.conn.execute(
                "SELECT p.*,a.* FROM provisions p JOIN acts a ON a.id=p.act_id WHERE " + " OR ".join(clauses),
                args,
            ).fetchall()
        elif corpus != "legislation" and self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0:
            rows = []
        else:
            match = self._expanded_match(query)
            rows = self._fts_rows(table, match, routed)
        rows = self._jurisdiction_filter(rows, jurisdictions)
        if authority_classes:
            allowed = set(authority_classes)
            rows = [r for r in rows if r["authority_class"] in allowed]
        # Current status is a tool default. A non-current act can only be requested
        # by using a future explicit API layer; the runtime never silently returns it.
        rows = [r for r in rows if r["status"] == "in_force"]
        if routed and not exact_candidates:
            # Prefer provision-level tags (cookies → 506 art. 4(5), not the
            # whole act). Fall back to act tags, then to the unscoped hits.
            tagged: set[str] = set()
            for domain in routed:
                tagged.update(
                    r[0] for r in self.conn.execute(
                        "SELECT provision_id FROM provision_domains WHERE tag=?", (domain,)
                    )
                )
            provision_scoped = [r for r in rows if r["id"] in tagged] if tagged else []
            if provision_scoped:
                rows = provision_scoped
            else:
                act_scoped = [r for r in rows if set(self._domains_for_act(r["act_id"])) & set(routed)]
                if act_scoped:
                    rows = act_scoped
        # Stable ranking: exact IDs first, then scope/authority, then lexical score.
        exact_set = {normalize_citation(x) for x in exact_candidates}
        def _search_key(r: sqlite3.Row) -> tuple:
            exact = 0 if r["id"] in exact_set else 1
            paragraph = str(r["paragraph"] or "")
            core = 0 if not r["letter"] and not r["point"] and paragraph in {"", "1"} else 1
            bm = float(r["bm_score"]) if "bm_score" in r.keys() and r["bm_score"] is not None else 99.0
            return (exact, core, bm, -self._rank(r["authority_class"]), r["id"])
        rows.sort(key=_search_key)
        selected = rows[:limit]
        self._record(selected, as_of)
        hits = []
        warnings: list[str] = []
        for row in selected:
            act = self.conn.execute("SELECT * FROM acts WHERE id=?", (row["act_id"],)).fetchone()
            meta = self._meta(act, as_of, as_of is not None)
            warnings.extend(meta["warnings"])
            item = {"provision_id": row["id"], "act_id": row["act_id"], "act_title": row["title"] if "title" in row.keys() else row["act_title"],
                    "provision_type": row["provision_type"], "citable_as_binding_basis": row["citable_as_binding_basis"],
                    "article": row["article"], "paragraph": row["paragraph"], "point": row["point"], "letter": row["letter"],
                    "snippet": row["text"], "score": round(1.0 / (1.0 + max(0.0, float(row["bm_score"] or 0))), 6) if "bm_score" in row.keys() else 1.0,
                    "authority_class": row["authority_class"], "authority_rank": self._rank(row["authority_class"]),
                    "canonical_citation": row["id"], "transposed_by": self._related_targets(row["act_id"], "transposed_by"),
                    "warnings": meta["warnings"],
                    **{k: v for k, v in meta.items() if k != "warnings"}}
            hits.append(item)
        guidance_hits = 0
        if corpus == "legislation" and self.conn.execute("SELECT COUNT(*) FROM guidance_fts").fetchone()[0]:
            try:
                guidance_hits = self.conn.execute("SELECT COUNT(*) FROM guidance_fts WHERE guidance_fts MATCH ?", (self._expanded_match(query),)).fetchone()[0]
            except sqlite3.OperationalError:
                guidance_hits = 0
        if not hits:
            candidates = []
            act_ids: set[str] = set()
            for domain in routed:
                act_ids.update(r[0] for r in self.conn.execute("SELECT act_id FROM act_domains WHERE tag=?", (domain,)))
            for aid in sorted(act_ids):
                act = self.conn.execute("SELECT * FROM acts WHERE id=?", (aid,)).fetchone()
                if act:
                    candidates.append({"act_id": aid, "title": act["title"], "summary_ro": act["summary_ro"]})
            warnings.append("NO_MATCH_ABOVE_THRESHOLD")
        status = "OK" if hits else "NO_MATCH_ABOVE_THRESHOLD"
        next_action = {"tool": "jurist provision", "args": {"citation": hits[0]["provision_id"]}} if hits else None
        return self._envelope("jurist search", as_of, warnings, next_action, status=status, corpus=corpus,
                              guidance_hits_excluded=guidance_hits, routed_domains=routed, results=hits,
                              candidate_acts=candidates if not hits else [])

    def _error(self, tool: str, code: str, message: str, as_of: str | None) -> dict[str, Any]:
        return {"tool": tool, "ok": False, "error": {"code": code, "message": message}, "as_of": as_of or _today(),
                "warnings": [], "next_action": None}

    def _resolve_act_id(self, value: str) -> sqlite3.Row | None:
        canonical = normalize_citation(value) if ":" in value else None
        if canonical and self.conn.execute("SELECT 1 FROM acts WHERE id=?", (canonical,)).fetchone():
            return self.conn.execute("SELECT * FROM acts WHERE id=?", (canonical,)).fetchone()
        matches = self._act_match(value)
        return matches[0] if matches else None

    def get_provision(self, citation: str | None = None, context: str | None = None, as_of: str | None = None,
                      act: str | None = None, article: str | None = None, paragraph: str | None = None,
                      point: str | None = None, letter: str | None = None) -> dict[str, Any]:
        act_row: sqlite3.Row | None = None
        if citation and not article and not act:
            cid = normalize_citation(citation)
            if as_of:
                row = self.conn.execute("""SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id
                    WHERE p.id=? AND (p.valid_from IS NULL OR p.valid_from<=?)
                      AND (p.valid_to IS NULL OR ?<p.valid_to)
                    ORDER BY COALESCE(p.valid_from,'') DESC, p.sequence DESC LIMIT 1""", (cid, as_of, as_of)).fetchone()
            else:
                row = self.conn.execute("SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id WHERE p.id=? ORDER BY COALESCE(p.valid_from,'') DESC, p.sequence DESC LIMIT 1", (cid,)).fetchone()
        else:
            act_row = self._resolve_act_id(act or citation or "")
            if not act_row:
                return self._error("jurist provision", "UNKNOWN_ACT", "Actul nu există în corpus.", as_of)
            cid = self._provision_citation_for_row(act_row, article, paragraph, point, letter)
            row = self.conn.execute("SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id WHERE p.id=? ORDER BY COALESCE(p.valid_from,'') DESC, p.sequence DESC LIMIT 1", (cid,)).fetchone()
        article_children: list[sqlite3.Row] = []
        if row is None and paragraph is None and point is None and letter is None:
            # The parser stores an article-level row only when the source has an
            # explicit article heading/lead; otherwise the article exists only
            # as its alin./lit. children. Reconstruct it deterministically.
            article_no = article or self._article_level_of(cid)
            if article_no:
                if act_row is None:
                    prefix = ":".join(cid.split(":")[:4])
                    act_row = self.conn.execute("SELECT * FROM acts WHERE id=?", (prefix,)).fetchone()
                if act_row is not None:
                    article_children = self._article_children(act_row["id"], article_no, as_of)
                    if article_children:
                        row = article_children[0]
        if not row:
            return self._error("jurist provision", "NOT_FOUND", "Provision not found in the local corpus.", as_of)
        act_row = self.conn.execute("SELECT * FROM acts WHERE id=?", (row["act_id"],)).fetchone()
        if context == "article":
            if article_children:
                rows = article_children
            elif as_of:
                rows = self.conn.execute("""SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id
                    WHERE p.act_id=? AND p.article=? AND (p.valid_from IS NULL OR p.valid_from<=?)
                      AND (p.valid_to IS NULL OR ?<p.valid_to) ORDER BY p.sequence""", (row["act_id"], row["article"], as_of, as_of)).fetchall()
            else:
                rows = self.conn.execute("SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id WHERE p.act_id=? AND p.article=? ORDER BY p.sequence", (row["act_id"], row["article"])).fetchall()
        elif context == "section":
            if article_children:
                first, last = article_children[0], article_children[-1]
                lo, hi = max(0, first["sequence"] - 1), last["sequence"] + 1
                if as_of:
                    rows = self.conn.execute("""SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id
                        WHERE p.act_id=? AND p.sequence BETWEEN ? AND ? AND (p.valid_from IS NULL OR p.valid_from<=?)
                          AND (p.valid_to IS NULL OR ?<p.valid_to) ORDER BY p.sequence""", (row["act_id"], lo, hi, as_of, as_of)).fetchall()
                else:
                    rows = self.conn.execute("SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id WHERE p.act_id=? AND p.sequence BETWEEN ? AND ? ORDER BY p.sequence", (row["act_id"], lo, hi)).fetchall()
            elif as_of:
                rows = self.conn.execute("""SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id
                    WHERE p.act_id=? AND p.sequence BETWEEN ? AND ? AND (p.valid_from IS NULL OR p.valid_from<=?)
                      AND (p.valid_to IS NULL OR ?<p.valid_to) ORDER BY p.sequence""", (row["act_id"], max(0, row["sequence"] - 1), row["sequence"] + 1, as_of, as_of)).fetchall()
            else:
                rows = self.conn.execute("SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id WHERE p.act_id=? AND p.sequence BETWEEN ? AND ? ORDER BY p.sequence", (row["act_id"], max(0, row["sequence"] - 1), row["sequence"] + 1)).fetchall()
        else:
            rows = article_children if article_children else [row]
        self._record(rows, as_of, [(cid, row["act_id"])] if article_children else [])
        meta = self._meta(act_row, as_of, as_of is not None)
        warnings = list(meta["warnings"])
        items = []
        for item_row in rows:
            item = {"provision_id": item_row["id"], "act_id": item_row["act_id"], "act_title": item_row["act_title"],
                    "provision_type": item_row["provision_type"], "citable_as_binding_basis": item_row["citable_as_binding_basis"],
                    "article": item_row["article"], "paragraph": item_row["paragraph"], "point": item_row["point"], "letter": item_row["letter"],
                    "text": item_row["text"], "canonical_citation": item_row["id"], "full_article_available": True,
                    "context_call": f"jurist provision --act {act_row['id']} --article {item_row['article']} --context section --json",
                    "valid_from": item_row["valid_from"], "valid_to": item_row["valid_to"], **{k: v for k, v in meta.items() if k != "warnings"}}
            items.append(item)
        if article_children:
            provision_item = self._article_payload(cid, act_row, article_children, meta)
        else:
            provision_item = next((x for x in items if x["provision_id"] == row["id"]), items[0])
        next_action = {"tool": "jurist related", "args": {"act_id": act_row["id"]}}
        # `provision` is the canonical v1 field; `context` carries the requested
        # neighboring rows. There is no plural alias in the public contract.
        return self._envelope("jurist provision", as_of, warnings, next_action,
                              provision=provision_item, context=items)

    @staticmethod
    def _article_level_of(cid: str) -> str | None:
        """Article number when the citation addresses a whole article (ACT:ART:n)."""
        parts = cid.split(":")
        for index, part in enumerate(parts):
            if part.upper() == "ART" and index + 1 < len(parts):
                rest = [p.upper() for p in parts[index + 2:]]
                if any(marker in rest for marker in ("P", "POINT", "L")):
                    return None
                return parts[index + 1]
        return None

    def _article_children(self, act_id: str, article: str, as_of: str | None) -> list[sqlite3.Row]:
        """All article-type rows of one article, in legal reading order."""
        if as_of:
            return self.conn.execute(
                """SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id
                   WHERE p.act_id=? AND p.article=? AND p.provision_type='article'
                     AND (p.valid_from IS NULL OR p.valid_from<=?)
                     AND (p.valid_to IS NULL OR ?<p.valid_to) ORDER BY p.sequence""",
                (act_id, article, as_of, as_of)).fetchall()
        return self.conn.execute(
            """SELECT p.*,a.title AS act_title,a.* FROM provisions p JOIN acts a ON a.id=p.act_id
               WHERE p.act_id=? AND p.article=? AND p.provision_type='article' ORDER BY p.sequence""",
            (act_id, article)).fetchall()

    @staticmethod
    def _article_payload(cid: str, act_row: sqlite3.Row, children: list[sqlite3.Row],
                         meta: dict[str, Any]) -> dict[str, Any]:
        """Synthesize the article-level payload from its ordered children."""
        chunks = []
        for child in children:
            marker_parts = []
            if child["paragraph"] is not None:
                marker_parts.append(f"({child['paragraph']})")
            if child["point"] is not None:
                marker_parts.append(f"punctul ({child['point']})")
            if child["letter"] is not None:
                marker_parts.append(f"lit. ({child['letter']})")
            marker = " ".join(marker_parts)
            chunks.append(f"{marker} {child['text']}" if marker else child["text"])
        valid_from = min((c["valid_from"] for c in children if c["valid_from"]), default=None)
        valid_to = max((c["valid_to"] for c in children if c["valid_to"]), default=None)
        return {
            "provision_id": cid, "act_id": act_row["id"], "act_title": children[0]["act_title"],
            "provision_type": "article", "citable_as_binding_basis": 1,
            "article": children[0]["article"], "paragraph": None, "point": None, "letter": None,
            "text": "\n".join(chunks), "canonical_citation": cid, "full_article_available": True,
            "context_call": f"jurist provision --act {act_row['id']} --article {children[0]['article']} --context section --json",
            "valid_from": valid_from, "valid_to": valid_to,
            **{k: v for k, v in meta.items() if k != "warnings"},
        }

    @staticmethod
    def _provision_citation_for_row(act: sqlite3.Row, article: str | None, paragraph: str | None, point: str | None, letter: str | None) -> str:
        if not article:
            raise ValueError("article is required")
        return canonical_citation(act["jurisdiction"], act["act_type"], act["number"], act["year"], "article", article, paragraph, point, letter)

    def find_related(self, act_id: str | None = None, relations: list[str] | None = None, identifier: str | None = None) -> dict[str, Any]:
        target = act_id or identifier or ""
        row = self._resolve_act_id(target)
        canonical = row["id"] if row else target
        if row:
            result = [{"source_act_id": rel["source_act_id"], "target_act_id": rel["target_act_id"],
                       "relation_type": rel["relation_type"], "target_title": rel["target_title"],
                       "target_status": rel["target_status"], "source_reference": rel["source_reference"]}
                      for rel in self._outgoing_relations(canonical, relations)]
        else:
            result = []
        meta = self._meta(row) if row else {"warnings": []}
        return self._envelope("jurist related", None, meta.get("warnings", []), {"tool": "jurist resolve", "args": {"reference": target}} if not result else None,
                              status="OK" if result else "NO_MATCH_ABOVE_THRESHOLD", act={"act_id": canonical, **{k: meta[k] for k in ("status", "in_force_on_as_of", "amended_since", "version_coverage", "applicability")}} if row else None,
                              relations=result)

    def corpus_status(self) -> dict[str, Any]:
        acts = []
        for act in self.conn.execute("SELECT * FROM acts ORDER BY id"):
            meta = self._meta(act)
            acts.append({"act_id": act["id"], "title": act["title"], "status": act["status"],
                         "version_coverage": act["version_coverage"], "last_checked": act["last_checked"],
                         "domains": self._domains_for_act(act["id"]), "scope_provisions": json.loads(act["scope_provisions"] or "[]"),
                         "source_url": meta["source_url"]})
        # Per-source documents/freshness are derived from the live acts/act_versions
        # tables, not from the corpus_status table written by the last ingest run.
        # Legacy rows with a misspelled source key (e.g. 'jurislatie_just_ro') are ignored.
        table_rows = {r["source"]: r for r in self.conn.execute("SELECT * FROM corpus_status")}

        def source_entry(name: str, jurisdiction: str, default_method: str) -> dict[str, Any]:
            row = table_rows.get(name)
            documents = self.conn.execute("SELECT COUNT(*) FROM acts WHERE jurisdiction=?", (jurisdiction,)).fetchone()[0]
            last_sync = self.conn.execute(
                """SELECT MAX(v.retrieved_at) FROM act_versions v JOIN acts a ON a.id=v.act_id
                   WHERE a.jurisdiction=?""", (jurisdiction,)).fetchone()[0]
            status = (row["status"] if row else None) or ("ingested" if documents else "not_downloaded")
            method = (row["method"] if row else None) or default_method
            return {"method": method, "last_sync": last_sync, "status": status, "documents": documents}

        sources = {
            "legislatie_just_ro": source_entry("legislatie_just_ro", "RO", "SOAP"),
            "eurlex_cellar": source_entry("eurlex_cellar", "EU", "CELLAR"),
        }
        for source, row in table_rows.items():
            if source in sources or source == "jurislatie_just_ro":
                continue
            sources[source] = {"method": row["method"], "last_sync": row["last_sync"],
                               "status": row["status"], "documents": row["documents"]}
        domain_counts = {r[0]: r[1] for r in self.conn.execute("SELECT tag,COUNT(*) FROM act_domains GROUP BY tag ORDER BY tag")}
        configured = self._configured_act_count()
        warnings = ["REAL_SOURCES_NOT_DOWNLOADED"] if any(x["status"] == "not_downloaded" for x in sources.values()) else []
        return self._envelope("jurist corpus-status", None, warnings, None,
                              schema_version=1,
                              last_build=self.conn.execute("SELECT MAX(retrieved_at) FROM act_versions").fetchone()[0],
                              configured_act_count=configured, counts={
                                  "acts": len(acts), "provisions": self.conn.execute("SELECT COUNT(*) FROM provisions").fetchone()[0],
                                  "aliases": self.conn.execute("SELECT COUNT(*) FROM aliases").fetchone()[0],
                                  "act_versions": self.conn.execute("SELECT COUNT(*) FROM act_versions").fetchone()[0],
                                  "relations": self.conn.execute("SELECT COUNT(*) FROM act_relations").fetchone()[0]},
                              sources=sources, acts=acts, domains=domain_counts)

    def _configured_act_count(self) -> int:
        path = ROOT / "sources" / "corpus.yaml"
        if not path.exists():
            return 0
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if re.match(r"\s*- id:\s*", line))

    def validate_citations(self, draft: str, as_of: str | None = None) -> dict[str, Any]:
        pattern = re.compile(r"\b(?:RO|EU|CJEU):[A-Za-z]+(?::[A-Za-z0-9.-]+){2,}(?::(?:ART|REC|ANN|PRE|art|recital|annex|preamble))?(?::[A-Za-z0-9.-]+)*\b")
        citations: list[str] = []
        for match in pattern.findall(draft):
            # Keep only strings with a path marker; this prevents matching a bare act ID twice.
            if (":ART:" in match.upper() or ":REC:" in match.upper() or ":ANN:" in match.upper()
                    or ":PRE" in match.upper() or match.upper().startswith("CJEU:") and ":P:" in match.upper()):
                canonical = normalize_citation(match)
                if canonical not in citations:
                    citations.append(canonical)
        issues = []
        retrieved = {entry["provision_id"] for entry in self.retrieval_log}
        # Session scoping: validation judges the draft against what THIS session
        # retrieved, both in-process and previously logged under the same id.
        retrieved |= {r[0] for r in self.conn.execute(
            "SELECT provision_id FROM retrieval_log WHERE session_id=?", (self.session_id,))}
        for citation in citations:
            row = self.conn.execute("SELECT p.*,a.version_coverage,a.status,a.last_checked FROM provisions p JOIN acts a ON a.id=p.act_id WHERE p.id=?", (citation,)).fetchone()
            if not row:
                issues.append({"citation": citation, "code": "UNKNOWN_CITATION"})
                continue
            if citation not in retrieved:
                issues.append({"citation": citation, "code": "CITED_WITHOUT_RETRIEVAL"})
                continue
            if as_of and row["version_coverage"] == "current_only" and as_of != (row["last_checked"] or "")[:10]:
                issues.append({"citation": citation, "code": "OUTDATED_PROVISION"})
            elif as_of and row["valid_from"] and as_of < row["valid_from"]:
                issues.append({"citation": citation, "code": "OUTDATED_PROVISION"})
        return {"valid": not issues, "citations": citations, "issues": issues, "warnings": [], "next_action": None}

    def apply_tags(self, path: Path | None = None) -> dict[str, Any]:
        """Insert human provision/act tags from sources/tags.tsv. Idempotent."""
        tags_path = Path(path) if path else ROOT / "sources" / "tags.tsv"
        stats = {"acts": 0, "provisions": 0, "skipped": [], "rows": 0}
        if not tags_path.exists():
            stats["skipped"].append(f"missing {tags_path}")
            return stats
        known_acts = {r[0] for r in self.conn.execute("SELECT id FROM acts")}
        for line_no, raw in enumerate(tags_path.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 3:
                stats["skipped"].append(f"tags.tsv:{line_no}: bad format")
                continue
            kind, entity_id, tag_field = fields[0].strip().lower(), fields[1].strip(), fields[2]
            tags = [fold(t) for t in tag_field.split(",") if fold(t)]
            if not tags:
                stats["skipped"].append(f"tags.tsv:{line_no}: no tags")
                continue
            stats["rows"] += 1
            if kind == "act":
                if entity_id not in known_acts:
                    stats["skipped"].append(f"tags.tsv:{line_no}: unknown act {entity_id}")
                    continue
                for tag in tags:
                    self._insert_domain(entity_id, tag, is_act=True)
                    stats["acts"] += 1
                continue
            if kind != "provision":
                stats["skipped"].append(f"tags.tsv:{line_no}: unknown kind {kind}")
                continue
            ids = [r[0] for r in self.conn.execute(
                "SELECT id FROM provisions WHERE id=? OR id LIKE ?",
                (entity_id, entity_id + ":%"),
            )]
            if not ids:
                stats["skipped"].append(f"tags.tsv:{line_no}: no provisions for {entity_id}")
                continue
            for pid in ids:
                for tag in tags:
                    self._insert_domain(pid, tag, is_act=False)
                    stats["provisions"] += 1
        self.conn.commit()
        return stats

    def ingest_snapshot(self, act: dict[str, Any], version: dict[str, Any], provisions: list[dict[str, Any]]) -> dict[str, Any]:
        """Insert one immutable parsed snapshot and its canonical provisions.

        This is the boundary between fetch/parse and runtime retrieval. It does
        not overwrite an existing checksum; callers can safely retry a build.
        """
        aid = act["id"]
        retrieved_at = version.get("retrieved_at") or _today()
        source_url = version.get("source_url") or act.get("source_url") or ""
        checksum = version.get("checksum") or hashlib.sha256(
            "\\n".join(normalize(p.get("text")) for p in provisions).encode("utf-8")
        ).hexdigest()
        existing = self.conn.execute("SELECT id FROM act_versions WHERE act_id=? AND checksum=?", (aid, checksum)).fetchone()
        if existing:
            return {"status": "NO_OP", "act_id": aid, "version_id": existing[0], "added": 0, "warnings": []}
        self.conn.execute(
            """INSERT INTO acts(id,jurisdiction,source_system,celex,eli,act_type,number,year,title,short_title,
               issuer,status,authority_class,version_coverage,language,scope_provisions,summary_ro,source_url,last_checked)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET title=excluded.title,status=excluded.status,
                 authority_class=excluded.authority_class,version_coverage=excluded.version_coverage,
                 summary_ro=excluded.summary_ro,source_url=excluded.source_url,last_checked=excluded.last_checked""",
            (aid, act.get("jurisdiction", "RO"), act.get("source_system", "ingest"), act.get("celex"), act.get("eli"),
             act.get("act_type", "ACT"), str(act.get("number", "0")), int(act.get("year", 0)), act.get("title", aid),
             act.get("short_title"), act.get("issuer"), act.get("status", "in_force"), act.get("authority_class", "binding_legislation"),
             act.get("version_coverage", "current_only"), act.get("language", "ro"), json.dumps(act.get("scope_provisions", []), ensure_ascii=False),
             act.get("summary_ro", ""), source_url, retrieved_at[:10]),
        )
        version_id = version.get("id") or f"{aid}:VERSION:{checksum[:12]}"
        # Close the previous interval when a real version date is available
        # (EU consolidations). RO polling may omit it: detection is not law.
        version_start = version.get("valid_from") or version.get("version_date")
        if version_start:
            previous = self.conn.execute("SELECT id FROM act_versions WHERE act_id=? AND valid_to IS NULL ORDER BY COALESCE(valid_from,'') DESC LIMIT 1", (aid,)).fetchone()
            if previous:
                self.conn.execute("UPDATE act_versions SET valid_to=? WHERE id=?", (version_start, previous[0]))
                self.conn.execute("UPDATE provisions SET valid_to=? WHERE act_version_id=? AND valid_to IS NULL", (version_start, previous[0]))
        self.conn.execute(
            """INSERT INTO act_versions(id,act_id,valid_from,valid_to,version_date,consolidation_date,detected_at,
               data_vigoare_reported,source_url,checksum,retrieved_at,parser_version,language,is_consolidated,legally_authentic)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (version_id, aid, version.get("valid_from"), version.get("valid_to"), version.get("version_date"),
             version.get("consolidation_date"), version.get("detected_at"), version.get("data_vigoare_reported"),
             source_url, checksum, retrieved_at, version.get("parser_version", "1"), act.get("language", "ro"),
             int(version.get("is_consolidated", act.get("jurisdiction") == "EU")), version.get("legally_authentic")),
        )
        for alias in act.get("aliases", []):
            self.conn.execute("INSERT OR IGNORE INTO aliases(alias,act_id,priority) VALUES(?,?,?)", (fold(alias), aid, 10))
        for domain in act.get("domains", []):
            self._insert_domain(aid, domain, is_act=True)
        act_row = self.conn.execute("SELECT * FROM acts WHERE id=?", (aid,)).fetchone()
        # Route by corpus, defaulting to legislation. The corpus registry uses a
        # finer vocabulary than the generic "binding_legislation" label
        # (eu_regulation, eu_directive, ro_law, ro_government_ordinance...), so
        # anything not explicitly case law or guidance is binding legislation.
        cls = act_row["authority_class"] or ""
        if "case_law" in cls:
            fts_table = "case_law_fts"
        elif "guidance" in cls or "decision" in cls or cls == "informational":
            fts_table = "guidance_fts"
        else:
            fts_table = "legislation_fts"
        for sequence, provision in enumerate(provisions, start=1):
            ptype = provision.get("provision_type", "article")
            cid = normalize_citation(provision.get("id") or self._provision_citation(act_row, provision))
            text = normalize(provision.get("text"))
            self.conn.execute(
                """INSERT INTO provisions(id,act_id,act_version_id,provision_type,citable_as_binding_basis,article,paragraph,point,letter,heading,text,valid_from,valid_to,sequence,canonical_citation)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, aid, version_id, ptype, int(provision.get("citable", 0 if ptype in {"recital", "preamble"} else 1)),
                 provision.get("article"), provision.get("paragraph"), provision.get("point"), provision.get("letter"),
                 provision.get("heading"), text, version.get("valid_from"), version.get("valid_to"), provision.get("sequence", sequence), cid),
            )
            aliases = [r[0] for r in self.conn.execute("SELECT alias FROM aliases WHERE act_id=?", (aid,))]
            self.conn.execute("INSERT INTO " + fts_table + "(provision_id,text) VALUES(?,?)", (cid, normalize(" ".join([act_row["title"], *aliases, text, *provision.get("domains", [])]))))
            for domain in provision.get("domains", []):
                self._insert_domain(cid, domain, is_act=False)
        self.conn.commit()
        return {"status": "INSERTED", "act_id": aid, "version_id": version_id, "added": len(provisions), "checksum": checksum, "warnings": []}

    def update(self) -> dict[str, Any]:
        """Return the safe offline no-op; network update is performed by fetch scripts."""
        return {"status": "NO_OP", "new_versions": 0, "warnings": ["NETWORK_FETCH_NOT_RUN"], "next_action": "schedule_fetch"}

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "JuristEngine":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
