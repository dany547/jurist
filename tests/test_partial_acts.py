"""Partially ingested acts: Codul civil (art. 1164-1762, 2500-2544) and Legea 31/1990 art. 74.

Covers the three mechanisms they needed: article numbers past 999 written with a
thousands dot, the corpus.yaml `ingest_articles` filter and the Portal Legislativ
shell page that loads large acts lazily from another document id.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.ingest_corpus import _filter_articles  # noqa: E402
from scripts import parse_ro as P  # noqa: E402
import fetch_corpus as fc  # noqa: E402

CIVIL_CODE = ROOT / "raw" / "ro" / "LEGE_287_2009.html"
REAL_DB = ROOT / "data" / "legal.db"


@pytest.mark.parametrize("title, expected", [
    ("Articolul 1.164", "1164"),
    ("Articolul 1.203^1", "1203^1"),
    ("Articolul 74", "74"),
    ("Art. 5.", "5"),
])
def test_article_number_strips_thousands_dot(title, expected):
    match = P.ARTICLE_NUM_RE.search(title)
    assert match.group(1).replace(" ", "").replace(".", "") == expected


def test_filter_articles_keeps_ranges_and_superscripts():
    rows = [{"article": a} for a in ["1163", "1164", "1203^1", "1762", "1763", "2517", None]]
    kept = [r["article"] for r in _filter_articles(rows, ["1164-1762", "2517"])]
    assert kept == ["1164", "1203^1", "1762", "2517"]
    assert _filter_articles(rows, None) == rows


def test_lazy_consolidation_link_is_followed_to_the_detail_page():
    shell = '<a href="~/../../../Public/DetaliiDocumentAfis/309285">Forma printabilă</a>'
    assert fc._lazy_consolidation_link(shell) == "https://legislatie.just.ro/Public/DetaliiDocument/309285"
    assert fc._lazy_consolidation_link("<p>fără link</p>") is None


@pytest.mark.skipif(not CIVIL_CODE.exists(), reason="raw/ro/LEGE_287_2009.html lipsește")
def test_civil_code_parses_past_article_999_without_collisions():
    rows = P.parse_ro_html(CIVIL_CODE.read_text(encoding="utf-8"), act_type="LEGE", number="287", year=2009)
    articles = {r["article"] for r in rows}
    assert {"1164", "1203", "1707", "2517"} <= articles
    assert len(rows) == len({r["id"] for r in rows}), "ID-uri duplicate"


@pytest.mark.skipif(not REAL_DB.exists(), reason="data/legal.db lipsește")
def test_partial_acts_in_db_respect_ingest_articles(monkeypatch):
    monkeypatch.setenv("JURIST_SESSION", "test")
    from jurist import JuristEngine
    e = JuristEngine(REAL_DB)
    try:
        cc = {r[0] for r in e.conn.execute("SELECT DISTINCT article FROM provisions WHERE act_id='RO:LEGE:287:2009'")}
        bases = {int(a.split("^")[0]) for a in cc}
        assert all(1164 <= b <= 1762 or 2500 <= b <= 2544 for b in bases)
        assert {1164, 1762, 2500, 2544} <= bases
        l31 = {r[0] for r in e.conn.execute("SELECT DISTINCT article FROM provisions WHERE act_id='RO:LEGE:31:1990'")}
        assert l31 == {"74"}
        website = e.get_provision(act="Legea 31/1990", article="74", paragraph="5")
        assert website["ok"] and "pagina de internet" in website["provision"]["text"]
    finally:
        e.conn.execute("DELETE FROM retrieval_log WHERE session_id='test'")
        e.conn.commit()
        e.close()
