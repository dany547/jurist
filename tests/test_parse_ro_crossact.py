"""Cross-act amendment quotes must never become articles of the host act.

Portal Legislativ embeds, inside the consolidated HTML of an act, the full text
of articles it modifies in OTHER acts ("La articolul 185 din Legea nr. 31/1990
... se modifică: Articolul 185 ..."). Structurally those blocks are an S_ART
nested inside another S_ART (wrapped in S_CIT). They used to be emitted as
articles of the host act (stray RO:LEGE:214:2024:ART:185, ART:154^1,
RO:LEGE:209:2019:ART:404^1). The parser now excludes them by DOM position and
keeps their text inside the parent provision. Two fallbacks covered here keep
legal text in the corpus without inventing retrieval units: roman-numbered
articles for pure amending acts, and numeric-label puncte folded into the
provision they belong to.
"""
from pathlib import Path

import pytest

from scripts import parse_ro as P
from scripts.parse_ro import parse_ro_html

ROOT = Path(__file__).resolve().parents[1]
RAW_RO = ROOT / "raw" / "ro"


def _host_article_numbers(html: str) -> list[str]:
    """Article numbers of S_ART containers that are NOT nested in another S_ART.

    Arabic numbers always count; roman numbers count only for a document that
    has no arabic-numbered article at all (a pure amending act). Deliberately an
    independent DOM walk, so the assertion does not trust the parser's own
    notion of "host article".
    """
    arabic: list[str] = []
    roman: list[str] = []

    def walk(node, inside_article: bool) -> None:
        for child in node.children:
            if isinstance(child, str):
                continue
            if P.CLS_ART in child.classes:
                title = P._own(child, P.CLS_ART_TTL)
                text = P.normalize(P._text(title, include_units=True)) if title else ""
                if not inside_article:
                    match = P.ARTICLE_NUM_RE.search(text)
                    if match:
                        arabic.append(match.group(1).replace(" ", ""))
                    else:
                        roman_match = P.ROMAN_ARTICLE_NUM_RE.search(text)
                        if roman_match:
                            roman.append(roman_match.group(1).upper())
                walk(child, True)
            else:
                walk(child, inside_article)

    walk(P._parse_html(html), False)
    return arabic or roman


# --- the two real snapshots that used to leak strays -------------------------

