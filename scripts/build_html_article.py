#!/usr/bin/env python3
"""Build a self-contained "deck as an article" HTML page from a slide manifest.

The M3-series reading experience: the whole deck laid out vertically, in
slide order, each slide's SVG followed by its narrative prose -- a deck that
reads top to bottom like a web article instead of click-through-one-slide-
at-a-time. Companion to scripts/build_speaker_script.py (the podium script,
one slide per printed page) and scripts/build_html_deck.py (the click-
through presenter deck); this shares their manifest format and the reading
mechanics of scripts/build_html_report.py.

Manifest format (same file scripts/build_html_deck.py consumes):

    {"title": "Q3 Board Update", "description": "...", "slides": [
        "specs/01-cover.json", "specs/02-agenda.json", ...
    ]}

Slide paths resolve relative to the manifest file, in the order listed --
that order is preserved exactly in the rendered article. ``title`` and
``description`` (if present) seed the navy title band's heading and
subtitle; the first ``cover``-pattern slide's ``presenter``/``date`` fields
(if present) seed the band's meta line, the same "presenter · date" pairing
render_cover() draws on the cover slide itself.

The shared `notes` contract (any slide spec may carry a top-level `notes`:
a string, or a list of strings, one per paragraph): scripts/render_slide_spec.py
ignores it entirely -- a spec with notes renders byte-identical SVG to the
same spec without (see tests/test_build_html_article.py) -- so notes are
purely this builder's concern. A string is split into paragraphs on blank
lines, mirroring the paragraph convention scripts/build_html_report.py's
Markdown parser already uses for prose; a list is used as-is, one entry per
paragraph. Every paragraph is escaped with the shared `esc()` on the way
into HTML: notes are untrusted, spoken/narrative text, never markup.

Output is one <section> per slide, always in manifest order, with every
slide shown -- chromeless slides (cover / section_divider / end_cover,
scripts/render_slide_spec.CHROMELESS) included, exactly like flipping
through the physical deck:

    - The slide's SVG, embedded inline (xmlns stripped, as build_html_report.py
      strips it for the same "no spurious http:// string" reason), running
      the full ~980px reading column.
    - Below it, the slide's notes as reading prose on build_html_report.py's
      ~720px measure -- 16px body, `--lang ja` loosens line-height to 1.9
      with `font-feature-settings: palt` for CJK readability (Latin: 1.7).
    - A slide with no notes renders frame-only: the figure, nothing below
      it. The article still shows the slide -- never silently skipped.

A "Contents" TOC is built from every *content* slide's headline (falling
back to `title`, then a "Slide N" placeholder) in document order; chromeless
slides are omitted from the TOC (they carry no headline chrome to link to)
but still appear in the flow. The TOC reuses build_html_report.py's exact
mechanics rather than forking a third style: a hairline-bordered band by
default, promoted to a sticky right rail via `:has()` on wide screens.

Output is a single self-contained HTML file: zero external requests, no
required JavaScript (the TOC scroll-highlight script is inline and
decorative only, included only when a TOC exists). Screen layout is a
~980px reading column; print layout is A4 with the slide figure kept
together (`break-inside: avoid`) but no forced page break between slides
(this is a continuous read, not a one-slide-per-page script -- see
scripts/build_speaker_script.py for that).

Usage:
    python3 scripts/build_html_article.py --manifest deck.json -o article.html
    python3 scripts/build_html_article.py --manifest deck.json -o article.html --lang ja
    python3 scripts/build_html_article.py --manifest deck.json -o article.html --title "Custom title"
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
CHROMELESS = _renderer.CHROMELESS


class ArticleBuildError(ValueError):
    """Raised when the article cannot be built: a missing slide spec file, a
    spec that is not valid JSON, or a spec scripts/render_slide_spec.py
    rejects. Mirrors build_html_report.py's ReportBuildError -- a bad slide
    reference is always a hard error naming the path, never a blank section."""


# ---------------------------------------------------------------------------
# notes -> paragraphs (shared contract with scripts/build_speaker_script.py)
# ---------------------------------------------------------------------------

_BLANK_LINE_RE = re.compile(r"\n\s*\n+")


def notes_paragraphs(notes: object) -> list[str]:
    """Normalize a slide's ``notes`` field into raw (unescaped) paragraph
    strings, in reading order.

    Accepts the two shapes the shared contract allows: a list of strings
    (one paragraph each) or a single string (split into paragraphs on blank
    lines). Anything else -- a missing key, ``None``, a number, an empty
    list -- degrades to "no notes" (an empty list) rather than raising, so a
    malformed or absent notes field never breaks the build.
    """
    if isinstance(notes, list):
        raw_paragraphs = [str(item) for item in notes]
    elif isinstance(notes, str):
        raw_paragraphs = _BLANK_LINE_RE.split(notes.strip())
    else:
        return []
    # Collapse internal whitespace/newlines within a paragraph to single
    # spaces -- a paragraph is read as one continuous line of prose
    # regardless of how it was wrapped in the source JSON.
    return [" ".join(p.split()) for p in raw_paragraphs if p.strip()]


# ---------------------------------------------------------------------------
# Slide loading + inline SVG embedding
# ---------------------------------------------------------------------------

_SVG_XMLNS_RE = re.compile(r'\s+xmlns="[^"]*"')
_XML_PROLOG_RE = re.compile(r"^\s*<\?xml[^>]*\?>\s*")


def _strip_for_inline_embed(svg: str) -> str:
    """Drop standalone-XML furniture not needed once inlined in HTML5: the
    xml prolog and the root xmlns attribute (see build_html_report.py's
    identically-named helper for the full rationale)."""
    svg = _XML_PROLOG_RE.sub("", svg, count=1)
    svg = _SVG_XMLNS_RE.sub("", svg, count=1)
    return svg


def _load_spec(path: Path) -> dict:
    if not path.is_file():
        raise ArticleBuildError(f"slide spec not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArticleBuildError(f"slide spec is not valid JSON: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise ArticleBuildError(f"slide spec must be a JSON object: {path}")
    return data


def _render_slide_svg(spec: dict, path: Path) -> str:
    try:
        svg = _renderer.render(spec)
    except Exception as exc:  # noqa: BLE001 - any render failure is a hard, named error
        raise ArticleBuildError(f"slide spec failed to render: {path} ({exc})") from exc
    return _strip_for_inline_embed(svg)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "slide"


def _cover_meta_html(specs: list[dict]) -> str:
    """The title band's "presenter · date" meta line, sourced from the first
    cover-pattern slide that carries either field -- the same pairing
    render_cover() draws on the cover slide itself."""
    for spec in specs:
        if spec.get("pattern") != "cover":
            continue
        parts = [esc(spec[key]) for key in ("presenter", "date") if spec.get(key)]
        if parts:
            return " &middot; ".join(parts)
    return ""


# ---------------------------------------------------------------------------
# Sections + TOC
# ---------------------------------------------------------------------------


def _build_sections(specs: list[dict], spec_paths: list[Path]) -> tuple[str, str]:
    """Render every slide, in order, into an article section; build the
    matching "Contents" TOC alongside it.

    Every slide gets a section -- chromeless (CHROMELESS) or not -- so the
    article always shows the whole deck. Only non-chromeless (headline-
    bearing) slides get a TOC entry and the anchor id it links to.
    """
    section_parts: list[str] = []
    toc_items: list[str] = []
    used_slugs: set[str] = set()
    entry_number = 0

    for spec, path in zip(specs, spec_paths):
        svg = _render_slide_svg(spec, path)
        is_content = spec.get("pattern", "") not in CHROMELESS

        id_attr = ""
        if is_content:
            entry_number += 1
            label = spec.get("headline") or spec.get("title") or f"Slide {entry_number}"
            base_slug = _slugify(label)
            slug, suffix = base_slug, 2
            while slug in used_slugs:
                slug = f"{base_slug}-{suffix}"
                suffix += 1
            used_slugs.add(slug)
            id_attr = f' id="{esc(slug)}"'
            toc_items.append(f'<li><a href="#{esc(slug)}">{entry_number}. {esc(label)}</a></li>')

        notes_html = ""
        paragraphs = notes_paragraphs(spec.get("notes"))
        if paragraphs:
            paras_html = "".join(f"<p>{esc(p)}</p>" for p in paragraphs)
            notes_html = f'<div class="notes">{paras_html}</div>'

        section_parts.append(
            f'<section class="slide-block"{id_attr}>'
            f'<figure class="slide-figure">\n{svg}\n</figure>'
            f"{notes_html}"
            "</section>"
        )

    toc_html = ""
    if toc_items:
        toc_html = (
            '<nav class="toc" aria-label="Contents">'
            '<p class="toc-label">Contents</p>'
            f"<ol>{''.join(toc_items)}</ol>"
            "</nav>"
        )
    return "\n".join(section_parts), toc_html


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

STYLE = """
/* Reading layer, sharing scripts/build_html_report.py's mechanics: the deck
   read top-to-bottom as one article. Each slide's SVG runs the full ~980px
   column (an "exhibit"); its narration sits below on a capped 720px
   reading measure. Section rhythm from hairlines and whitespace only -- no
   boxes, no left accent bars. The TOC is a sticky rail on wide screens,
   otherwise the same hairline band build_html_report.py uses -- never a
   third TOC style. */
