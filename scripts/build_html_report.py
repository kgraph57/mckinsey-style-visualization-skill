#!/usr/bin/env python3
"""Build a self-contained consulting-style HTML report from Markdown.

Converts a Markdown document (with an optional front-matter block) into a
single self-contained HTML file: a navy title band, an auto-numbered table
of contents, and body copy set in the same type system as
scripts/render_slide_spec.py (references/style-system.md). Any existing
slide spec or rendered SVG can be dropped in as a numbered exhibit.

Front matter (optional; must be the first lines of the file):

    ---
    title: FY26 growth review
    subtitle: Pre-read for the March board meeting
    author: Strategy Office
    date: March 2026
    classification: Confidential - illustrative
    lang: en
    ---

Recognized keys: title, subtitle, author, date, classification, lang.
Unrecognized keys are read but ignored (never an error). A first line other
than a bare `---`, or a `---` fence that never closes, means "no front
matter" -- the whole input is read as the document body instead of raising.

Markdown subset (an intentionally small, own stdlib parser -- not
CommonMark). Anything outside this subset passes through as escaped plain
text; the parser never raises on unrecognized syntax, only on a bad exhibit
reference (see below):

    ## Heading        -> auto-numbered h2 ("1. Heading"), becomes a TOC entry
    ### Heading       -> unnumbered h3 (weight 600)
    plain lines       -> <p>, consecutive lines join with a single space
    - item            -> <ul><li>; one nested level via a `  - ` indent
    1. item           -> <ol><li> (the literal numbers are cosmetic, as in
                         CommonMark; the first item's number becomes the
                         list's `start` attribute)
    **bold**, *italic*, `code`, [text](url)   -> inline formatting (bold and
                         italic do not nest inside each other -- keep them in
                         separate spans, e.g. "**bold** and *italic*", not
                         "**bold *and* italic**")
    > quoted text     -> <blockquote>
    ---               -> <hr> (a line of three or more hyphens, alone)
    GFM tables        -> | a | b | / | --- | --- | / | 1 | 2 |, with column
                         alignment via `:---`, `:---:`, `---:`
    (h1 is not part of the subset -- it is reserved for the title-block
    heading built from front matter `title`.)

Escaping order: every line is passed through the shared `esc()` (HTML entity
escaping for &, <, >, ") before any markdown syntax is recognized. None of
`# - . > | * `` [ ] ( )` -- the characters this subset's syntax is built
from -- are touched by that escaping, so detecting syntax on the escaped
string is equivalent to detecting it on the raw string, while user text can
never reopen an HTML tag. A source line like `<script>alert(1)</script>`
therefore always renders as inert text, never as a tag.

Exhibits are the one exception to "escape, then look for syntax": a
paragraph that consists solely of

    ![Caption](spec:relative/path.json)

is recognized on its *raw* text (a file path must not be HTML-entity
decoded), and renders that slide spec with render_slide_spec.render() -- the
full 1280x720 slide, header/footer chrome included, not a chart body --
inside a bordered, auto-numbered figure ("Exhibit 1 -- Caption"; the caption
itself is still escaped for display). `![Caption](svg:relative/path.svg)`
embeds an existing SVG file the same way. Both paths resolve relative to the
input Markdown file. A `spec:`/`svg:` reference whose file is missing, whose
JSON is invalid, or whose spec the renderer rejects is a hard error naming
the path (raises ReportBuildError) -- an exhibit never renders blank. Any
other `![...](...)` scheme (anything that isn't exactly `spec:` or `svg:`)
is not part of this subset at all, so it falls through to the general
escaped-text rule like any other unrecognized syntax, rather than erroring.

The embedded SVG's `xmlns` attribute is stripped on the way in: it is
required for a standalone .svg file to be valid XML, but redundant (and,
for this skill's zero-external-request goal, a spurious "http://" string)
once the same markup is inlined inside an HTML5 document, where the SVG
namespace is assigned implicitly.

Output is a single self-contained HTML file: zero external requests, no
required JavaScript (a small inline script for TOC scroll-highlighting is
included but is decorative only). Screen layout is a 900px column; print
layout is A4 portrait with the title band as a full navy first page.
`--lang ja` sets `<html lang="ja">` and loosens body line-height to 1.9 for
CJK readability (Latin default: 1.6).

Usage:
    python3 scripts/build_html_report.py input.md -o report.html
    python3 scripts/build_html_report.py input.md -o report.html --lang ja
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_renderer():
    module_path = ROOT / "render_slide_spec.py"
    spec = importlib.util.spec_from_file_location("render_slide_spec", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_renderer = _load_renderer()
esc = _renderer.esc


class ReportBuildError(ValueError):
    """Raised when a report cannot be built: a missing/invalid exhibit
    reference, an exhibit spec the renderer rejects, or an unreadable
    exhibit file. Front-matter and Markdown-subset problems never raise --
    see the module docstring."""


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split a leading ``---``-fenced front-matter block from the body.

    A well-formed block is a first line that is exactly ``---``, then
    ``key: value`` lines, then a line that is exactly ``---``. Anything else
    (no front matter, or an unterminated fence) means "no front matter" --
    the whole input becomes the body, so a stray leading ``---`` line (e.g.
    a Markdown hr as the very first line) never crashes the build.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() != "---":
            continue
        front: dict[str, str] = {}
        for raw_line in lines[1:i]:
            if not raw_line.strip() or ":" not in raw_line:
                continue
            key, _, value = raw_line.partition(":")
            key = key.strip().lower()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key:
                front[key] = value
        body = "\n".join(lines[i + 1 :])
        return front, body
    return {}, text


# ---------------------------------------------------------------------------
# Inline formatting (operates on already-escaped text)
# ---------------------------------------------------------------------------

_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]*)\)")
_BOLD_RE = re.compile(r"\*\*([^*]+?)\*\*")
_ITALIC_RE = re.compile(r"\*([^*]+?)\*")


def _emphasis(text: str) -> str:
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _ITALIC_RE.sub(r"<em>\1</em>", text)
    return text


_URL_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.\-]*):")
_SAFE_SCHEMES = {"http", "https", "mailto"}


def _safe_href(url: str) -> str | None:
    """Return the href if its scheme is safe to emit, else None.

    The report is a trusted-looking executive document, so a Markdown link
    must never smuggle an executable URL (javascript:, data:, vbscript:, …)
    into the generated HTML. Allowed: http(s), mailto, and scheme-less
    fragment/relative targets. Control characters are rejected outright
    because browsers strip some of them during URL parsing, which would
    otherwise reassemble a forbidden scheme (e.g. "java\\x01script:").
    """
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in url):
        return None
    match = _URL_SCHEME_RE.match(url)
    if match:
        return url if match.group(1).lower() in _SAFE_SCHEMES else None
    # Scheme-less: allow fragments and relative paths, but reject a colon
    # anywhere before the first /, ? or # — that is how a browser would
    # find a scheme this regex did not.
    head = re.split(r"[/?#]", url, maxsplit=1)[0]
    return None if ":" in head else url


def render_inline(escaped_text: str) -> str:
    """Apply inline formatting to text that has already been HTML-escaped.

    Order matters: code spans are pulled out first so their content is inert
    to everything that follows (a `*` inside a code span must never become
    `<em>`); links are pulled out next, with bold/italic applied to the link
    label only; then bold/italic apply to what remains. Extracted spans are
    stashed behind private-use placeholders and spliced back in at the end
    so later passes can never re-match inside them.
    """
    stash: list[str] = []

    def _keep(html: str) -> str:
        token = f"{len(stash)}"
        stash.append(html)
        return token

    def _link(m: re.Match) -> str:
        label = _emphasis(m.group(1))
        href = _safe_href(m.group(2))
        if href is None:
            # Unsafe scheme: keep the label as plain text, drop the link.
            return _keep(label)
        return _keep(f'<a href="{href}">{label}</a>')

    text = _CODE_RE.sub(lambda m: _keep(f"<code>{m.group(1)}</code>"), escaped_text)
    text = _LINK_RE.sub(_link, text)
    text = _emphasis(text)

    for i, html in enumerate(stash):
        text = text.replace(f"{i}", html)
    return text


def inline_html(raw_text: str) -> str:
    return render_inline(esc(raw_text))


# ---------------------------------------------------------------------------
# Block parsing
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^\s{0,3}(#{2,3})\s+(.+?)\s*$")
HR_RE = re.compile(r"^-{3,}$")
UL_RE = re.compile(r"^(\s*)-\s+(.+?)\s*$")
OL_RE = re.compile(r"^(\s*)(\d+)\.\s+(.+?)\s*$")
TABLE_SEP_CELL_RE = re.compile(r"^:?-+:?$")
EXHIBIT_RE = re.compile(r"^!\[(?P<caption>[^\]]*)\]\((?P<scheme>spec|svg):(?P<path>[^)]+)\)$")


def _split_row(line: str) -> list[str]:
    """Split a GFM table row on unescaped ``|``, honoring ``\\|`` as a
    literal pipe inside a cell, and dropping a leading/trailing empty cell
    from the row's own bounding ``|`` characters."""
    s = line.strip()
    cells: list[str] = []
    current = ""
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            current += "|"
            i += 2
            continue
        if ch == "|":
            cells.append(current.strip())
            current = ""
            i += 1
            continue
        current += ch
        i += 1
    cells.append(current.strip())
    if cells and cells[0] == "":
        cells.pop(0)
    if cells and cells[-1] == "":
        cells.pop()
    return cells


