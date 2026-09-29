"""Parser for Portal Legislativ consolidated HTML.

Reads the semantic DOM structure (S_ART / S_ALN / S_LIT / S_PCT containers)
instead of regex-scraping flat text, so paragraphs (alineate) and letters
(litere) become first-class retrieval units. The SOAP `Text` flat parser
(`parse_ro_text`) is kept for legacy callers and .txt inputs.

The parser is deliberately independent from HTTP. Fetchers save the raw
document first; this module receives only the extracted HTML text.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import canonical_citation, normalize

# Portal Legislativ CSS classes (semantic structure of the consolidated form).
CLS_ART, CLS_ART_TTL, CLS_ART_DEN, CLS_ART_BDY = "S_ART", "S_ART_TTL", "S_ART_DEN", "S_ART_BDY"
CLS_ALN, CLS_ALN_TTL, CLS_ALN_BDY = "S_ALN", "S_ALN_TTL", "S_ALN_BDY"
CLS_LIT, CLS_LIT_TTL, CLS_LIT_BDY = "S_LIT", "S_LIT_TTL", "S_LIT_BDY"
CLS_PCT, CLS_PCT_TTL, CLS_PCT_BDY = "S_PCT", "S_PCT_TTL", "S_PCT_BDY"
CLS_PAR = "S_PAR"
# Hidden helper elements that must never leak into stored text (S_LIT_SHORT /
# S_PCT_SHORT carry literal " ... "; S_NTA_* are portal "Notă ..." annotations).
SKIP_CLASSES = {CLS_ALN, CLS_LIT, CLS_PCT, "S_LIT_SHORT", "S_PCT_SHORT", "S_NTA",
                "S_NTA_TTL", "S_NTA_BDY", "S_NTA_SHORT",
                "TAG_COLLAPSED", "S_SMN", "S_SMN_PAR"}
# A unit's own text excludes nested legal units; they are rendered separately.
UNIT_CLASSES = (CLS_ALN, CLS_LIT, CLS_PCT)

ARTICLE_NUM_RE = re.compile(r"art(?:icolul)?\.?\s*([0-9]+(?:\s*\^\s*[0-9]+)?)[\s.]*", re.I)
# Pure amending acts number their own articles with roman numerals ("Articolul I",
# "Articolul II"). The negative lookahead keeps ordinary words ("Articolul curent")
# from being read as a numeral.
ROMAN_ARTICLE_NUM_RE = re.compile(
    r"art(?:icolul)?\.?\s*([IVXCDM]+(?:\s*\^\s*[IVXCDM]+)?)(?![A-Z])", re.I)
PARA_NUM_RE = re.compile(r"\(\s*([0-9]+(?:\^[0-9]+)?)\s*\)")
LETTER_RE = re.compile(r"^\(?([a-z](?:\^[0-9]+)?)\)\s*$", re.I)
POINT_RE = re.compile(r"\(\s*([ivx]+)\s*\)\s*$", re.I)
# Portal change annotations rendered as S_PAR blocks: "(la 26-04-2012, ...)",
# "Abrogat. (la ...)", "A se vedea punerea în aplicare ...", "Notă ...", footnote
# stars and dotted placeholder rules — none of them are act text.
ANNOTATION_RE = re.compile(
    r"^(?:\(\s*la\b|abrogat\b|a se vedea\b|not[ăa]\b|\*+|-{3,}|…+|\.{4,})", re.I)

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "source", "track", "wbr"}


class _Element:
    """Minimal DOM node; children are str leaves or nested _Element nodes."""
    __slots__ = ("tag", "classes", "children")

    def __init__(self, tag: str, classes: frozenset[str] = frozenset()) -> None:
        self.tag = tag
        self.classes = classes
        self.children: list[str | _Element] = []


class _DOMBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Element("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = frozenset((dict(attrs).get("class") or "").split())
        el = _Element(tag, classes)
        self.stack[-1].children.append(el)
        if tag not in VOID_TAGS:
            self.stack.append(el)

    def handle_startendtag(self, tag: str, attrs) -> None:
        classes = frozenset((dict(attrs).get("class") or "").split())
        el = _Element(tag, classes)
        self.stack[-1].children.append(el)

    def handle_endtag(self, tag: str) -> None:
        # Tolerant close: drop back to the nearest matching open tag.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].children.append(data)


def _parse_html(html: str) -> _Element:
    builder = _DOMBuilder()
    builder.feed(html)
    builder.close()
    return builder.root


def _iter(node: _Element):
    for child in node.children:
        if isinstance(child, _Element):
            yield child
            yield from _iter(child)


def _first(node: _Element, cls: str) -> _Element | None:
    for el in _iter(node):
        if cls in el.classes:
            return el
    return None


def _direct(node: _Element, cls: str) -> list[_Element]:
    return [c for c in node.children if isinstance(c, _Element) and cls in c.classes]


def _own(node: _Element, cls: str) -> _Element | None:
    """Container's own child of this class, not one inherited from a quoted
    nested block (Portal Legislativ renders S_ART_TTL/S_ART_BDY as direct
    children of S_ART; the descendant search stays as a fallback)."""
    found = _direct(node, cls)
    return found[0] if found else _first(node, cls)


def _segments(node: _Element, *, include_units: bool = False,
              flatten_units: bool = False) -> list[str]:
    """Text segments of a container, in DOM order.

    include_units=True keeps S_ALN/S_LIT/S_PCT subtrees (used only for
    annotation detection); default renders a container's own text, excluding
    nested units, which become provisions of their own.

    flatten_units=True renders units inline as text instead of dropping them:
    used for content that can never be emitted as provisions of this act, i.e.
    articles quoted from other acts and units nested under a plain S_PAR
    wrapper (the provision collector only walks direct unit children).
    Portal annotations keep being excluded in this mode.
    """
    keep_units = include_units or flatten_units
    segs: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            segs.append(child)
            continue
        is_unit = bool(child.classes & set(UNIT_CLASSES))
        if child.classes & SKIP_CLASSES and not (keep_units and is_unit):
            continue
        if CLS_ART in child.classes and not include_units:
            # An S_ART nested inside another S_ART is an article of ANOTHER act
            # quoted by a consolidated amendment instruction: it is quoted text
            # of the parent provision, never an article of the host act.
            segs.append(_text(child, flatten_units=True))
            continue
        if CLS_PAR in child.classes and not include_units:
            if _is_annotation(child):
                continue
            segs.append(_text(child, flatten_units=True))
            continue
        segs.append(_text(child, include_units=include_units,
                          flatten_units=flatten_units))
    return segs


def _text(node: _Element, *, include_units: bool = False,
          flatten_units: bool = False) -> str:
    """Normalized container text: segments joined with an explicit separator,
    so adjacent tags without whitespace in the source never glue words."""
    return normalize(" ".join(
        s for s in _segments(node, include_units=include_units,
                            flatten_units=flatten_units) if s.strip()))


def _is_annotation(el: _Element) -> bool:
    text = _text(el, include_units=True).strip()
    return bool(text) and bool(ANNOTATION_RE.match(text))


def _ttl_text(unit: _Element, ttl_cls: str) -> str:
    ttl = _first(unit, ttl_cls)
    return normalize(_text(ttl, include_units=True)) if ttl is not None else ""


def _render_body(body: _Element) -> str:
    """Aggregate legal text of a unit body, composed in document (DOM) order:
    own text, inline S_PAR blocks and child units ("a) ... (i) ...") appear
    exactly where they occur in the source, separated by explicit spaces."""
    segs: list[str] = []
    for child in body.children:
        if isinstance(child, str):
            segs.append(child)
            continue
        kind = _unit_kind(child)
        if kind is None:
            if child.classes & SKIP_CLASSES:
                continue
            if CLS_PAR in child.classes:
                if _is_annotation(child):
                    continue
                # units under a plain S_PAR wrapper are never collected as
                # provisions -> keep them as text of this provision
                segs.append(_text(child, flatten_units=True))
                continue
            if CLS_ART in child.classes:
                # quoted article of another act: keep it verbatim as text
                segs.append(_text(child, flatten_units=True))
                continue
            segs.append(_text(child))
            continue
        child_cls, child_ttl, child_body, _ = _UNIT_SPECS[kind]
        label = _ttl_text(child, child_ttl)
        child_body_el = _first(child, child_body) or child
        rendered = _render_body(child_body_el)
        segs.append(f"{label} {rendered}".strip())
    return normalize(" ".join(s for s in segs if s.strip()))


def _iter_host_articles(root: _Element, drop_log: list[dict] | None = None):
    """Yield only the act's own S_ART containers, in document order.

    Portal Legislativ writes amendment instructions inline: the consolidated
    form of an act quotes, inside the host article's alineate/puncte, the full
    text of articles belonging to OTHER acts (wrapped in S_CIT). Structurally
    such a block is an S_ART nested inside another S_ART, so it is quoted text
    of the parent provision - never an article of the host act. Nested S_ART
    subtrees are therefore not descended into (their text is already rendered
    inline by _segments/_render_body) and are reported to drop_log.
    """
    def walk(node: _Element, inside_article: bool):
        for child in node.children:
            if isinstance(child, str):
                continue
            if CLS_ART not in child.classes:
                yield from walk(child, inside_article)
                continue
            if inside_article:
                if drop_log is not None:
                    title_el = _first(child, CLS_ART_TTL)
                    title = normalize(_text(title_el, include_units=True)) if title_el else ""
                    m = ARTICLE_NUM_RE.search(title)
                    drop_log.append({
                        "article": m.group(1).replace(" ", "") if m else "",
                        "title": title,
                        "reason": "QUOTED_ARTICLE_OF_OTHER_ACT",
                    })
                continue
            yield child
            yield from walk(child, True)

    yield from walk(root, False)


def _unit_kind(el: _Element) -> int | None:
    for i, (cls, _ttl, _bdy, _kind) in enumerate(_UNIT_SPECS):
        if cls in el.classes:
            return i
    return None


_UNIT_SPECS = (
    (CLS_ALN, CLS_ALN_TTL, CLS_ALN_BDY, "paragraph"),
    (CLS_LIT, CLS_LIT_TTL, CLS_LIT_BDY, "letter"),
    (CLS_PCT, CLS_PCT_TTL, CLS_PCT_BDY, "point"),
)


_UNIT_SPECS = (
    (CLS_ALN, CLS_ALN_TTL, CLS_ALN_BDY, "paragraph"),
    (CLS_LIT, CLS_LIT_TTL, CLS_LIT_BDY, "letter"),
    (CLS_PCT, CLS_PCT_TTL, CLS_PCT_BDY, "point"),
)


def parse_ro_html(html: str, *, jurisdiction: str = "RO", act_type: str = "LEGE",
                  number: str = "0", year: int = 0,
                  drop_log: list[dict] | None = None) -> list[dict]:
    """Parse a Portal Legislativ consolidated HTML document into provisions.

    The retrieval unit is the paragraph (alineat) when the article has them;
    articles without paragraphs stay single provisions; letters (litere) and
    points (puncte) are also kept as standalone provisions with their parent
    coordinates filled in.

    Articles quoted from other acts (cross-act amendment instructions) are not
    emitted as provisions of this act; their text stays inside the parent
    provision. Pass a list as ``drop_log`` to receive the skipped blocks.

    Two document-level fallbacks keep legal text in the corpus without inventing
    retrieval units:

    * a document whose host articles are all roman-numbered (a pure amending
      act) is emitted as roman articles, one provision per article, carrying
      the amendment instruction together with the quoted text of the amended
      act. Acts with arabic numbering never gain roman articles;
    * a direct unit of an article whose label cannot be turned into a citation
      (e.g. puncte numbered "1.", "2.") is appended to the provision it belongs
      to instead of being dropped. No new provision id is created for it.
    """
    root = _parse_html(html or "")
    provisions: list[dict] = []
    seen_ids: set[str] = set()
    seen_rows: dict[str, dict] = {}
    state: dict[str, dict | None] = {"last_row": None}

    def add(*, article: str, paragraph: str | None, letter: str | None,
            point: str | None, heading: str | None, text: str) -> dict | None:
        if not text:
            return None
        cid = canonical_citation(jurisdiction, act_type, number, year,
                                 "article", article, paragraph, point, letter)
        if cid in seen_ids:  # unnumbered duplicates merge into the first occurrence
            state["last_row"] = seen_rows[cid]
            return seen_rows[cid]
        row = {
            "id": cid,
            "article": article,
            "paragraph": paragraph,
            "letter": letter,
            "point": point,
            "heading": heading,
            "provision_type": "article",
            "text": text,
            "sequence": len(provisions) + 1,
        }
        seen_ids.add(cid)
        seen_rows[cid] = row
        provisions.append(row)
        state["last_row"] = row
        return row

    def unit_fragment(unit: _Element, label: str) -> str:
        """Whole text of a unit that cannot become a provision: its label plus
        the full subtree, quoted cross-act blocks included, so no text is lost.
        """
        text = normalize(_text(unit, flatten_units=True))
        if label and not text.startswith(label):
            text = normalize(f"{label} {text}")
        return text

    def collect(body: _Element, *, article: str, heading: str | None,
                paragraph: str | None, letter: str | None, skip_kinds: tuple[str, ...],
                unparsed: list[str] | None = None) -> None:
        for child_cls, child_ttl, child_body, child_kind in _UNIT_SPECS:
            if child_kind in skip_kinds:
                continue
            for unit in _direct(body, child_cls):
                unit_body = _first(unit, child_body) or unit
                label = _ttl_text(unit, child_ttl)
                full_text = _render_body(unit_body)
                if child_kind == "paragraph":
                    m = PARA_NUM_RE.search(label)
                    child_paragraph = m.group(1) if m else paragraph
                    add(article=article, paragraph=child_paragraph, letter=letter,
                        point=None, heading=heading, text=full_text)
                    collect(unit_body, article=article, heading=heading,
                            paragraph=child_paragraph, letter=letter,
                            skip_kinds=(child_kind,))
                elif child_kind == "letter":
                    m = LETTER_RE.search(label)
                    if not m:
                        if unparsed is not None:
                            fragment = unit_fragment(unit, label)
                            if fragment:
                                unparsed.append(fragment)
                        continue
                    child_letter = m.group(1).lower()
                    add(article=article, paragraph=paragraph, letter=child_letter,
                        point=None, heading=heading, text=full_text)
                    collect(unit_body, article=article, heading=heading,
                            paragraph=paragraph, letter=child_letter,
                            skip_kinds=(child_kind,))
                else:  # point
                    m = POINT_RE.search(label)
                    if not m:
                        # Only article-body level loses text here: units nested
                        # inside an alineat or litera are already rendered inline
                        # by _render_body, so nested levels keep unparsed=None.
                        if unparsed is not None:
                            fragment = unit_fragment(unit, label)
                            if fragment:
                                unparsed.append(fragment)
                        continue
                    add(article=article, paragraph=paragraph, letter=letter,
                        point=m.group(1).lower(), heading=heading,
                        text=normalize(_text(unit_body)))

    def numeral(art_el: _Element, pattern: re.Pattern[str]) -> str:
        title_el = _own(art_el, CLS_ART_TTL)
        if title_el is None:
            return ""
        match = pattern.search(normalize(_text(title_el, include_units=True)))
        return match.group(1).replace(" ", "").upper() if match else ""

    host_articles = list(_iter_host_articles(root, drop_log))
    roman_only = not any(numeral(el, ARTICLE_NUM_RE) for el in host_articles)

    for art_el in host_articles:
        article = numeral(art_el, ARTICLE_NUM_RE)
        roman = numeral(art_el, ROMAN_ARTICLE_NUM_RE) if roman_only and not article else ""
        if not article and not roman:
            continue
        body_el = _own(art_el, CLS_ART_BDY)
        if body_el is None:
            continue
        den_el = _own(art_el, CLS_ART_DEN)
        heading_parts = []
        if den_el is not None:
            heading_parts.append(normalize(_text(den_el, include_units=True)))
        head_pars = _direct(body_el, CLS_PAR)
        if head_pars and not _is_annotation(head_pars[0]):
            heading_parts.append(normalize(_text(head_pars[0], include_units=True)))
        heading = normalize(" ".join(p for p in heading_parts if p)) or None
        state["last_row"] = None

        if roman:
            # The quoted text of the amended act IS the content of the amending
            # article: keep instruction and quote together in one provision.
            add(article=roman, paragraph=None, letter=None, point=None,
                heading=heading, text=normalize(_text(body_el, flatten_units=True)))
            continue

        if _direct(body_el, CLS_ALN) or _direct(body_el, CLS_LIT):
            unparsed: list[str] = []
            collect(body_el, article=article, heading=heading,
                    paragraph=None, letter=None, skip_kinds=(), unparsed=unparsed)
            if unparsed:
                fold = normalize(" ".join(unparsed))
                target = state["last_row"]
                if target is not None and target["article"] == article:
                    target["text"] = normalize(f"{target['text']} {fold}")
                else:
                    add(article=article, paragraph=None, letter=None, point=None,
                        heading=heading, text=fold)
        else:
            add(article=article, paragraph=None, letter=None, point=None,
                heading=heading, text=normalize(_text(body_el)))
    provisions.sort(key=lambda row: row["sequence"])  # list follows document order
    return provisions


def parse_ro_text(text: str, *, jurisdiction: str = "RO", act_type: str = "LEGE", number: str = "0", year: int = 0) -> list[dict]:
    """Legacy flat-text parser (SOAP `Text` field / .txt snapshots)."""
    # Preserve line boundaries while locating headings; collapse whitespace only
    # after each legal unit has been isolated.
    text = unicodedata.normalize("NFC", text or "").translate(str.maketrans({"Ş": "Ș", "ş": "ș", "Ţ": "Ț", "ţ": "ț"})).replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    ARTICLE_RE = re.compile(r"(?im)^\s*(?:art(?:icolul)?\.?\s*)([0-9]+(?:\^?[0-9]+)?)\s*\.?\s*(.*?)(?=^\s*(?:art(?:icolul)?\.?\s*)[0-9]+|\Z)", re.S)
    PARA_RE = re.compile(r"(?m)(?:^|\n)\s*\(([0-9]+)\)\s*(.*?)(?=(?:\n\s*\([0-9]+\)\s*)|\Z)", re.S)
    matches = list(ARTICLE_RE.finditer(text))
    provisions: list[dict] = []
    for sequence, match in enumerate(matches, start=1):
        article = match.group(1)
        body = normalize(match.group(2))
        paragraphs = list(PARA_RE.finditer(body))
        if not paragraphs:
            paragraphs = [None]
        for para in paragraphs:
            paragraph = para.group(1) if para else None
            paragraph_text = normalize(para.group(2)) if para else body
            cid = canonical_citation(jurisdiction, act_type, number, year, "article", article, paragraph)
            provisions.append({"id": cid, "article": article, "paragraph": paragraph,
                               "provision_type": "article", "citable": 1,
                               "text": paragraph_text, "sequence": sequence})
    return provisions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--act-type", default="LEGE")
    parser.add_argument("--number", default="0")
    parser.add_argument("--year", type=int, default=0)
    args = parser.parse_args()
    raw = args.path.read_text(encoding="utf-8")
    if args.path.suffix.lower() == ".html":
        dropped: list[dict] = []
        parsed = parse_ro_html(raw, act_type=args.act_type, number=args.number,
                               year=args.year, drop_log=dropped)
        if dropped:
            print(f"parse_ro: excluded {len(dropped)} quoted article block(s) "
                  f"belonging to other acts: "
                  + ", ".join(d['article'] or '?' for d in dropped), file=sys.stderr)
    else:
        parsed = parse_ro_text(raw, act_type=args.act_type, number=args.number, year=args.year)
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
