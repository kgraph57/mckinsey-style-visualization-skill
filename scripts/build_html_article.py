#!/usr/bin/env python3
"""Build a self-contained "deck as an article" HTML page from a slide manifest.

The M3-series reading experience: the whole deck laid out vertically, in
slide order, each slide's SVG followed by its narrative prose -- a deck that
reads top to bottom like a web article instead of click-through-one-slide-
at-a-time. Companion to scripts/build_speaker_script.py (the podium script,
one slide per printed page) and scripts/build_html_deck.py (the click-
through presenter deck).

v2.4 matches the structure of a real published M3-series article: a single
680px reading column (no sticky/side "Contents" rail -- this is a linear
scroll, not a document with navigation), a paper-first hero (kicker, serif
h1, lead paragraph, meta chips -- no navy title band), and per-slide meta
(number + optional section label) with an optional "further reading" aside.
The skill's own skin is kept throughout: navy #15296B as the one accent
color, Georgia serif headings, hairlines, and the JP sans stack (Hiragino
before Noto Sans JP).

Manifest format (same file scripts/build_html_deck.py consumes):

    {
      "title": "Q3 Board Update",
      "series": "Board Reporting Series",
      "lead": "A short narrative lead paragraph for the hero.",
      "description": "...",
      "slides": ["specs/01-cover.json", "specs/02-agenda.json", ...]
    }

Slide paths resolve relative to the manifest file, in the order listed --
that order is preserved exactly in the rendered article, and drives the
per-slide anchor ids (``slide-01``, ``slide-02``, ...). ``title`` seeds the
hero's ``<h1>`` and the document ``<title>``. ``series`` (optional) seeds
the hero's uppercase kicker line. ``lead`` (optional) seeds the hero's lead
paragraph; if a manifest has no ``lead``, ``description`` is used instead so
older manifests (written before ``lead`` existed) still get a lead
paragraph -- ``description`` remains the field scripts/scaffold_deck.py
reads for its own deck-picker listing, so this is additive, not a rename.
The first ``cover``-pattern slide's ``presenter``/``date`` fields (if
present) seed two of the hero's meta chips; a third chip always reports the
slide count.

The shared `notes` contract (any slide spec may carry a top-level `notes`:
a string, or a list of strings, one per paragraph): scripts/render_slide_spec.py
ignores it entirely -- a spec with notes renders byte-identical SVG to the
same spec without (see tests/test_build_html_article.py) -- so notes are
purely this builder's concern. A string is split into paragraphs on blank
lines, mirroring the paragraph convention scripts/build_html_report.py's
Markdown parser already uses for prose; a list is used as-is, one entry per
paragraph. Every paragraph is escaped with the shared `esc()` on the way
into HTML: notes are untrusted, spoken/narrative text, never markup.

Two more optional per-slide spec fields, both additive (the renderer
ignores both, exactly like ``notes``):

    - ``label``: a short string shown next to the slide number in the
      meta line (small caps, muted) -- a section tag, e.g. "Growth Bridge".
    - ``refs``: a list of ``{"label": str, "url": str}`` objects rendered
      as a bulleted "Links" aside below the slide's notes. A ``url`` whose
      scheme is not http(s)/mailto is dropped to plain (unlinked) text --
      the same allowlist scripts/build_html_report.py's Markdown links use
      (``_safe_href``, imported rather than re-implemented). Every ref
      collected across the whole deck is also rolled up, deduped by URL, in
      an aggregated links section after the last slide.

Output is one <article class="slide-block"> per slide, always in manifest
order, with every slide shown -- chromeless slides (cover / section_divider
/ end_cover, scripts/render_slide_spec.CHROMELESS) included, exactly like
flipping through the physical deck:

    - A meta line: the slide's 1-based position (in navy) and its optional
      ``label``.
    - An <h2> with the slide's headline, or (chromeless slides only) its
      ``title`` -- omitted entirely when neither is present, since a
      chromeless slide with no headline and no title carries no distinct
      message text to show.
    - The slide's SVG, embedded inline (xmlns stripped, as build_html_report.py
      strips it for the same "no spurious http:// string" reason), running
      the full 680px reading column with a 1px hairline frame.
    - Below it, the slide's notes as reading prose (16px, `--lang ja`
      loosens line-height to 1.9 with `font-feature-settings: palt` for CJK
      readability; Latin stays 1.7). A slide with no notes renders frame-
      only: the figure, nothing below it. The article still shows the
      slide -- never silently skipped.
    - An optional "Links" aside, if the slide carries ``refs``.

There is no "Contents" navigation in this mode (v2.3 had one; the reference
M3 article format this version matches is a single linear scroll instead --
see the v2.4.0 addendum). If any slide carried refs, an aggregated links
section follows the last slide, then a one-line footer.

Output is a single self-contained HTML file: zero external requests (the
one exception is the ``href`` of a ref link itself, which is meant to be
followed -- there is no image, script, or stylesheet fetch anywhere), no
required JavaScript at all. Screen layout is a single 680px reading column;
print layout is A4 portrait with each slide-block kept together
(`break-inside: avoid`) -- no forced page break between slides (this is a
continuous read, not a one-slide-per-page script -- see
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


def _load_module(name: str):
    module_path = ROOT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_renderer = _load_module("render_slide_spec")
esc = _renderer.esc
CHROMELESS = _renderer.CHROMELESS

# The refs scheme allowlist is the report builder's own -- imported rather
# than re-implemented, so the two never drift apart (see _safe_href's
# docstring in build_html_report.py for the full rationale: http(s)/mailto
# only, control characters rejected outright).
_report = _load_module("build_html_report")
_safe_href = _report._safe_href


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


def _normalize_refs(raw: object) -> list[dict]:
    """Normalize a slide's optional ``refs`` field into an ordered list of
    ``{"label": str, "url": str}`` dicts, dropping malformed entries.

    ``refs`` is additive and optional, exactly like ``notes`` and ``label``:
    anything that is not a list, a list item that is not an object, or an
    item missing a usable ``url`` is silently skipped rather than raising --
    a malformed ref entry never breaks the build. A missing ``label`` falls
    back to the URL itself so the link always has visible text.
    """
    if not isinstance(raw, list):
        return []
    normalized: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        label = item.get("label")
        label = str(label) if label else url
        normalized.append({"label": label, "url": url})
    return normalized


def _render_ref_list(refs: list[dict]) -> str:
    """Render a ``<ul class="ref-list">`` for a list of normalized refs.

    Shared by the per-slide "Links" aside and the aggregated end-of-article
    links section, so the two can never drift in markup or in how they
    apply the scheme allowlist. A ref whose URL fails ``_safe_href`` (any
    scheme outside http/https/mailto, e.g. ``javascript:``) renders as
    plain, unlinked text instead of an <a> -- dropped silently, never an
    error, exactly like build_html_report.py's Markdown links.
    """
    items = []
    for ref in refs:
        label_html = esc(ref["label"])
        href = _safe_href(ref["url"])
        if href is None:
            items.append(f"<li>{label_html}</li>")
        else:
            items.append(
                f'<li><a href="{esc(href)}" target="_blank" rel="noopener">{label_html}</a></li>'
            )
    return f'<ul class="ref-list">{"".join(items)}</ul>'


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


def _cover_meta(specs: list[dict]) -> dict:
    """The hero's presenter/date chips, sourced from the first cover-pattern
    slide that carries either field -- the same pairing render_cover() draws
    on the cover slide itself."""
    for spec in specs:
        if spec.get("pattern") != "cover":
            continue
        return {
            "presenter": str(spec.get("presenter") or ""),
            "date": str(spec.get("date") or ""),
        }
    return {"presenter": "", "date": ""}


def _slide_heading(spec: dict, is_chromeless: bool, index: int) -> str | None:
    """The slide-block's <h2> text.

    Content slides always get one: headline, falling back to title, falling
    back to a "Slide N" placeholder -- there is always a message to show.
    Chromeless slides (cover / section_divider / end_cover) use headline or
    title if either is present, but render no <h2> at all when neither is:
    a bare chromeless slide with no distinct message text has nothing worth
    heading (the hero's own <h1> already carries the deck's title).
    """
    headline = spec.get("headline")
    if headline:
        return str(headline)
    title = spec.get("title")
    if title:
        return str(title)
    if is_chromeless:
        return None
    return f"Slide {index}"


# ---------------------------------------------------------------------------
# Sections + aggregated links
# ---------------------------------------------------------------------------


def _build_sections(specs: list[dict], spec_paths: list[Path], lang: str) -> tuple[str, list[dict]]:
    """Render every slide, in order, into an <article class="slide-block">;
    collect every ref seen along the way (in slide order, deduped by URL)
    for the aggregated end-of-article links section.

    Every slide gets a section -- chromeless (CHROMELESS) or not -- so the
    article always shows the whole deck.
    """
    section_parts: list[str] = []
    all_refs: list[dict] = []
    seen_urls: set[str] = set()

    for index, (spec, path) in enumerate(zip(specs, spec_paths), start=1):
        svg = _render_slide_svg(spec, path)
        is_chromeless = spec.get("pattern", "") in CHROMELESS
        slug = f"slide-{index:02d}"

        label = spec.get("label")
        label_html = f'<span class="lbl">{esc(label)}</span>' if label else ""
        meta_html = f'<p class="slide-meta"><span class="num">{index}</span>{label_html}</p>'

        heading = _slide_heading(spec, is_chromeless, index)
        heading_html = f"<h2>{esc(heading)}</h2>" if heading else ""

        head_html = f'<header class="slide-head">{meta_html}{heading_html}</header>'
        figure_html = f'<figure class="slide-figure">\n{svg}\n</figure>'

        notes_html = ""
        paragraphs = notes_paragraphs(spec.get("notes"))
        if paragraphs:
            paras_html = "".join(f"<p>{esc(p)}</p>" for p in paragraphs)
            notes_html = f'<div class="notes">{paras_html}</div>'

        refs = _normalize_refs(spec.get("refs"))
        refs_html = ""
        if refs:
            refs_html = (
                '<aside class="slide-refs">'
                f'<p class="slide-refs-label">{esc(REFS_LABEL[lang])}</p>'
                f"{_render_ref_list(refs)}"
                "</aside>"
            )
            for ref in refs:
                if ref["url"] not in seen_urls:
                    seen_urls.add(ref["url"])
                    all_refs.append(ref)

        section_parts.append(
            f'<article class="slide-block" id="{slug}">'
            f"{head_html}"
            f"{figure_html}"
            f"{notes_html}"
            f"{refs_html}"
            "</article>"
        )

    return "\n".join(section_parts), all_refs


# ---------------------------------------------------------------------------
# Hero, aggregated links, footer
# ---------------------------------------------------------------------------

SLIDE_COUNT_TEXT = {
    "en": lambda n: f"{n} slide" if n == 1 else f"{n} slides",
    "ja": lambda n: f"全 {n} スライド",
}
AUTHOR_PREFIX = {"en": "Author: ", "ja": "著者："}
REFS_LABEL = {"en": "Links", "ja": "関連リンク"}
ALL_LINKS_TITLE = {"en": "All links", "ja": "参考リンク一覧"}
FOOTER_GENERATED = {
    "en": "Generated by the Strategy Consulting Visualization skill.",
    "ja": "Strategy Consulting Visualization スキルで生成。",
}


def _hero_html(title: str, lead: str, series: str, cover_meta: dict, slide_count: int, lang: str) -> str:
    kicker_html = f'<p class="kicker">{esc(series)}</p>' if series else ""
    lead_html = f'<p class="lead">{esc(lead)}</p>' if lead else ""

    chips = [f'<span class="chip">{esc(SLIDE_COUNT_TEXT[lang](slide_count))}</span>']
    if cover_meta.get("presenter"):
        chips.append(f'<span class="chip">{AUTHOR_PREFIX[lang]}{esc(cover_meta["presenter"])}</span>')
    if cover_meta.get("date"):
        chips.append(f'<span class="chip">{esc(cover_meta["date"])}</span>')
    meta_row_html = f'<div class="meta-row">{"".join(chips)}</div>'

    return (
        '<header class="hero">'
        f"{kicker_html}"
        f"<h1>{esc(title)}</h1>"
        f"{lead_html}"
        f"{meta_row_html}"
        "</header>"
    )


def _bibliography_html(all_refs: list[dict], lang: str) -> str:
    """The aggregated "All links" / "参考リンク一覧" section after the last
    slide -- every ref collected across the deck, in slide order, deduped by
    URL. Omitted entirely when no slide carried any refs."""
    if not all_refs:
        return ""
    return (
        '<section class="bibliography" id="all-links">'
        f"<h2>{esc(ALL_LINKS_TITLE[lang])}</h2>"
        f"{_render_ref_list(all_refs)}"
        "</section>"
    )


def _footer_html(title: str, lang: str) -> str:
    return f"<footer><p>{esc(title)} &middot; {esc(FOOTER_GENERATED[lang])}</p></footer>"


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

STYLE = """
/* Paper-first reading layer matching the M3-series article format (see the
   v2.4.0 addendum): a single 680px column, no side rail, no navy band --
   just a hero, then each slide's figure and prose, in one linear scroll.
   The skill's own skin throughout: navy as the one accent, Georgia serif
   headings, hairlines, no boxes, no left accent bars. */