def _is_table_separator(line: str) -> bool:
    if "-" not in line or "|" not in line:
        return False
    cells = _split_row(line)
    return bool(cells) and all(TABLE_SEP_CELL_RE.match(cell) for cell in cells)


def _parse_alignment(sep_line: str) -> list[str]:
    aligns = []
    for cell in _split_row(sep_line):
        left, right = cell.startswith(":"), cell.endswith(":")
        if left and right:
            aligns.append("center")
        elif right:
            aligns.append("right")
        elif left:
            aligns.append("left")
        else:
            aligns.append("")
    return aligns


def _build_list_block(list_lines: list[str]) -> tuple:
    first = list_lines[0]
    if OL_RE.match(first):
        start = None
        items: list[str] = []
        for raw in list_lines:
            match = OL_RE.match(raw)
            assert match is not None
            if start is None:
                start = int(match.group(2))
            items.append(match.group(3))
        return ("ol", start or 1, items)

    top_items: list[dict] = []
    for raw in list_lines:
        match = UL_RE.match(raw)
        assert match is not None
        indent, text = match.group(1), match.group(2)
        if not indent or not top_items:
            top_items.append({"text": text, "children": []})
        else:
            top_items[-1]["children"].append(text)
    return ("ul", top_items)


def _split_blocks(body: str) -> list[tuple]:
    lines = body.splitlines()
    blocks: list[tuple] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            blocks.append(("heading", len(heading_match.group(1)), heading_match.group(2)))
            i += 1
            continue

        if HR_RE.match(stripped):
            blocks.append(("hr",))
            i += 1
            continue

        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].strip().startswith(">"):
                content = lines[i].strip()[1:]
                if content.startswith(" "):
                    content = content[1:]
                quote_lines.append(content)
                i += 1
            blocks.append(("blockquote", quote_lines))
            continue

        if "|" in stripped and i + 1 < n and _is_table_separator(lines[i + 1]):
            header_cells = _split_row(line)
            aligns = _parse_alignment(lines[i + 1])
            i += 2
            rows = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append(_split_row(lines[i]))
                i += 1
            blocks.append(("table", header_cells, aligns, rows))
            continue

        is_ul, is_ol = bool(UL_RE.match(line)), bool(OL_RE.match(line))
        if is_ul or is_ol:
            list_lines = [line]
            i += 1
            while i < n and (UL_RE.match(lines[i]) if is_ul else OL_RE.match(lines[i])):
                list_lines.append(lines[i])
                i += 1
            blocks.append(_build_list_block(list_lines))
            continue

        para_lines: list[str] = []
        while i < n:
            current = lines[i]
            current_stripped = current.strip()
            if not current_stripped:
                break
            if (
                HEADING_RE.match(current)
                or HR_RE.match(current_stripped)
                or current_stripped.startswith(">")
                or UL_RE.match(current)
                or OL_RE.match(current)
            ):
                break
            if "|" in current_stripped and i + 1 < n and _is_table_separator(lines[i + 1]):
                break
            para_lines.append(current)
            i += 1
        blocks.append(("paragraph", para_lines))
    return blocks


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "section"