:root {
  color-scheme: light;
  --navy: #15296B;
  --ink: #000000;
  --body-ink: #1F2937;
  --muted: #6B7280;
  --rule: #D1D5DB;
  --rule-strong: #9CA3AF;
  --measure: 720px;
  --serif: Georgia, 'Times New Roman', 'Hiragino Mincho ProN', 'Yu Mincho', serif;
  --sans: 'Helvetica Neue', Helvetica, Arial, 'Hiragino Sans', 'Yu Gothic', 'Noto Sans JP', 'Meiryo', sans-serif;
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
h1 { color: var(--ink); font-family: var(--serif); font-weight: bold; }

.title-band { background: var(--navy); color: #FFFFFF; }
.title-band-inner { max-width: 1220px; margin: 0 auto; padding: 72px 32px 48px; }
.title-band h1 { font-size: 42px; font-weight: normal; color: #FFFFFF; line-height: 1.25; max-width: 780px; text-wrap: balance; }
.title-band .subtitle { margin-top: 14px; font-size: 18px; font-weight: normal; color: #E5E7EB; max-width: 720px; }
.title-band .meta { margin-top: 24px; font-size: 14px; color: #E5E7EB; letter-spacing: 0.02em; }

.doc { max-width: 1044px; margin: 0 auto; padding: 56px 32px 96px; }
.doc-main { min-width: 0; }

.toc { border-top: 1px solid var(--rule-strong); border-bottom: 1px solid var(--rule-strong); padding: 20px 0; margin-bottom: 56px; }
.toc .toc-label { font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; }
.toc ol { list-style: none; padding-left: 0; }
.toc li { margin: 4px 0; }
.toc a { color: var(--body-ink); text-decoration: none; font-size: 15px; }
.toc a:hover { color: var(--navy); }
.toc a.active { color: var(--navy); font-weight: 600; }

.slide-block { margin: 0 0 56px; }
.slide-block:last-child { margin-bottom: 0; }
.slide-figure { border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule); padding: 20px 0; margin: 0; }
.slide-figure svg { display: block; width: 100%; height: auto; }
.notes { max-width: var(--measure); margin-top: 20px; }
.notes p { margin: 12px 0; }
.notes p:first-child { margin-top: 0; }

/* Wide screens: the TOC becomes a sticky rail, same mechanics as build_html_report.py. */
@media (min-width: 1240px) {
  .doc:has(nav.toc) { max-width: 1302px; display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 72px; align-items: start; }
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
  .notes { max-width: none; }
  .toc {
    position: static; border-left: none;
    border-top: 1px solid var(--rule-strong); border-bottom: 1px solid var(--rule-strong);
    padding: 20px 0; margin: 0 0 32px;
  }
  /* Keep a slide's figure from splitting across a page break; the notes
     below it may still flow onto the next page -- this is a continuous
     read, not a one-slide-per-page script (see build_speaker_script.py). */
  .slide-figure { break-inside: avoid; page-break-inside: avoid; }
  p { orphans: 3; widows: 3; }
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


def build_article(spec_paths: list[Path], title: str, subtitle: str, lang: str) -> str:
    """Build the article HTML from an ordered list of slide spec paths.

    ``title``/``subtitle``/``lang`` are already resolved by the caller (CLI
    override vs. manifest fallback) -- this function only assembles them.
    """
    lang = lang if lang in ("en", "ja") else "en"
    specs = [_load_spec(path) for path in spec_paths]
    sections_html, toc_html = _build_sections(specs, spec_paths)

    cover_meta = _cover_meta_html(specs)
    meta_html = f'<p class="meta">{cover_meta}</p>' if cover_meta else ""
    subtitle_html = f'<p class="subtitle">{esc(subtitle)}</p>' if subtitle else ""

    title_band = (
        '<header class="title-band">'
        '<div class="title-band-inner">'
        f"<h1>{esc(title)}</h1>"
        f"{subtitle_html}"
        f"{meta_html}"
        "</div>"
        "</header>"
    )

    body_class = ' class="lang-ja"' if lang == "ja" else ""
    script_html = f"<script>{TOC_SCRIPT}</script>" if toc_html else ""

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
{sections_html}
</div>
</main>
{script_html}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a self-contained HTML article from a slide deck manifest."
    )
    parser.add_argument("--manifest", required=True, help="Deck manifest JSON with {title, slides}")
    parser.add_argument("-o", "--output", required=True, help="Output HTML path")
    parser.add_argument(
        "--lang", choices=("en", "ja"), default="en", help="Document language (default: en)"
    )
    parser.add_argument(
        "--title", default=None, help="Override the article title (default: manifest title)"
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read manifest: {exc}", file=sys.stderr)
        raise SystemExit(1)

    slides = manifest.get("slides")
    if not isinstance(slides, list) or not slides:
        print("ERROR: manifest has no slides", file=sys.stderr)
        raise SystemExit(1)

    base = manifest_path.parent
    spec_paths = [base / p for p in slides]
    title = args.title or manifest.get("title", "Untitled")
    subtitle = manifest.get("description", "")

    try:
        html = build_article(spec_paths, title, subtitle, args.lang)
    except ArticleBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"OK: built article ({len(spec_paths)} slides) at {output_path}")


if __name__ == "__main__":
    main()