:root {
  color-scheme: light;
  --navy: #15296B;
  --ink: #000000;
  --body-ink: #1F2937;
  --muted: #6B7280;
  --rule: #D1D5DB;
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
  /* Progressive enhancements from the reference: inert on browsers that
     don't support them, harmless everywhere, never load-bearing. */
  text-wrap: pretty;
  word-break: auto-phrase;
}
body.lang-ja { line-height: 1.9; font-feature-settings: 'palt'; }
h1, h2 { font-family: var(--serif); font-weight: normal; color: var(--ink); }

.wrap { max-width: 680px; margin: 0 auto; padding: clamp(40px, 7vw, 72px) clamp(20px, 5vw, 28px) 96px; }

.hero { padding-bottom: 28px; margin-bottom: 8px; border-bottom: 1px solid var(--ink); }
.hero .kicker { font-size: 12px; font-weight: 600; letter-spacing: 0.14em; text-transform: uppercase; color: var(--muted); margin-bottom: 12px; }
.hero h1 { font-size: clamp(1.6rem, 4.2vw, 2rem); line-height: 1.35; letter-spacing: 0.01em; }
.hero .lead { margin-top: 16px; color: var(--muted); font-size: 1rem; max-width: 56ch; line-height: 1.75; }
.hero .meta-row { margin-top: 18px; font-size: 13px; color: var(--muted); letter-spacing: 0.02em; }
.hero .meta-row .chip { display: inline; }
.hero .meta-row .chip + .chip::before { content: " · "; }