def _render_ul(items: list[dict]) -> str:
    parts = []
    for item in items:
        li = f"<li>{inline_html(item['text'])}"
        if item["children"]:
            child_lis = "".join(f"<li>{inline_html(c)}</li>" for c in item["children"])
            li += f"<ul>{child_lis}</ul>"
        li += "</li>"
        parts.append(li)
    return f"<ul>{''.join(parts)}</ul>"


_ALIGN_STYLE = {
    "left": ' style="text-align:left"',
    "center": ' style="text-align:center"',
    "right": ' style="text-align:right"',
}


def _render_table(header_cells: list[str], aligns: list[str], rows: list[list[str]]) -> str:
    def align_attr(index: int) -> str:
        if index < len(aligns) and aligns[index]:
            return _ALIGN_STYLE[aligns[index]]
        return ""

    thead = "".join(
        f"<th{align_attr(i)}>{inline_html(cell)}</th>" for i, cell in enumerate(header_cells)
    )
    body_rows = []
    for row in rows:
        cells = "".join(f"<td{align_attr(i)}>{inline_html(cell)}</td>" for i, cell in enumerate(row))
        body_rows.append(f"<tr>{cells}</tr>")
    table = f"<table><thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
    return f'<div class="table-scroll">{table}</div>'


_SVG_XMLNS_RE = re.compile(r'\s+xmlns="[^"]*"')
_XML_PROLOG_RE = re.compile(r"^\s*<\?xml[^>]*\?>\s*")


