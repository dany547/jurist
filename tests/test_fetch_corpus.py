"""Offline unit tests for scripts/fetch_corpus.py.

No network: TipAct matching, RO filename mapping (ingest_corpus contract),
manifest upsert, consolidated selection, consolidation-list parsing, content
gate no-overwrite behaviour, dry-run planning/CLI.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.fetch_corpus as fc  # noqa: E402

RO_HTML = ("<html><body>" + "Articolul 1. Dispozitii generale. " + "x" * 6000
           + "</body></html>")
EU_HTML = "<html><body>" + "Articolul 1 " + "y" * 6000 + "</body></html>"


def ro_row(**over) -> dict:
    row = {
        "DataVigoare": "28.11.2004",
        "Emitent": "Parlamentul Romaniei",
        "LinkHtml": "https://legislatie.just.ro/Public/DetaliiDocument/56973",
        "Numar": "506",
        "Publicatie": "MO 878/2004",
        "Text": "original published form — must never be stored as canonical",
        "TipAct": "LEGE",
        "Titlu": "Legea nr. 506 din 2004",
    }
    row.update(over)
    return row


def manifest_entry(celex_base="32016R0679", celex_downloaded="02016R0679-20160504",
                   sha256="a" * 64, **over) -> dict:
    entry = {
        "status": "ok", "celex_base": celex_base,
        "celex_downloaded": celex_downloaded,
        "is_consolidated": celex_downloaded != celex_base,
        "url": f"https://publications.europa.eu/resource/celex/{celex_downloaded}",
        "sha256": sha256, "bytes": 100, "articole_gasite": 10,
    }
    entry.update(over)
    return entry


# ── TipAct matching (SOAP cannot filter TipAct server-side) ─────────────

@pytest.mark.parametrize("tipact,tip,expected", [
    ("LEGE", "LEGE", True),
    ("lege", "LEGE", True),
    ("ORDONANȚĂ DE URGENȚĂ", "OUG", True),
    ("ORDONANŢĂ DE URGENŢĂ", "OUG", True),        # cedilla variant
    ("ordonanta de urgenta", "OUG", True),
    ("OUG", "OUG", True),
    ("ORDONANȚĂ", "OG", True),
    ("ordonanţă", "OG", True),                    # cedilla variant
    ("ORDONANȚĂ DE URGENȚĂ", "OG", False),        # OUG must not satisfy OG
    ("HOTĂRÂRE", "HG", True),
    ("hotărâre", "HG", True),
    ("HG", "HG", True),
    ("DECRET", "LEGE", False),
    ("HOTĂRÂRE", "OUG", False),
    (None, "LEGE", False),
])
def test_tip_act_matches(tipact, tip, expected):
    assert fc.tip_act_matches(tipact, tip) is expected


def test_pick_ro_result_selects_type_client_side():
    rows = [
        ro_row(TipAct="HOTĂRÂRE", LinkHtml="h1", Titlu="Hotararea nr. 1"),
        ro_row(TipAct="ORDONANȚĂ DE URGENȚĂ", LinkHtml="h2",
               Titlu="Ordonanța de urgență nr. 34 din 28 martie 2014"),
        ro_row(TipAct="LEGE", LinkHtml="h3", Titlu="Legea nr. 506 din 2004"),
    ]
    assert fc.pick_ro_result(rows, "OUG", 2014)["LinkHtml"] == "h2"
    assert fc.pick_ro_result(rows, "LEGE", 2004)["LinkHtml"] == "h3"
    with pytest.raises(fc.FetchError):
        fc.pick_ro_result(rows, "OG", 2014)   # no plain ORDONANȚĂ (OG) in rows
    assert fc.pick_ro_result(rows, "HG", 2014)["LinkHtml"] == "h1"


def test_pick_ro_result_rejects_ambiguity_and_missing_link():
    two = [ro_row(TipAct="ORDONANȚĂ", LinkHtml="a", Titlu="OG nr. 1 din 2001"),
           ro_row(TipAct="ORDONANȚĂ", LinkHtml="b", Titlu="OG nr. 2 din 2001")]
    with pytest.raises(fc.FetchError, match="ambiguous"):
        fc.pick_ro_result(two, "OG", 2001)
    no_link = [ro_row(LinkHtml="  ")]
    with pytest.raises(fc.FetchError, match="LinkHtml"):
        fc.pick_ro_result(no_link, "LEGE", 2004)


def test_pick_ro_result_prefers_title_starting_with_tip():
    # Both rows share tip + number + year; only the real act's Titlu STARTS
    # with the type — a document that merely mentions it must lose.
    rows = [
        ro_row(TipAct="LEGE", LinkHtml="mention",
               Titlu="Studiu privind aplicarea Legii nr. 190/2018"),
        ro_row(TipAct="LEGE", LinkHtml="real",
               Titlu="Lege nr. 190 din 2018 privind aplicarea RGPD"),
    ]
    assert fc.pick_ro_result(rows, "LEGE", 2018, numar=190)["LinkHtml"] == "real"


def test_pick_ro_result_number_narrows_before_ambiguity():
    rows = [
        ro_row(TipAct="LEGE", LinkHtml="l-505", Titlu="Legea nr. 505 din 2004"),
        ro_row(TipAct="LEGE", LinkHtml="l-506", Titlu="Legea nr. 506 din 2004"),
    ]
    with pytest.raises(fc.FetchError, match="ambiguous"):
        fc.pick_ro_result(rows, "LEGE", 2004)            # no numar → ambiguous
    assert fc.pick_ro_result(rows, "LEGE", 2004, numar=506)["LinkHtml"] == "l-506"


def test_pick_ro_result_identity_beats_year_mentioned_in_subject():
    # Live portal behaviour (2026-09-29): Search(2024, 50) also returns
    # "LEGE nr. 50 din 17 aprilie 2026 privind aprobarea OUG nr. 38/2024", whose
    # title CITES 2024. Only the act whose own issue date is 2024 may win.
    rows = [
        ro_row(TipAct="LEGE", LinkHtml="wrong",
               Titlu="LEGE nr. 50 din 17 aprilie 2026 privind aprobarea "
                     "Ordonan\u0163ei de urgen\u0163\u0103 a Guvernului nr. 38/2024"),
        ro_row(TipAct="LEGE", LinkHtml="right",
               Titlu="LEGE nr. 50 din 18 martie 2024 privind stabilirea unor "
                     "m\u0103suri pentru aplicarea Regulamentului (UE) 2022/2.065"),
    ]
    assert fc.pick_ro_result(rows, "LEGE", 2024, numar=50)["LinkHtml"] == "right"


def test_pick_ro_result_identity_rejects_other_year_same_number():
    # The mis-pick that corrupted raw/ro/OUG_34_2014.html once: OUG 34/2017
    # mentions 2014 in its subject and must never satisfy a 34/2014 request.
    rows = [
        ro_row(TipAct="ORDONANȚĂ DE URGENȚĂ", LinkHtml="wrong",
               Titlu="ORDONANȚĂ DE URGENȚĂ nr. 34 din 5 mai 2017 privind "
                     "gestionarea financiar\u0103 a fondurilor 2014-2020"),
        ro_row(TipAct="ORDONANȚĂ DE URGENȚĂ", LinkHtml="right",
               Titlu="ORDONANȚĂ DE URGENȚĂ nr. 34 din 30 aprilie 2014 "
                     "privind drepturile consumatorilor"),
    ]
    got = fc.pick_ro_result(rows, "OUG", 2014, numar=34)
    assert got["LinkHtml"] == "right"


def test_pick_ro_result_same_act_two_manifestations():
    # HG 947/2000 is listed twice: original 24730 and republished form 97219.
    # Same 'nr. 947 din 13 octombrie 2000' identity → newest document id wins.
    rows = [
        ro_row(TipAct="HOTĂRÂRE", Numar="947",
               LinkHtml="https://legislatie.just.ro/Public/DetaliiDocument/24730",
               Titlu="\ufeff HOTĂRÂRE nr. 947 din 13 octombrie 2000 privind "
                     "modalitatea de indicare a preţurilor"),
        ro_row(TipAct="HOTĂRÂRE", Numar="947",
               LinkHtml="https://legislatie.just.ro/Public/DetaliiDocument/97219",
               Titlu="\ufeff HOTĂRÂRE nr. 947 din 13 octombrie 2000 (*republicată*) "
                     "privind modalitatea de indicare a preţurilor"),
    ]
    got = fc.pick_ro_result(rows, "HG", 2000, numar=947)
    assert got["LinkHtml"].endswith("/97219")


def test_pick_ro_result_strips_utf8_bom_from_title():
    # Portal rows may begin with U+FEFF; the type-prefix narrowing still applies.
    rows = [
        ro_row(TipAct="LEGE", LinkHtml="bom",
               Titlu="\ufeff LEGE nr. 363 din 21 decembrie 2007 privind "
                     "combaterea practicilor incorecte"),
        ro_row(TipAct="LEGE", LinkHtml="plain",
               Titlu="LEGE nr. 363 din 28 decembrie 2018 privind protec\u0163ia "
                     "persoanelor fizice"),
    ]
    assert fc.pick_ro_result(rows, "LEGE", 2007, numar=363)["LinkHtml"] == "bom"


# ── RO filename mapping (contract with ingest_corpus._ro_filename_to_meta) ─

def _ingest_type_map() -> dict:
    """Read _RO_TYPE_MAP from ingest_corpus.py WITHOUT importing it (its
    import pulls jurist.engine; also keeps the test offline & unedited)."""
    src = (ROOT / "scripts" / "ingest_corpus.py").read_text(encoding="utf-8")
    m = re.search(r"_RO_TYPE_MAP\s*=\s*(\{.*?\})", src, re.S)
    assert m, "_RO_TYPE_MAP not found in ingest_corpus.py"
    return ast.literal_eval(m.group(1))


def test_ro_filename_maps_to_ingest_accepted_tokens():
    type_map = _ingest_type_map()
    # Report-only check: OG and HG tokens are already accepted by ingest.
    assert {"LEGE", "OUG", "OG", "HG"} <= set(type_map)
    assert fc.ro_filename("OG", 21, 1992) == "OG_21_1992.html"
    assert fc.ro_filename("lege", 506, 2004) == "LEGE_506_2004.html"

    ro_acts = [a for a in fc.load_corpus() if a["id"].startswith("RO:")]
    assert ro_acts
    for act in ro_acts:
        spec = act["fetch"]
        filename = fc.ro_filename(spec["tip"], spec["numar"], spec["an"])
        prefix, number, year = filename[: -len(".html")].split("_")
        # Mirror of ingest_corpus._ro_filename_to_meta on our filename:
        assert prefix in type_map, f"{prefix} not accepted by ingest"
        assert type_map[prefix] == spec["tip"]
        assert number == str(spec["numar"])
        assert int(year) == spec["an"]
        assert act["id"] == f"RO:{type_map[prefix]}:{number}:{year}"


# ── consolidated selection ──────────────────────────────────────────────

def test_select_celex_pinned_vs_base():
    assert fc.select_celex({"celex": "32011L0083",
                            "consolidated": "02011L0083-20250901"}) == ("02011L0083-20250901", True)
    assert fc.select_celex({"celex": "32018R0302"}) == ("32018R0302", False)
    assert fc.select_celex({"celex": "32016R0679",
                            "consolidated": None}) == ("32016R0679", False)


def test_select_celex_for_every_corpus_eu_act():
    for act in fc.load_corpus():
        if not act["id"].startswith("EU:"):
            continue
        downloaded, is_con = fc.select_celex(act["fetch"])
        assert downloaded == act["fetch"].get("consolidated", act["fetch"]["celex"])
        assert is_con == (downloaded != act["fetch"]["celex"])


# ── manifest upsert ─────────────────────────────────────────────────────

def test_upsert_manifest_replaces_same_celex_base_in_place(tmp_path):
    path = tmp_path / "MANIFEST.json"
    first = manifest_entry()                                   # 32016R0679 pinned
    second = manifest_entry(celex_base="32018R0302",
                            celex_downloaded="32018R0302")
    path.write_text(json.dumps([first, second], indent=1), encoding="utf-8")

    new = manifest_entry(celex_downloaded="32016R0679", sha256="b" * 64)
    out = fc.upsert_manifest(new, path)

    assert [e["celex_base"] for e in out] == ["32016R0679", "32018R0302"]
    assert out[0]["celex_downloaded"] == "32016R0679"   # replaced, not appended
    assert out[0]["sha256"] == "b" * 64
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert len(on_disk) == 2
    assert len([e for e in on_disk if e["celex_base"] == "32016R0679"]) == 1


def test_upsert_manifest_creates_file_and_keeps_schema(tmp_path):
    path = tmp_path / "sub" / "MANIFEST.json"
    entry = manifest_entry(celex_base="32019R1150", celex_downloaded="32019R1150")
    out = fc.upsert_manifest(entry, path)
    assert path.exists()
    assert len(out) == 1
    assert set(entry) == set(fc.MANIFEST_KEYS)  # exact ingest/eu schema
    assert json.loads(path.read_text(encoding="utf-8"))[0]["status"] == "ok"


def test_read_manifest_missing_and_invalid(tmp_path):
    assert fc.read_manifest(tmp_path / "nope.json") == []
    bad = tmp_path / "MANIFEST.json"
    bad.write_text('{"not": "a list"}', encoding="utf-8")
    with pytest.raises(fc.FetchError):
        fc.read_manifest(bad)


def test_upsert_manifest_writes_atomically(tmp_path, monkeypatch):
    path = tmp_path / "MANIFEST.json"
    path.write_text(json.dumps([manifest_entry()]), encoding="utf-8")
    calls: list[tuple[str, str]] = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(fc.os, "replace", spy)
    fc.upsert_manifest(manifest_entry(sha256="c" * 64), path)

    assert calls == [(str(path) + ".tmp", str(path))]   # tmp file + rename
    assert not list(tmp_path.glob("*.tmp"))             # no leftover temp file
    assert json.loads(path.read_text(encoding="utf-8"))[0]["sha256"] == "c" * 64


# ── --list-consolidations parsing ───────────────────────────────────────

def test_parse_consolidations_filters_foreign_celex():
    xml = """
    <notice>
      <ref>02011L0083-20111122</ref>
      <ref>02011L0083-20180701</ref>
      <ref>02011L0083-20220528</ref>
      <ref>02011L0083-20260927</ref>
      <ref>01993L0013-20220528</ref>   <!-- amending act, not our CELEX -->
      <ref>02005L0029-20220528</ref>   <!-- foreign CELEX -->
    </notice>
    """
    out = fc.parse_consolidations(xml, "32011L0083", today="2026-01-01")
    assert [v["celex_downloaded"] for v in out] == [
        "02011L0083-20111122", "02011L0083-20180701",
        "02011L0083-20220528", "02011L0083-20260927"]
    assert out[2]["date"] == "2022-05-28"
    assert out[2]["in_force_by_today"] is True
    assert out[3]["in_force_by_today"] is False     # 2026-09-27 > today


def test_parse_consolidations_empty_when_absent():
    assert fc.parse_consolidations("<notice/>", "32018R0302") == []


# ── EU fetch: gate / unchanged / manifest (offline, _http_get patched) ──

def _root(tmp_path: Path) -> Path:
    (tmp_path / "ingest" / "eu").mkdir(parents=True)
    (tmp_path / "raw" / "eu").mkdir(parents=True)
    return tmp_path


def test_fetch_eu_gate_failure_never_overwrites(tmp_path, monkeypatch):
    root = _root(tmp_path)
    existing = root / "ingest" / "eu" / "32018R0302.html"
    existing.write_bytes(b"<html>ORIGINAL</html>")
    manifest_path = root / "ingest" / "eu" / "MANIFEST.json"
    manifest_path.write_text(json.dumps([manifest_entry(celex_base="32018R0302",
                                                         celex_downloaded="32018R0302")]),
                             encoding="utf-8")
    before = manifest_path.read_bytes()

    # RDF dump + too short → content gate rejects.
    monkeypatch.setattr(fc, "_http_get",
                        lambda url, headers, **kw: b"<rdf:RDF>ontology</rdf:RDF>")
    monkeypatch.setattr(fc, "_nap", lambda: None)

    act = {"id": "EU:REG:2018:302", "fetch": {"method": "cellar", "celex": "32018R0302"}}
    res = fc.fetch_eu_act(act, root=root)

    assert res["status"] == "failed"
    assert "content gate" in res["error"]
    assert existing.read_bytes() == b"<html>ORIGINAL</html>"   # untouched
    assert not (root / "raw" / "eu" / "32018R0302.html").exists()
    assert manifest_path.read_bytes() == before                # untouched


def test_fetch_eu_unchanged_when_sha_matches(tmp_path, monkeypatch):
    root = _root(tmp_path)
    ingest_file = root / "ingest" / "eu" / "32018R0302.html"
    ingest_file.write_text(EU_HTML, encoding="utf-8")
    manifest_path = root / "ingest" / "eu" / "MANIFEST.json"
    sha = hashlib.sha256(EU_HTML.encode("utf-8")).hexdigest()
    manifest_path.write_text(json.dumps(
        [manifest_entry(celex_base="32018R0302", celex_downloaded="32018R0302",
                        sha256=sha)]), encoding="utf-8")
    before = manifest_path.read_bytes()

    monkeypatch.setattr(fc, "_http_get", lambda url, headers, **kw: EU_HTML.encode())
    monkeypatch.setattr(fc, "_nap", lambda: None)

    act = {"id": "EU:REG:2018:302", "fetch": {"method": "cellar", "celex": "32018R0302"}}
    res = fc.fetch_eu_act(act, root=root)

    assert res["status"] == "unchanged"
    assert res["sha256"] == sha
    assert res["path"] == "ingest/eu/32018R0302.html"
    assert manifest_path.read_bytes() == before                # not rewritten


def test_fetch_eu_writes_both_copies_and_upserts_manifest(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(fc, "_http_get", lambda url, headers, **kw: EU_HTML.encode())
    monkeypatch.setattr(fc, "_nap", lambda: None)

    act = {"id": "EU:REG:2018:302", "fetch": {"method": "cellar", "celex": "32018R0302"}}
    res = fc.fetch_eu_act(act, root=root)

    assert res["status"] == "fetched"
    data = EU_HTML.encode("utf-8")
    assert (root / "ingest" / "eu" / "32018R0302.html").read_bytes() == data
    assert (root / "raw" / "eu" / "32018R0302.html").read_bytes() == data
    manifest = json.loads((root / "ingest" / "eu" / "MANIFEST.json").read_text())
    assert len(manifest) == 1
    entry = manifest[0]
    assert set(entry) == set(fc.MANIFEST_KEYS)
    assert entry["celex_base"] == "32018R0302"
    assert entry["celex_downloaded"] == "32018R0302"
    assert entry["is_consolidated"] is False
    assert entry["sha256"] == hashlib.sha256(data).hexdigest()
    assert entry["articole_gasite"] >= 1
    # second run with the same bytes → unchanged + no duplicate manifest entry
    res2 = fc.fetch_eu_act(act, root=root)
    assert res2["status"] == "unchanged"
    assert len(json.loads((root / "ingest" / "eu" / "MANIFEST.json").read_text())) == 1


def test_fetch_eu_pinned_consolidated_path(tmp_path, monkeypatch):
    root = _root(tmp_path)
    monkeypatch.setattr(fc, "_http_get", lambda url, headers, **kw: EU_HTML.encode())
    monkeypatch.setattr(fc, "_nap", lambda: None)

    act = {"id": "EU:DIR:2011:83",
           "fetch": {"method": "cellar", "celex": "32011L0083",
                     "consolidated": "02011L0083-20250901"}}
    res = fc.fetch_eu_act(act, root=root)
    assert res["status"] == "fetched"
    assert res["path"] == "ingest/eu/02011L0083-20250901.html"
    entry = json.loads((root / "ingest" / "eu" / "MANIFEST.json").read_text())[0]
    assert entry["celex_base"] == "32011L0083"
    assert entry["celex_downloaded"] == "02011L0083-20250901"
    assert entry["is_consolidated"] is True


# ── RO fetch (offline: get_token/search/_http_get patched) ──────────────

def _patch_soap(monkeypatch, pages):
    calls = {"search": 0}

    def fake_get_token():
        return "token"

    def fake_search(token, year, number, *, page=1, page_size=10):
        calls["search"] += 1
        return pages.get(page, [])

    monkeypatch.setattr(fc.fetch_ro, "get_token", fake_get_token)
    monkeypatch.setattr(fc.fetch_ro, "search", fake_search)
    monkeypatch.setattr(fc, "_nap", lambda: None)
    return calls


def test_fetch_ro_unchanged_with_metadata(tmp_path, monkeypatch):
    root = tmp_path
    raw = root / "raw" / "ro"
    raw.mkdir(parents=True)
    (raw / "LEGE_506_2004.html").write_text(RO_HTML, encoding="utf-8")
    _patch_soap(monkeypatch, {1: [ro_row()]})
    monkeypatch.setattr(fc, "_http_get", lambda url, headers, **kw: RO_HTML.encode())

    act = {"id": "RO:LEGE:506:2004",
           "fetch": {"method": "soap", "tip": "LEGE", "numar": 506, "an": 2004}}
    res = fc.fetch_ro_act(act, root=root)

    assert res["status"] == "unchanged"
    assert res["path"] == "raw/ro/LEGE_506_2004.html"
    assert res["source_url"] == "https://legislatie.just.ro/Public/DetaliiDocument/56973"
    assert res["data_vigoare"] == "28.11.2004"
    assert res["sha256"] == hashlib.sha256(RO_HTML.encode()).hexdigest()


def test_fetch_ro_unchanged_despite_print_token_nonce(tmp_path, monkeypatch):
    # Verified live: the portal embeds a per-response nonce in the
    # FormaPrintabila URL and serves CRLF/LF endings interchangeably;
    # neither must flip status to 'fetched'.
    root = tmp_path
    raw = root / "raw" / "ro"
    raw.mkdir(parents=True)
    stored = RO_HTML + 'href=/Public/FormaPrintabila/OLDTOKEN0123456789ABCDEF>'
    (raw / "LEGE_506_2004.html").write_text(stored, encoding="utf-8")
    _patch_soap(monkeypatch, {1: [ro_row()]})
    monkeypatch.setattr(
        fc, "_http_get",
        lambda url, headers, **kw:
            (RO_HTML + 'href=/Public/FormaPrintabila/NEWTOKEN9876543210FEDCBA>'
             ).replace("\n", "\r\n").encode())

    act = {"id": "RO:LEGE:506:2004",
           "fetch": {"method": "soap", "tip": "LEGE", "numar": 506, "an": 2004}}
    res = fc.fetch_ro_act(act, root=root)

    # only the nonce differs → unchanged, existing snapshot untouched
    assert res["status"] == "unchanged"
    assert (raw / "LEGE_506_2004.html").read_text(encoding="utf-8") == stored

    # legal content changed → fetched, and the written snapshot is
    # homogenized (nonce replaced by STABLE, real nonce never stored)
    monkeypatch.setattr(
        fc, "_http_get",
        lambda url, headers, **kw:
            ("Articolul 2. Modificata. " + RO_HTML
             + 'href=/Public/FormaPrintabila/NEWTOKEN9876543210FEDCBA>').encode())
    res = fc.fetch_ro_act(act, root=root)
    assert res["status"] == "fetched"
    on_disk = (raw / "LEGE_506_2004.html").read_text(encoding="utf-8")
    assert "/Public/FormaPrintabila/STABLE" in on_disk
    assert "NEWTOKEN" not in on_disk


def test_fetch_ro_paginates_and_selects_tipact(tmp_path, monkeypatch):
    root = tmp_path
    page1 = [ro_row(TipAct="HOTĂRÂRE", LinkHtml=f"h-{i}",
                    Titlu=f"Hotarare {i}") for i in range(10)]
    page2 = [ro_row(TipAct="DECRET", LinkHtml=f"d-{i}",
                    Titlu=f"Decret {i}") for i in range(10)]
    page3 = [ro_row()]  # the actual LEGE
    calls = _patch_soap(monkeypatch, {1: page1, 2: page2, 3: page3})
    seen_urls = []

    def fake_get(url, headers, **kw):
        seen_urls.append(url)
        return RO_HTML.encode()

    monkeypatch.setattr(fc, "_http_get", fake_get)

    act = {"id": "RO:LEGE:506:2004",
           "fetch": {"method": "soap", "tip": "LEGE", "numar": 506, "an": 2004}}
    res = fc.fetch_ro_act(act, root=root)

    assert res["status"] == "fetched"
    assert calls["search"] == 3                      # paginated past 20 decoys
    assert seen_urls == ["https://legislatie.just.ro/Public/DetaliiDocument/56973"]
    assert (root / "raw" / "ro" / "LEGE_506_2004.html").exists()
    # SOAP Text (original form) must NOT be stored anywhere
    stored = (root / "raw" / "ro" / "LEGE_506_2004.html").read_text(encoding="utf-8")
    assert "original published form" not in stored


def test_fetch_ro_gate_failure_keeps_existing(tmp_path, monkeypatch):
    root = tmp_path
    raw = root / "raw" / "ro"
    raw.mkdir(parents=True)
    (raw / "OG_21_1992.html").write_bytes(b"<html>ORIGINAL</html>")
    _patch_soap(monkeypatch, {1: [ro_row(TipAct="ORDONANȚĂ", Numar="21",
                                         Titlu="Ordonanta nr. 21 din 1992",
                                         LinkHtml="https://legislatie.just.ro/x",
                                         DataVigoare="27.12.1992")]})
    monkeypatch.setattr(fc, "_http_get",
                        lambda url, headers, **kw: b"<html>too short</html>")

    act = {"id": "RO:OG:21:1992",
           "fetch": {"method": "soap", "tip": "OG", "numar": 21, "an": 1992}}
    res = fc.fetch_ro_act(act, root=root)

    assert res["status"] == "failed"
    assert "content gate" in res["error"]
    assert (raw / "OG_21_1992.html").read_bytes() == b"<html>ORIGINAL</html>"


# ── planning / CLI (offline) ────────────────────────────────────────────

def test_build_plan_covers_whole_corpus():
    acts = fc.load_corpus()
    assert len(acts) == 46, "corpus.yaml should currently list 46 acts"
    plan, warnings = fc.build_plan(acts)
    assert len(plan) == 46
    assert isinstance(warnings, list)
    by_id = {e["id"]: e for e in plan}
    assert by_id["RO:LEGE:506:2004"]["path"] == "raw/ro/LEGE_506_2004.html"
    assert by_id["RO:OG:21:1992"]["path"] == "raw/ro/OG_21_1992.html"
    assert by_id["EU:REG:2018:302"]["path"] == "ingest/eu/32018R0302.html"
    # GDPR e pinat pe consolidarea oficială disponibilă (cea mai nouă <= data de astăzi).
    assert by_id["EU:REG:2016:679"]["celex_downloaded"] == "02016R0679-20160504"
    assert sum(1 for e in plan if e["jurisdiction"] == "RO") == 17
    assert sum(1 for e in plan if e["jurisdiction"] == "EU") == 29


def test_filter_acts_by_only_and_jurisdiction():
    acts = fc.load_corpus()
    sel, unknown = fc.filter_acts(acts, only="RO:LEGE:506:2004,EU:DOES:NOT:EXIST")
    assert [a["id"] for a in sel] == ["RO:LEGE:506:2004"]
    assert unknown == ["EU:DOES:NOT:EXIST"]
    sel, unknown = fc.filter_acts(acts, jurisdiction="EU")
    assert len(sel) == 29 and not unknown
    sel, unknown = fc.filter_acts(acts, jurisdiction="RO")
    assert len(sel) == 17 and not unknown


def test_main_unknown_only_id_exits_2(capsys):
    rc = fc.main(["--only", "EU:DOES:NOT:EXIST", "--dry-run"])
    assert rc == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["unknown"] == ["EU:DOES:NOT:EXIST"]


def test_main_exit_code_reflects_failures(monkeypatch):
    acts = [a for a in fc.load_corpus() if a["id"] == "RO:LEGE:506:2004"]
    monkeypatch.setattr(fc, "load_corpus", lambda: acts)
    monkeypatch.setattr(fc, "_nap", lambda: None)
    monkeypatch.setattr(fc, "fetch_act",
                        lambda act: {"id": act["id"], "status": "unchanged"})
    assert fc.main([]) == 0                              # all ok → 0
    monkeypatch.setattr(fc, "fetch_act",
                        lambda act: {"id": act["id"], "status": "failed",
                                     "error": "boom"})
    assert fc.main([]) == 1                              # any failure → non-zero


def test_cli_dry_run_lists_all_46_acts():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "fetch_corpus.py"), "--dry-run"],
        capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["dry_run"] is True
    assert data["count"] == 46
    assert len(data["acts"]) == 46
    ids = {e["id"] for e in data["acts"]}
    assert {"RO:LEGE:506:2004", "EU:REG:2018:302"} <= ids
    for e in data["acts"]:
        assert e["status"] == "planned"
        assert e["path"]