.slide-block { padding: 40px 0; border-top: 1px solid var(--rule); }
.slide-block:first-of-type { border-top: none; padding-top: 0; }
.slide-head { margin-bottom: 18px; }
.slide-meta { font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
.slide-meta .num { color: var(--navy); margin-right: 0.6em; }
.slide-head h2 { font-size: 1.2rem; line-height: 1.5; }

.slide-figure { margin: 0 0 24px; border: 1px solid var(--rule); }
.slide-figure svg { display: block; width: 100%; height: auto; }

.notes p { margin: 0 0 16px; font-size: 16px; }
.notes p:first-child { margin-top: 0; }
.notes p:last-child { margin-bottom: 0; }

.slide-refs { margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--rule); }
.slide-refs-label { font-size: 11px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); margin-bottom: 8px; }
.ref-list { margin: 0; padding-left: 1.15em; list-style: disc; }
.ref-list li { margin: 0.35em 0; font-size: 0.9rem; line-height: 1.55; }
.ref-list a { color: var(--navy); text-decoration: none; font-weight: 600; word-break: break-all; }
.ref-list a:hover { text-decoration: underline; }

.bibliography { margin-top: 48px; padding-top: 28px; border-top: 1px solid var(--ink); }
.bibliography h2 { font-size: 1.05rem; margin-bottom: 14px; }
.bibliography .ref-list li { font-size: 0.92rem; }