def _strip_for_inline_embed(svg: str) -> str:
    """Drop the standalone-XML furniture that inline HTML embedding does not
    need: the xml prolog (only meaningful for a document served as its own
    .svg file) and the root xmlns attribute (implicit once `<svg>` is a
    descendant of an HTML5 document -- see the module docstring)."""
    svg = _XML_PROLOG_RE.sub("", svg, count=1)
    svg = _SVG_XMLNS_RE.sub("", svg, count=1)
    return svg


def _render_exhibit(match: re.Match, number: int, base_dir: Path) -> str:
    caption_raw = match.group("caption")
    scheme = match.group("scheme")
    rel_path = match.group("path").strip()
    target = base_dir / rel_path

    if not target.is_file():
        raise ReportBuildError(f"exhibit reference not found: {rel_path}")

    if scheme == "spec":
        try:
            spec_data = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ReportBuildError(f"exhibit spec is not valid JSON: {rel_path} ({exc})") from exc
        try:
            svg = _renderer.render(spec_data)
        except Exception as exc:  # noqa: BLE001 - any render failure is a hard error naming the path
            raise ReportBuildError(f"exhibit spec failed to render: {rel_path} ({exc})") from exc
    else:  # scheme == "svg"
        svg = target.read_text(encoding="utf-8")
        if "<svg" not in svg:
            raise ReportBuildError(f"exhibit file is not an SVG: {rel_path}")

    svg = _strip_for_inline_embed(svg)
    caption_html = esc(caption_raw)
    label = f"Exhibit {number} — {caption_html}" if caption_html else f"Exhibit {number}"
    return f'<figure class="exhibit"><figcaption>{label}</figcaption>{svg}</figure>'