def test_lege_214_2024_emits_only_host_numbering():
    html = (RAW_RO / "LEGE_214_2024.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="LEGE", number="214", year=2024)
    articles = {row["article"] for row in provisions}
    assert articles == {str(n) for n in range(1, 37)}
    ids = {row["id"] for row in provisions}
    assert "RO:LEGE:214:2024:ART:185" not in ids
    assert "RO:LEGE:214:2024:ART:154^1" not in ids
    assert not any(cid.endswith(":ART:185") or ":ART:154^1" in cid for cid in ids)


def test_lege_214_2024_quoted_text_stays_inside_host_article_36():
    html = (RAW_RO / "LEGE_214_2024.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="LEGE", number="214", year=2024)
    article_36 = " ".join(row["text"] for row in provisions if row["article"] == "36")
    # quoted article of Legea societăților nr. 31/1990 (host has no art. 185)
    assert "(1) În condițiile prevăzute de Legea contabilității nr. 82/1991" in article_36
    # quoted article 154^1 (also from another act)
    assert "(1) Comunicarea hotărârilor judecătorești se va face, din oficiu" in article_36


def test_lege_209_2019_emits_only_host_numbering():
    html = (RAW_RO / "LEGE_209_2019.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="LEGE", number="209", year=2019)
    articles = {row["article"] for row in provisions}
    assert articles == {str(n) for n in range(1, 250)}
    assert not any("^" in row["article"] for row in provisions)  # host has no ^n article
    assert not any(row["id"].endswith(":ART:404^1") for row in provisions)


def test_lege_209_2019_quoted_text_stays_inside_host_article_247():
    html = (RAW_RO / "LEGE_209_2019.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="LEGE", number="209", year=2019)
    article_247 = " ".join(row["text"] for row in provisions if row["article"] == "247")
    # quoted art. 404^1 of OUG 99/2006 must survive as text of the host article
    assert "Sistemele de plăți trebuie să asigure accesul neîngrădit la sistem" in article_247


def test_drop_log_reports_excluded_quoted_articles():
    html = (RAW_RO / "LEGE_214_2024.html").read_text(encoding="utf-8")
    dropped: list[dict] = []
    provisions = parse_ro_html(html, act_type="LEGE", number="214", year=2024, drop_log=dropped)
    excluded = {row["article"] for row in dropped}
    assert {"185", "154^1"} <= excluded
    assert all(row["reason"] == "QUOTED_ARTICLE_OF_OTHER_ACT" for row in dropped)
    emitted = {row["article"] for row in provisions}
    # numbers outside the host range can only come from quoted blocks
    assert emitted.isdisjoint(n for n in excluded if int(n.split("^")[0]) > 36)


# --- the structural rule, shown on a minimal document ------------------------

QUOTED_HTML = """
<html><body><div class="content_form">
  <span class="S_CAP"><span class="S_CAP_BDY">
    <span class="S_ART"><span class="S_ART_TTL">Articolul 1</span>
      <span class="S_ART_BDY">
        <span class="S_ALN"><span class="S_ALN_TTL">(1)</span>
          <span class="S_ALN_BDY">Prezenta lege se modifică astfel:</span></span>
        <span class="S_ALN"><span class="S_ALN_TTL">(2)</span>
          <span class="S_ALN_BDY">La articolul 12 din Legea nr. 8/1996 se modifică:
            <span class="S_CIT"><span class="S_ART">
              <span class="S_ART_TTL">Articolul 12</span>
              <span class="S_ART_DEN">Dreptul de autor</span>
              <span class="S_ART_BDY"><span class="S_ALN"><span class="S_ALN_TTL">(1)</span>
                <span class="S_ALN_BDY">TEXTUL CITAT DIN ALTĂ LEGE este protejat.</span></span>
              </span></span></span>
          </span></span>
      </span>
    </span>
    <span class="S_ART"><span class="S_ART_TTL">Articolul 2</span>
      <span class="S_ART_BDY"><span class="S_PAR">Prezenta lege se abrogă.</span></span></span>
  </span></span>
</div></body></html>
"""


def test_nested_quoted_article_is_text_not_provision():
    provisions = parse_ro_html(QUOTED_HTML, act_type="LEGE", number="999", year=2024)
    assert {row["article"] for row in provisions} == {"1", "2"}
    assert not any("ART:12" in row["id"] for row in provisions)
    host = " ".join(row["text"] for row in provisions if row["article"] == "1")
    assert "TEXTUL CITAT DIN ALTĂ LEGE este protejat." in host
    assert "Dreptul de autor" in host  # quoted heading survives too


@pytest.mark.parametrize("path", sorted(RAW_RO.glob("*.html")), ids=lambda p: p.name)
def test_no_snapshot_emits_an_article_that_is_not_top_level(path):
    """Whole-corpus invariant: every emitted article id is a host article."""
    html = path.read_text(encoding="utf-8")
    act_type, number, year = path.stem.rsplit("_", 2)
    provisions = parse_ro_html(html, act_type=act_type, number=number, year=int(year))
    emitted = {row["article"] for row in provisions}
    allowed = set(_host_article_numbers(html))
    assert emitted <= allowed, (
        f"{path.name}: {sorted(emitted - allowed)} "
        "are quoted articles of other acts, not host articles"
    )


# --- gap 1: pure amending acts number their own articles in roman numerals ----


@pytest.mark.parametrize("path", sorted(RAW_RO.glob("*.html")), ids=lambda p: p.name)
def test_roman_articles_only_appear_in_documents_without_arabic_numbering(path):
    html = path.read_text(encoding="utf-8")
    act_type, number, year = path.stem.rsplit("_", 2)
    provisions = parse_ro_html(html, act_type=act_type, number=number, year=int(year))
    articles = {row["article"] for row in provisions}
    has_arabic = any(a[0].isdigit() for a in articles)
    if has_arabic:
        assert all(a[0].isdigit() for a in articles), path.name
    elif articles:
        assert all(a.isalpha() and a.upper() == a for a in articles), path.name


def test_oug_58_2022_is_a_pure_amending_act_with_roman_host_articles():
    html = (RAW_RO / "OUG_58_2022.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="OUG", number="58", year=2022)
    articles = [row["article"] for row in provisions]
    assert articles == ["I", "II", "III", "IV", "V", "VI"]
    assert {row["id"] for row in provisions} == {
        f"RO:OUG:58:2022:ART:{n}" for n in ["I", "II", "III", "IV", "V", "VI"]
    }
    # articles of the amended acts stay quoted content, never ids of this act
    assert not any(row["id"].startswith("RO:OUG:58:2022:ART:1") and row["article"].isdigit()
                   for row in provisions)


def test_oug_58_2022_roman_article_keeps_instruction_and_quoted_text_together():
    html = (RAW_RO / "OUG_58_2022.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="OUG", number="58", year=2022)
    rows = {row["article"]: row["text"] for row in provisions}
    assert "Legea nr. 193/2000 privind clauzele abuzive" in rows["I"]      # instruction
    assert "Articolul 12" in rows["I"]                                     # quoted act
    assert len(rows["I"]) > 5_000 and len(rows["III"]) > 20_000
    assert any("contract la distanță" in text for text in rows.values())


def test_lege_363_2007_keeps_its_roman_amendment_blocks_out_of_the_article_ids():
    """An act with arabic numbering must not gain roman articles from annexes."""
    html = (RAW_RO / "LEGE_363_2007.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="LEGE", number="363", year=2007)
    articles = {row["article"] for row in provisions}
    assert articles == {"1", "2", "3", "4", "5", "6", "6^1", "7", "8", "9", "10",
                        "11", "12", "12^1", "13", "13^1", "14", "15", "15^1",
                        "15^2", "15^3", "15^4", "15^5", "16", "17"}


# --- gap 2: puncte labelled "1.", "2." ... keep their text in the parent ------


def test_oug_34_2014_article_29_keeps_its_numeric_points_without_new_ids():
    html = (RAW_RO / "OUG_34_2014.html").read_text(encoding="utf-8")
    provisions = parse_ro_html(html, act_type="OUG", number="34", year=2014)
    article_29 = [row for row in provisions if row["article"] == "29"]
    # no new provision ids were invented for the numeric points
    assert [row["id"] for row in article_29] == [
        "RO:OUG:34:2014:ART:29:P:1", "RO:OUG:34:2014:ART:29:P:2",
        "RO:OUG:34:2014:ART:29:P:3", "RO:OUG:34:2014:ART:29:P:4",
    ]
    assert not any(":POINT:" in row["id"] for row in article_29)
    text = " ".join(row["text"] for row in article_29)
    # first point and last point of the amendment list, labels preserved, in order
    first = text.index("1. La articolul 4 alineatul (1), punctul 46 se modifică")
    last = text.index("18. La articolul 142, după punctul 24 se introduc")
    assert first < last
    assert len(text) > 27_000
    # quoted lists inside the points are not lost either
    assert "24^18" in text and "nerespectarea prevederilor art. 59^8" in text