footer { margin-top: 56px; padding-top: 16px; border-top: 1px solid var(--rule); font-size: 12px; color: var(--muted); }

@media (max-width: 640px) {
  .wrap { padding: 32px 16px 64px; }
}

@media print {
  @page { size: A4 portrait; margin: 18mm; }
  html, body { background: #FFFFFF; font-size: 10.5pt; line-height: 1.6; }
  .wrap { max-width: none; padding: 0; }
  /* Keep a slide's whole block (meta, heading, figure, prose, refs) from
     splitting across a page break; nothing forces a page break between
     slides -- this is a continuous read, not a one-slide-per-page script
     (see scripts/build_speaker_script.py for that). */
  .slide-block { break-inside: avoid; page-break-inside: avoid; }
  p { orphans: 3; widows: 3; }
}
"""


def build_article(
    spec_paths: list[Path],
    title: str,
    lead: str,
    lang: str,
    series: str = "",
) -> str:
    """Build the article HTML from an ordered list of slide spec paths.

    ``title``/``lead``/``lang``/``series`` are already resolved by the
    caller (CLI override vs. manifest fallback) -- this function only
    assembles them. ``lead`` is the hero's lead paragraph (the manifest's
    optional ``lead`` key, or ``description`` as a fallback for older
    manifests); ``series`` is the hero's optional uppercase kicker line.
    """
    lang = lang if lang in ("en", "ja") else "en"
    specs = [_load_spec(path) for path in spec_paths]
    sections_html, all_refs = _build_sections(specs, spec_paths, lang)

    cover_meta = _cover_meta(specs)
    hero_html = _hero_html(title, lead, series, cover_meta, len(specs), lang)
    bibliography_html = _bibliography_html(all_refs, lang)
    footer_html = _footer_html(title, lang)

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
<div class="wrap">
{hero_html}
<main class="doc-main">
{sections_html}
</main>
{bibliography_html}
{footer_html}
</div>
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
    lead = manifest.get("lead") or manifest.get("description", "")
    series = manifest.get("series", "")

    try:
        html = build_article(spec_paths, title, lead, args.lang, series=series)
    except ArticleBuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"OK: built article ({len(spec_paths)} slides) at {output_path}")


if __name__ == "__main__":
    main()