def render_body(blocks: list[tuple], base_dir: Path) -> tuple[str, list[tuple[int, str, str]]]:
    """Render parsed blocks to HTML.

    Returns ``(html, toc)`` where ``toc`` is ``[(number, heading_html, slug), ...]``
    for every h2, in document order, ready to build the "Contents" nav.
    """
    html_parts: list[str] = []
    toc: list[tuple[int, str, str]] = []
    used_slugs: set[str] = set()
    h2_count = 0
    exhibit_count = 0

    for block in blocks:
        kind = block[0]

        if kind == "heading":
            _, level, raw_text = block
            text_html = inline_html(raw_text)
            if level == 2:
                h2_count += 1
                base_slug = _slugify(raw_text)
                slug, suffix = base_slug, 2
                while slug in used_slugs:
                    slug = f"{base_slug}-{suffix}"
                    suffix += 1
                used_slugs.add(slug)
                html_parts.append(f'<h2 id="{esc(slug)}">{h2_count}. {text_html}</h2>')
                toc.append((h2_count, text_html, slug))
            else:
                html_parts.append(f"<h3>{text_html}</h3>")

        elif kind == "hr":
            html_parts.append("<hr>")

        elif kind == "blockquote":
            _, lines = block
            joined = " ".join(line for line in lines if line.strip())
            html_parts.append(f"<blockquote><p>{inline_html(joined)}</p></blockquote>")

        elif kind == "ul":
            _, items = block
            html_parts.append(_render_ul(items))

        elif kind == "ol":
            _, start, items = block
            start_attr = f' start="{start}"' if start != 1 else ""
            lis = "".join(f"<li>{inline_html(t)}</li>" for t in items)
            html_parts.append(f"<ol{start_attr}>{lis}</ol>")

        elif kind == "table":
            _, header_cells, aligns, rows = block
            html_parts.append(_render_table(header_cells, aligns, rows))

        elif kind == "paragraph":
            _, lines = block
            if not lines:
                continue
            if len(lines) == 1:
                exhibit_match = EXHIBIT_RE.match(lines[0].strip())
                if exhibit_match:
                    exhibit_count += 1
                    html_parts.append(_render_exhibit(exhibit_match, exhibit_count, base_dir))
                    continue
            joined = " ".join(line.strip() for line in lines)
            html_parts.append(f"<p>{inline_html(joined)}</p>")

    return "\n".join(html_parts), toc


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

