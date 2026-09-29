"""Parser for EUR-Lex consolidated / Official Journal HTML (ELI XHTML).

Reads the semantic DOM structure instead of regex-scraping flat text:
  - div.el-subdivision id="art_N" containers (new consolidations and OJ files),
  - legacy formex conversions without art_N ids (p.title-article-norm),
  - div.el-subdivision id="rct_N" recitals (OJ files; consolidated forms have none),
  - letters/points as grid-container grid-list units, modref/footnote apparatus stripped.

Article representation rule (same as parse_ro.py): an article WITH paragraphs is
represented by its paragraphs alone; an article WITHOUT paragraphs is a single
article-level provision. Orphan text inside an article but outside any numbered
paragraph is never dropped and never becomes a phantom article provision: it is
attached to the preceding paragraph, preserving document order.

The parser is deliberately independent from HTTP. Fetchers save the raw
document first; this module receives only the extracted HTML text.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jurist.engine import canonical_citation, normalize

CELEX_TYPE_MAP = {"R": "REG", "L": "DIR", "F": "DEC", "C": "DEC", "D": "DEC"}
# CELEX layout: optional leading digit, year(4), type(1), number(4):
# 32016R0679 -> REG 679 2016; 02002L0058-20091219 -> DIR 58 2002.
CELEX_RE = re.compile(r"^\d?(\d{4})([A-Z])(\d{4})")

ARTICLE_ID_RE = re.compile(r"^art_([0-9]+[a-z]?)$", re.I)
RECITAL_ID_RE = re.compile(r"^rct_([0-9]+)$", re.I)
# Annex titles: consolidated files use p.title-annex-1 (+ p.title-annex-2 as
# subtitle), OJ files use p.oj-doc-ti. Annex content is a provision of its own
# (AGENTS.md §8.3); before this marker existed it was appended to the last
# article paragraph of the act.
ANNEX_TITLE_CLASSES = {"title-annex-1", "oj-doc-ti", "stitle-annex-1"}
ANNEX_TITLE_RE = re.compile(r"^anex[ăa]\b", re.I)
ARTICLE_TITLE_RE = re.compile(r"articolul\s+([0-9]+[a-z]?)\b", re.I)
PARA_NUM_RE = re.compile(r"^\(([0-9]+)\)\s*")
LETTER_LABEL_RE = re.compile(r"^\(([a-z]{1,2}|[ivx]{1,5})\)$", re.I)
DIVISION_RE = re.compile(r"oj-ti-section-([123])")
PARA_WRAPPER_ID_RE = re.compile(r"^\d{3}\.\d{3}$")

# Modification references, footnotes and paragraph numbers never belong to the
# stored text: modref spans, note tags, superscript markers, span.no-parag.
SKIP_CLASSES = {"modref", "oj-note-tag", "superscript", "oj-super", "oj-footnote",
                "no-parag"}


def celex_to_act(celex: str) -> tuple[str, str, int]:
    """Map a CELEX (optional leading 0, optional -YYYYMMDD suffix) to (act_type, number, year).

    >>> celex_to_act("02002L0058-20091219")
    ('DIR', '58', 2002)
    >>> celex_to_act("32016R0679")
    ('REG', '679', 2016)
    """
    stem = (celex or "").split("-")[0].strip()
    m = CELEX_RE.match(stem)
    if not m:
        raise ValueError(f"unrecognized CELEX: {celex!r}")
    year, type_char, num = m.group(1), m.group(2).upper(), m.group(3)
    return CELEX_TYPE_MAP.get(type_char, type_char), str(int(num)), int(year)


class _Element:
    """Minimal DOM node; children are str leaves or nested _Element nodes."""
    __slots__ = ("tag", "classes", "id", "children")

    def __init__(self, tag: str, classes: frozenset[str] = frozenset(), eid: str = "") -> None:
        self.tag = tag
        self.classes = classes
        self.id = eid
        self.children: list[str | _Element] = []


VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "source", "track", "wbr"}


class _DOMBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = _Element("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs) -> None:
        attrs_d = dict(attrs)
        el = _Element(tag, frozenset((attrs_d.get("class") or "").split()),
                      attrs_d.get("id") or "")
        self.stack[-1].children.append(el)
        if tag not in VOID_TAGS:
            self.stack.append(el)

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
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


def _is_skipped(el: _Element) -> bool:
    return bool(el.classes & SKIP_CLASSES) or el.id.startswith(("ntc", "ntr", "src.", "fnt"))


def _segments(node: _Element) -> list[str]:
    """Text segments in DOM order; apparatus (modref, footnotes) excluded."""
    segs: list[str] = []
    for child in node.children:
        if isinstance(child, str):
            segs.append(child)
            continue
        if _is_skipped(child):
            continue
        segs.extend(_segments(child))
    return segs


def _text(node: _Element) -> str:
    """Normalized text with explicit separators; adjacent tags never glue words."""
    return normalize(" ".join(s for s in _segments(node) if s.strip()))


def _is_grid(el: _Element) -> bool:
    return "grid-container" in el.classes and "grid-list" in el.classes


def _grid_parts(grid: _Element) -> tuple[str | None, _Element | None]:
    """Label ('(a)') and body element of a grid-list letter/point unit."""
    label = None
    body = None
    for el in _iter(grid):
        if "grid-list-column-2" in el.classes:
            body = el
            break
        if label is None and el.tag == "span" and not el.classes & {"oj-note-tag"}:
            t = normalize(_text(el))
            if LETTER_LABEL_RE.match(t):
                label = t
    if body is None:
        for el in _iter(grid):
            if label is not None and el.tag == "p":
                body = el
                break
    return label, body


def _unit_no(label: str | None) -> str | None:
    if not label:
        return None
    m = LETTER_LABEL_RE.match(label)
    return m.group(1).lower() if m else None


class _Paragraph:
    """A numbered paragraph; pieces keep text and letters in document order."""
    __slots__ = ("number", "pieces")

    def __init__(self, number: str | None, own: str = "",
                 letters: list[dict] | None = None) -> None:
        self.number = number
        self.pieces: list[dict] = []
        if own:
            self.pieces.append({"text": own})
        for letter in letters or []:
            self.pieces.append({"letter": letter})


def parse_eu_html(html: str, *, jurisdiction: str = "EU", act_type: str = "REG",
                  number: str = "0", year: int = 0) -> list[dict]:
    """Parse an EUR-Lex consolidated/OJ HTML document into provisions.

    Retrieval units: the paragraph (alineat) when the article has numbered
    paragraphs; letters and nested points as standalone provisions; recitals
    only when the file actually contains them (OJ originals), citable=0.
    """
    root = _parse_html(html or "")
    provisions: list[dict] = []
    seen: set[str] = set()
    state: dict = {"chapter": None, "section": None, "article": None, "annex_no": 0}

    def add(*, article: str | None, paragraph: str | None, letter: str | None,
            point: str | None, heading: str | None, provision_type: str,
            citable: int, text: str, recital_no: str | None = None) -> None:
        if not text:
            return
        cid = canonical_citation(jurisdiction, act_type, number, year,
                                 provision_type, recital_no or article,
                                 paragraph, point, letter)
        if cid in seen:
            return
        seen.add(cid)
        provisions.append({
            "id": cid,
            "article": article,
            "paragraph": paragraph,
            "letter": letter,
            "point": point,
            "heading": heading,
            "provision_type": provision_type,
            "citable": citable,
            "chapter": state["chapter"],
            "section": state["section"],
            "text": text,
            "sequence": len(provisions) + 1,
        })

    def render_body(body: _Element) -> tuple[str, list[dict]]:
        """Own text + direct letter/point units of a body, in DOM order."""
        segs: list[str] = []
        letters: list[dict] = []
        for child in body.children:
            if isinstance(child, str):
                segs.append(child)
                continue
            if _is_skipped(child):
                continue
            if _is_grid(child):
                label, grid_body = _grid_parts(child)
                if label and grid_body is not None:
                    letters.append({"label": label, "body": grid_body})
                    continue
            segs.extend(_segments(child))
        return normalize(" ".join(s for s in segs if s.strip())), letters

    def render_letter(letter: dict) -> tuple[str, list[dict]]:
        """Full letter text (points folded inline) + standalone point units."""
        own, subgrids = render_body(letter["body"])
        pieces = [own]
        points: list[dict] = []
        for g in subgrids:
            pno = _unit_no(g["label"])
            pfull, _ = render_letter(g)
            if pno:
                points.append({"no": pno, "label": g["label"], "full": pfull})
            pieces.append(f"{g['label']} {pfull}".strip())
        return normalize(" ".join(p for p in pieces if p)), points

    def flush_article() -> None:
        art = state["article"]
        state["article"] = None
        if not art or not art["number"]:
            if art and art.get("annex"):
                chunks = [normalize(" ".join(art["own_parts"]))]
                chunks += [render_paragraph(p) for p in art["paragraphs"]]
                text = normalize(" ".join(c for c in chunks if c))
                if text:
                    add(article=art["token"], paragraph=None, letter=None, point=None,
                        heading=art["title"] or None, provision_type="annex", citable=1,
                        text=text)
            return
        article_no, heading = art["number"], art["heading"]
        paras: list[_Paragraph] = art["paragraphs"]
        if not paras:
            # Article without paragraphs: one article-level provision.
            add(article=article_no, paragraph=None, letter=None, point=None,
                heading=heading, provision_type="article", citable=1,
                text=normalize(" ".join(art["own_parts"])))
            return
        # Orphan text before the first paragraph leads the article: keep it at
        # the top of the first paragraph, preserving document order.
        if art["own_parts"]:
            paras[0].pieces.insert(0, {"text": normalize(" ".join(art["own_parts"]))})
        for para in paras:
            rendered: list[tuple[dict, str, list[dict]]] = []
            pieces_out: list[str] = []
            for piece in para.pieces:
                if "text" in piece:
                    pieces_out.append(piece["text"])
                    continue
                letter = piece["letter"]
                full, points = render_letter(letter)
                rendered.append((letter, full, points))
                pieces_out.append(f"{letter['label']} {full}".strip())
            add(article=article_no, paragraph=para.number, letter=None, point=None,
                heading=heading, provision_type="article", citable=1,
                text=normalize(" ".join(p for p in pieces_out if p)))
            for letter, full, points in rendered:
                letter_no = _unit_no(letter["label"])
                add(article=article_no, paragraph=para.number, letter=letter_no,
                    point=None, heading=heading, provision_type="article", citable=1,
                    text=full)
                for pt in points:
                    add(article=article_no, paragraph=para.number, letter=letter_no,
                        point=pt["no"], heading=heading, provision_type="article",
                        citable=1, text=pt["full"])

    def render_paragraph(para: _Paragraph) -> str:
        """Full text of one paragraph: own text plus letters in document order."""
        out: list[str] = []
        for piece in para.pieces:
            if "text" in piece:
                out.append(piece["text"])
                continue
            letter = piece["letter"]
            full, _ = render_letter(letter)
            out.append(f"{letter['label']} {full}".strip())
        return normalize(" ".join(out))

    def open_annex(title: str) -> None:
        """Start an annex accumulator: content after an annex heading belongs
        to the annex, never to the preceding article. Sequential token keeps
        annexes unique even when the source repeats a heading."""
        flush_article()
        state["annex_no"] = int(state.get("annex_no") or 0) + 1
        state["article"] = {"number": None, "heading": None,
                            "paragraphs": [], "own_parts": [], "annex": True,
                            "token": str(state["annex_no"]), "title": title}

    def open_article(number: str | None) -> None:
        flush_article()
        state["article"] = {"number": number, "heading": None,
                            "paragraphs": [], "own_parts": []}

    def attach_orphan(text: str) -> None:
        """Orphan text: previous paragraph if any, else the article's own buffer."""
        if not text or state["article"] is None:
            return
        paras: list[_Paragraph] = state["article"]["paragraphs"]
        if paras:
            paras[-1].pieces.append({"text": text})
        else:
            state["article"]["own_parts"].append(text)

    def attach_grid(label: str, body: _Element) -> None:
        """Letter unit: previous paragraph if any, else folded into the buffer."""
        if state["article"] is None:
            return
        paras: list[_Paragraph] = state["article"]["paragraphs"]
        if paras:
            paras[-1].pieces.append({"letter": {"label": label, "body": body}})
        else:
            full, _ = render_letter({"label": label, "body": body})
            state["article"]["own_parts"].append(f"{label} {full}".strip())

    def add_paragraph(number: str | None, own: str, letters: list[dict]) -> None:
        if state["article"] is None:
            return  # preamble text before any article is not indexed
        if number is None:
            # Unnumbered block: never a phantom article provision. Attach to the
            # previous paragraph (document order) or keep as article-level text.
            attach_orphan(own)
            for letter in letters:
                attach_grid(letter["label"], letter["body"])
            return
        state["article"]["paragraphs"].append(_Paragraph(number, own, letters))

    def number_from_prefix(text: str) -> tuple[str | None, str]:
        m = PARA_NUM_RE.match(text)
        if m:
            return m.group(1), normalize(text[m.end():])
        return None, text

    def render_table_rows(table: _Element) -> list[str]:
        """Numbered items laid out as OJ tables ("1." + text) folded into lines.

        EUR-Lex renders definitions and numbered lists of older OJ files as
        two-column tables, which the DOM walk used to skip entirely: the text
        was silently lost. A row is never a provision of its own (it has no
        reliable article/paragraph coordinates of its own), so it is folded
        into the surrounding text in document order.
        """
        lines: list[str] = []
        for node in _iter(table):
            if node.tag != "tr":
                continue
            cells = [_text(c) for c in node.children
                     if isinstance(c, _Element) and c.tag in ("td", "th")]
            line = normalize(" ".join(p for p in cells if p))
            if line:
                lines.append(line)
        return lines

    def attach_table(el: _Element) -> None:
        for line in render_table_rows(el):
            attach_orphan(line)

    def process_article_container(el: _Element) -> None:
        """Families A/B: article content lives inside a div id="art_N"."""
        m = ARTICLE_ID_RE.match(el.id or "")
        open_article(m.group(1).lower() if m else None)
        for child in el.children:
            if isinstance(child, str):
                attach_orphan(normalize(child))
                continue
            if "eli-title" in child.classes:
                st = _first(child, "stitle-article-norm") or _first(child, "oj-sti-art")
                if st is not None and state["article"] is not None:
                    state["article"]["heading"] = _text(st) or None
                continue
            if child.tag == "p" and ("title-article-norm" in child.classes
                                     or "oj-ti-art" in child.classes):
                if state["article"] is not None and state["article"]["number"] is None:
                    tm = ARTICLE_TITLE_RE.search(_text(child))
                    if tm:
                        state["article"]["number"] = tm.group(1).lower()
                continue
            if child.tag == "div" and "norm" in child.classes:
                # Family A: div.norm > span.no-parag + body div/p
                no_parag = _first(child, "no-parag")
                body_el = next((sub for sub in child.children
                                if isinstance(sub, _Element)
                                and "no-parag" not in sub.classes and sub.tag in ("div", "p")),
                               None)
                own, letters = render_body(body_el if body_el is not None else child)
                if no_parag is not None:
                    nm = re.search(r"\(([0-9]+)\)", _text(no_parag))
                    add_paragraph(nm.group(1) if nm else None, own, letters)
                else:
                    num, own = number_from_prefix(own)
                    add_paragraph(num, own, letters)
                continue
            if child.tag == "p" and ("norm" in child.classes or "oj-normal" in child.classes):
                own, letters = render_body(child)
                num, own = number_from_prefix(own)
                add_paragraph(num, own, letters)
                continue
            if child.tag == "div" and PARA_WRAPPER_ID_RE.match(child.id or ""):
                own, letters = render_body(child)
                num, own = number_from_prefix(own)
                add_paragraph(num, own, letters)
                continue
            if _is_grid(child):
                label, grid_body = _grid_parts(child)
                if label and grid_body is not None:
                    attach_grid(label, grid_body)
                else:
                    # Numbered/plain lists ("1. ...") have no letter label: keep
                    # their text instead of dropping the unit.
                    attach_orphan(_text(child))
                continue
            if child.tag == "table":
                attach_table(child)
                continue
            if child.tag == "div" and not (child.classes & SKIP_CLASSES):
                _walk_generic(child)

    def _walk_generic(el: _Element) -> None:
        """Generic content walk: family-C paragraphs, headings, sibling grids."""
        for child in el.children:
            if isinstance(child, str):
                attach_orphan(normalize(child))
                continue
            if _is_skipped(child):
                continue
            if "eli-title" in child.classes:
                st = _first(child, "stitle-article-norm") or _first(child, "oj-sti-art")
                if st is not None and state["article"] is not None and not state["article"]["heading"]:
                    state["article"]["heading"] = _text(st) or None
                continue
            if child.tag == "p" and "stitle-article-norm" in child.classes:
                if state["article"] is not None and not state["article"]["heading"]:
                    state["article"]["heading"] = _text(child) or None
                continue
            if child.tag == "p" and (child.classes & ANNEX_TITLE_CLASSES) \
                    and ANNEX_TITLE_RE.match(_text(child)):
                open_annex(_text(child))
                continue
            if child.tag == "p" and ("norm" in child.classes or "oj-normal" in child.classes):
                own, letters = render_body(child)
                num, own = number_from_prefix(own)
                add_paragraph(num, own, letters)
                continue
            if _is_grid(child):
                label, grid_body = _grid_parts(child)
                if label and grid_body is not None:
                    attach_grid(label, grid_body)
                else:
                    attach_orphan(_text(child))
                continue
            if child.tag == "table":
                attach_table(child)
                continue
            if child.tag == "div" and not (child.classes & SKIP_CLASSES):
                _walk_generic(child)

    def set_division(level: str, title: str) -> None:
        if level == "1":
            state["chapter"], state["section"] = title or None, None
        else:
            state["section"] = title or None

    def walk(node: _Element) -> None:
        for child in node.children:
            if isinstance(child, str):
                continue
            if _is_skipped(child):
                continue
            cid = child.id or ""
            if ARTICLE_ID_RE.match(cid) and child.tag == "div":
                process_article_container(child)
                continue
            rm = RECITAL_ID_RE.match(cid)
            if rm:
                num, text = number_from_prefix(_text(child))
                add(article=None, paragraph=None, letter=None, point=None,
                    heading=None, provision_type="recital", citable=0, text=text,
                    recital_no=rm.group(1))
                continue
            if child.tag == "p" and (child.classes & ANNEX_TITLE_CLASSES) \
                    and ANNEX_TITLE_RE.match(_text(child)):
                open_annex(_text(child))
                continue
            if child.tag == "p":
                dm = DIVISION_RE.search(" ".join(child.classes))
                if dm:
                    set_division(dm.group(1), _text(child))
                    continue
                if "title-article-norm" in child.classes:
                    tm = ARTICLE_TITLE_RE.search(_text(child))
                    open_article(tm.group(1).lower() if tm else None)
                    continue
                if "stitle-article-norm" in child.classes:
                    if state["article"] is not None and not state["article"]["heading"]:
                        state["article"]["heading"] = _text(child) or None
                    continue
                if "norm" in child.classes or "oj-normal" in child.classes:
                    own, letters = render_body(child)
                    num, own = number_from_prefix(own)
                    add_paragraph(num, own, letters)
                    continue
            if child.tag == "table":
                attach_table(child)
                continue
            if "title-division-1" in child.classes:
                set_division("1", _text(child))
                continue
            if "title-division-2" in child.classes:
                set_division("2", _text(child))
                continue
            if "eli-title" in child.classes:
                inner = next((p for p in _iter(child)
                              if p.tag == "p" and DIVISION_RE.search(" ".join(p.classes))), None)
                if inner is not None:
                    set_division(DIVISION_RE.search(" ".join(inner.classes)).group(1),
                                 _text(inner))
                    continue
                if state["article"] is not None and not state["article"]["heading"]:
                    st = _first(child, "stitle-article-norm")
                    if st is not None:
                        state["article"]["heading"] = _text(st) or None
                continue
            if _is_grid(child):
                label, grid_body = _grid_parts(child)
                if label and grid_body is not None:
                    attach_grid(label, grid_body)
                else:
                    attach_orphan(_text(child))
                continue
            walk(child)

    walk(root)
    flush_article()
    provisions.sort(key=lambda row: row["sequence"])
    return provisions