STYLE = """
/* Reading layer. Mechanics follow proven long-form document practice:
   body text capped at a ~720px measure while exhibits and tables use the
   full column; section rhythm from hairlines and whitespace (no boxes,
   no left accent bars); a sticky table of contents on wide screens.
   The skin stays on the slide system's tokens (navy, Georgia, greys). */
:root {
  color-scheme: light;
  --navy: #15296B;
  --ink: #000000;
  --body-ink: #1F2937;
  --muted: #6B7280;
  --rule: #D1D5DB;
  --rule-strong: #9CA3AF;
  --tint: #F3F4F6;
  --link: #2563EB;
  --measure: 720px;
  --serif: Georgia, 'Times New Roman', 'Hiragino Mincho ProN', 'Yu Mincho', serif;
  --sans: 'Helvetica Neue', Helvetica, Arial, 'Hiragino Sans', 'Yu Gothic', 'Noto Sans JP', 'Meiryo', sans-serif;
  --mono: 'SFMono-Regular', 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { background: #FFFFFF; }
body {
  font-family: var(--sans);
  color: var(--body-ink);
  font-size: 16px;
  line-height: 1.7;
  -webkit-font-smoothing: antialiased;
  -webkit-text-size-adjust: 100%;
}
body.lang-ja { line-height: 1.9; font-feature-settings: 'palt'; }
h1, h2, h3 { color: var(--ink); }
h1, h2 { font-family: var(--serif); font-weight: bold; }

.title-band { background: var(--navy); color: #FFFFFF; }
.title-band-inner { position: relative; max-width: 1220px; margin: 0 auto; padding: 72px 32px 48px; }
.title-band h1 { font-size: 42px; font-weight: normal; color: #FFFFFF; line-height: 1.25; max-width: 780px; text-wrap: balance; }
.title-band .subtitle { margin-top: 14px; font-size: 18px; font-weight: normal; color: #E5E7EB; font-family: var(--sans); max-width: 720px; }
.title-band .meta { margin-top: 24px; font-size: 14px; color: #E5E7EB; letter-spacing: 0.02em; }
.title-band .classification {
  position: absolute; top: 36px; right: 32px; font-size: 11px; font-weight: 600;
  letter-spacing: 0.1em; color: #E5E7EB; text-transform: uppercase;
}

.doc { max-width: 820px; margin: 0 auto; padding: 56px 32px 96px; }
.doc-main { min-width: 0; }
/* Text stays on the reading measure; exhibits and tables may use the full column. */
.doc-main > p, .doc-main > ul, .doc-main > ol, .doc-main > blockquote, .doc-main > h3 { max-width: var(--measure); }

.toc { border-top: 1px solid var(--rule-strong); border-bottom: 1px solid var(--rule-strong); padding: 20px 0; margin-bottom: 56px; }
.toc .toc-label { font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
.toc ol { list-style: none; padding-left: 0; }
.toc li { margin: 4px 0; }
.toc a { color: var(--body-ink); text-decoration: none; font-size: 15px; border-bottom: none; }
.toc a:hover { color: var(--navy); }
.toc a.active { color: var(--navy); font-weight: 600; }

h2 { font-size: 25px; line-height: 1.4; margin: 72px 0 20px; padding-top: 24px; border-top: 1px solid var(--rule-strong); }
.doc-main > h2:first-child { margin-top: 0; border-top: none; padding-top: 0; }
h3 { font-family: var(--sans); font-size: 17px; font-weight: 700; line-height: 1.5; margin: 40px 0 10px; }
p { margin: 14px 0; }
strong { color: var(--ink); }

ul, ol { margin: 14px 0; padding-left: 1.6em; }
li { margin: 5px 0; }
ul ul, ol ol, ul ol, ol ul { margin: 5px 0; }
ul { list-style: none; padding-left: 1.4em; }
ul > li { position: relative; }
ul > li::before {
  content: ''; position: absolute; left: -1.15em; top: 0.62em;
  width: 6px; height: 6px; background: var(--navy);
}
ul ul > li::before { width: 5px; height: 5px; top: 0.68em; background: var(--muted); }
body.lang-ja ul > li::before { top: 0.72em; }

blockquote {
  border-top: 1px solid var(--rule-strong);
  border-bottom: 1px solid var(--rule);
  padding: 14px 0 16px;
  margin: 28px 0;
  color: var(--body-ink);
}
blockquote > :first-child { margin-top: 0; }
blockquote > :last-child { margin-bottom: 0; }

hr { border: none; border-top: 1px solid var(--rule); margin: 48px 0; }
code { font-family: var(--mono); background: var(--tint); padding: 1px 5px; font-size: 0.9em; }
a { color: var(--link); text-decoration: none; border-bottom: 1px solid rgba(37, 99, 235, 0.35); }
a:hover { border-bottom-color: var(--link); }

.table-scroll { overflow-x: auto; margin: 24px 0; }
table { border-collapse: collapse; width: 100%; margin: 0; font-size: 14.5px; line-height: 1.7; font-variant-numeric: tabular-nums; }
th, td { text-align: left; vertical-align: top; padding: 10px 16px 10px 0; border-bottom: 1px solid var(--rule); }
th { font-size: 11.5px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid var(--rule-strong); }

figure.exhibit { margin: 40px 0; border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); padding: 24px 0 28px; }
figure.exhibit figcaption { font-size: 13px; letter-spacing: 0.05em; font-variant: small-caps; color: #374151; margin-bottom: 14px; }
figure.exhibit svg { display: block; width: 100%; height: auto; }

/* Wide screens: the TOC becomes a sticky rail and the exhibits gain width. */
@media (min-width: 1240px) {
  .doc:has(nav.toc) { max-width: 1220px; display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 72px; align-items: start; }
  .doc:has(nav.toc) .doc-main { grid-column: 1; grid-row: 1; }
  .doc:has(nav.toc) .toc {
    grid-column: 2; grid-row: 1;
    position: sticky; top: 40px;
    border-top: none; border-bottom: none;
    border-left: 1px solid var(--rule);
    padding: 4px 0 4px 28px;
    margin: 0;
    max-height: calc(100vh - 80px);
    overflow-y: auto;
  }
}

@media (max-width: 640px) {
  .title-band-inner { padding: 40px 20px 28px; }
  .title-band h1 { font-size: 32px; }
  .doc { padding: 32px 16px 64px; }
}

@media print {
  @page { size: A4; margin: 20mm 18mm; }
  html, body { background: #FFFFFF; font-size: 10.5pt; line-height: 1.65; }
  .title-band {
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
    min-height: 257mm; box-sizing: border-box;
    display: flex; flex-direction: column; justify-content: center;
    break-after: page; page-break-after: always;
  }
  .doc { display: block; max-width: none; padding: 0; }
  .doc-main > p, .doc-main > ul, .doc-main > ol, .doc-main > blockquote, .doc-main > h3 { max-width: none; }
  .toc {
    position: static; border-left: none;
    border-top: 1px solid var(--rule-strong); border-bottom: 1px solid var(--rule-strong);
    padding: 20px 0; margin: 0;
    break-after: page; page-break-after: always;
  }
  h2 { margin-top: 40px; break-after: avoid-page; page-break-after: avoid; }
  h3 { break-after: avoid-page; page-break-after: avoid; }
  p, li { orphans: 3; widows: 3; }
  figure.exhibit, blockquote, .table-scroll, tr { break-inside: avoid; page-break-inside: avoid; }
  a { color: #000000; border-bottom: none; text-decoration: underline; }
  .toc a { text-decoration: none; }
}
"""

TOC_SCRIPT = """
(function () {
  var links = Array.prototype.slice.call(document.querySelectorAll('.toc a'));
  if (!links.length || !window.IntersectionObserver) return;
  var targets = links.map(function (a) { return document.getElementById(a.getAttribute('href').slice(1)); });
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      var index = targets.indexOf(entry.target);
      if (index === -1) return;
      if (entry.isIntersecting) {
        links.forEach(function (l) { l.classList.remove('active'); });
        links[index].classList.add('active');
      }
    });
  }, { rootMargin: '0px 0px -70% 0px' });
  targets.forEach(function (t) { if (t) observer.observe(t); });
})();
"""


def build_report(markdown_text: str, base_dir: Path, lang_override: str | None = None) -> str:
    """Build the report HTML from Markdown source.

    ``base_dir`` must be (or is made) absolute -- exhibit references resolve
    relative to it, independent of the process's current working directory.
    """
    base_dir = Path(base_dir).resolve()
    front, body_text = parse_front_matter(markdown_text)
    body_text = body_text.expandtabs(4)

    title = front.get("title", "Untitled")
    subtitle = front.get("subtitle", "")
    author = front.get("author", "")
    date = front.get("date", "")
    classification = front.get("classification", "")
    lang = (lang_override or front.get("lang") or "en").strip().lower()
    if lang not in ("en", "ja"):
        lang = "en"

    blocks = _split_blocks(body_text)
    body_html, toc = render_body(blocks, base_dir)

    toc_html = ""
    if toc:
        items_html = "".join(
            f'<li><a href="#{esc(slug)}">{number}. {heading_html}</a></li>'
            for number, heading_html, slug in toc
        )
        toc_html = (
            '<nav class="toc" aria-label="Contents">'
            '<p class="toc-label">Contents</p>'
            f"<ol>{items_html}</ol>"
            "</nav>"
        )

    classification_html = (
        f'<div class="classification">{esc(classification.upper())}</div>' if classification else ""
    )
    subtitle_html = f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else ""
    meta_parts = [esc(p) for p in (author, date) if p]
    meta_html = f'<p class="meta">{" &middot; ".join(meta_parts)}</p>' if meta_parts else ""

    title_band = (
        '<header class="title-band">'
        '<div class="title-band-inner">'
        f"{classification_html}"
        f"<h1>{esc(title)}</h1>"
        f"{subtitle_html}"
        f"{meta_html}"
        "</div>"
        "</header>"
    )

    script_html = f"<script>{TOC_SCRIPT}</script>" if toc_html else ""
    body_class = ' class="lang-ja"' if lang == "ja" else ""

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>{STYLE}</style>
</head>
<body{body_class}>
{title_band}
<main class="doc">
{toc_html}
<div class="doc-main">
{body_html}
</div>
</main>
{script_html}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a self-contained consulting-style HTML report from Markdown."
    )
    parser.add_argument("input", help="Path to the input Markdown file")
    parser.add_argument("-o", "--output", required=True, help="Output HTML path")
    parser.add_argument(
        "--lang",
        choices=("en", "ja"),
        default=None,
        help="Override the document language (default: front matter lang, else en)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    try:
        markdown_text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read input: {exc}", file=sys.stderr)
        raise SystemExit(1)

    try:
        html = build_report(markdown_text, input_path.resolve().parent, args.lang)
    except ReportBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"OK: built report at {output_path}")


if __name__ == "__main__":
    main()