def parse_eu_text(source: str, *, act_type: str = "REG", number: str = "0", year: int = 0) -> list[dict]:
    """Legacy flat-text parser kept for non-HTML fixtures."""
    import html as _html
    text = normalize(_html.unescape(re.sub(r"<[^>]+>", " ", source)))
    article_re = re.compile(r"(?i)(?:^|\s)Articolul\s+([0-9]+[a-z]?)\s*(.*?)(?=\sArticolul\s+[0-9]+|\Z)")
    output: list[dict] = []
    for sequence, match in enumerate(article_re.finditer(text), start=1):
        art = match.group(1).lower()
        cid = canonical_citation("EU", act_type, number, year, "article", art)
        output.append({"id": cid, "article": art, "paragraph": None, "letter": None,
                       "provision_type": "article", "citable": 1,
                       "text": normalize(match.group(2)), "sequence": sequence})
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--act-type", default=None)
    parser.add_argument("--number", default=None)
    parser.add_argument("--year", type=int, default=None)
    args = parser.parse_args()
    act_type, number, year = args.act_type, args.number, args.year
    if act_type is None or number is None or year is None:
        try:
            d_type, d_num, d_year = celex_to_act(args.path.stem)
        except ValueError:
            d_type, d_num, d_year = "REG", "0", 0
        act_type = act_type or d_type
        number = number or d_num
        year = year if year is not None else d_year
    raw = args.path.read_text(encoding="utf-8")
    if args.path.suffix.lower() == ".html":
        parsed = parse_eu_html(raw, act_type=act_type, number=number, year=year)
    else:
        parsed = parse_eu_text(raw, act_type=act_type, number=number, year=year)
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
