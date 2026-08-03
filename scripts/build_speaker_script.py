#!/usr/bin/env python3
"""Build a self-contained, print-first speaker script from a slide deck manifest.

The conference-day paper script: what a presenter reads at the podium, with
each slide reproduced above its own spoken narration. Every slide spec JSON
may carry a top-level ``"notes"`` field -- a string, or a list of strings
(paragraphs) -- holding that narration; render_slide_spec.py's SVG renderer
ignores the field entirely, so adding notes to a spec never changes its
rendered slide.

Manifest format (identical to scripts/build_html_deck.py; slide paths
resolve relative to the manifest file, not the process's current working
directory):

    {"title": "Q4 Review", "slides": ["specs/cover.json", "specs/bridge.json"]}

Notes normalization:
    - A list is already paragraph-segmented: each item becomes one <p>
      (internal newlines within an item collapse to a single space, the way
      a soft-wrapped line reads as one sentence).
    - A string is segmented into paragraphs on blank lines (one or more),
      the ordinary "blank line = new paragraph" convention.
    - Missing, empty, or a value that is neither a str nor a list normalizes
      to "no notes" -- the page still renders (slide + a muted "no script"
      marker), it is never silently skipped.

Output is a single self-contained HTML file, PRINT-FIRST:
    - @page A4 landscape, ~12mm margins; one slide per printed page,
      slide on the left and the narration on the right (the presenter-view
      layout: the script is the hero, the slide is the reference)
      (break-after: page on every page except the last, which gets none).
    - A cover page for the script itself: deck title, a "Speaker script" /
      "発表原稿" kicker, and the date pulled from the deck's own cover spec
      (the first slide whose pattern is "cover"), if present. A navy band,
      matching the report builder's title-band treatment (navy #15296B,
      Georgia headings) -- no decorative bars, no boxes, no left accents.
    - One page per slide: a small muted header line ("N / TOTAL ·
      <headline or title>"), the slide rendered inline as SVG at a reduced
      width (~62% of the page's text column, hairline border top/bottom
      like the report builder's exhibits), then the narration in
      podium-readable type (screen 20px, print ~13.5pt; line-height 1.7,
      1.9 with font-feature-settings 'palt' in --lang ja).
    - Zero external requests, no required JavaScript: the page has none.

Usage:
    python3 scripts/build_speaker_script.py --manifest deck.json -o script.html
    python3 scripts/build_speaker_script.py --manifest deck.json -o script.html --lang ja

Regenerate the committed demo pair (examples/demo-script.html) with:
    python3 scripts/build_speaker_script.py \\
        --manifest templates/decks/board-update-ja/deck.json \\
        -o examples/demo-script.html --lang ja
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


# ---------------------------------------------------------------------------
# Notes normalization
# ---------------------------------------------------------------------------

_BLANK_LINE_RE = re.compile(r"\n\s*\n+")


def notes_paragraphs(notes: object) -> list[str]:
    """Normalize a slide spec's ``notes`` field into a list of paragraphs.

    ``notes`` may be a list of strings (already paragraph-segmented -- each
    item becomes one paragraph) or a single string (segmented into
    paragraphs on blank lines). Anything else -- ``None``, an empty string,
    an empty list, or a value of some other type -- normalizes to ``[]``,
    meaning "no notes"; this function never raises. Internal newlines
    within a single paragraph collapse to a single space (a soft-wrapped
    line reads as one sentence, not a line break), and whitespace-only
    paragraphs are dropped.
    """
    if isinstance(notes, list):
        raw_paragraphs = [str(item) for item in notes]
    elif isinstance(notes, str):
        raw_paragraphs = _BLANK_LINE_RE.split(notes)
    else:
        return []
    paragraphs = []
    for raw in raw_paragraphs:
        collapsed = " ".join(raw.split())
        if collapsed:
            paragraphs.append(collapsed)
    return paragraphs


def _slide_label(spec: dict, spec_path: Path) -> str:
    """The page header's slide identifier: headline, then title, then the
    spec's own filename stem -- mirrors build_html_deck.py's aria-label
    fallback so a structural slide (cover, divider) without a headline
    still gets a sensible label instead of an empty header line."""
    return spec.get("headline") or spec.get("title") or spec_path.stem


_SVG_XMLNS_RE = re.compile(r'\s+xmlns="[^"]*"')


def _strip_xmlns(svg: str) -> str:
    """Drop the root ``<svg>``'s ``xmlns`` attribute before inline embedding:
    required for a standalone .svg file, redundant (and a spurious
    "http://" string) once inlined in an HTML5 document -- same rationale
    and mechanics as build_html_report.py's exhibit embedding."""
    return _SVG_XMLNS_RE.sub("", svg, count=1)


# ---------------------------------------------------------------------------
# Page rendering
# ---------------------------------------------------------------------------

NO_SCRIPT_MARKER = {"en": "(no script)", "ja": "（原稿なし）"}
SCRIPT_KICKER = {"en": "Speaker script", "ja": "発表原稿"}


def _render_slide_page(index: int, total: int, label: str, svg: str, paragraphs: list[str], lang: str) -> str:
    header = f'<p class="page-head">{index} / {total} &middot; {esc(label)}</p>'
    if paragraphs:
        notes_html = "".join(f"<p>{esc(paragraph)}</p>" for paragraph in paragraphs)
    else:
        notes_html = f'<p class="no-notes">{esc(NO_SCRIPT_MARKER[lang])}</p>'
    return (
        '<section class="page slide-page">'
        f"{header}"
        '<div class="duo">'
        f'<figure class="script-slide">{svg}</figure>'
        f'<div class="notes">{notes_html}</div>'
        "</div>"
        "</section>"
    )


def _render_cover_page(deck_title: str, cover_date: str, lang: str) -> str:
    date_html = f'<p class="cover-date">{esc(cover_date)}</p>' if cover_date else ""
    return (
        '<section class="page cover-page">'
        '<div class="cover-inner">'
        f'<p class="cover-kicker">{esc(SCRIPT_KICKER[lang])}</p>'
        f"<h1>{esc(deck_title)}</h1>"
        f"{date_html}"
        "</div>"
        "</section>"
    )


# ---------------------------------------------------------------------------
# Document assembly
# ---------------------------------------------------------------------------

STYLE = """
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
  -webkit-font-smoothing: antialiased;
  -webkit-text-size-adjust: 100%;
}

.page { max-width: 1160px; margin: 0 auto; padding: 48px 32px; border-bottom: 1px solid var(--rule); }
.page:last-child { border-bottom: none; }

/* Cover: a navy band for the script itself, in the report builder's own
   tokens (navy, Georgia) -- no decorative bars, no boxes, no left accents. */
.cover-page { max-width: none; padding: 0; border-bottom: none; background: var(--navy); }
.cover-inner { position: relative; max-width: 760px; margin: 0 auto; padding: 96px 32px; }
.cover-kicker {
  position: absolute; top: 40px; right: 32px;
  font-size: 12px; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase;
  color: #E5E7EB;
}
.cover-inner h1 { font-family: var(--serif); font-weight: normal; font-size: 40px; line-height: 1.3; color: #FFFFFF; max-width: 620px; }
.cover-date { margin-top: 20px; font-size: 16px; color: #E5E7EB; }

.page-head { font-size: 13px; color: var(--muted); letter-spacing: 0.02em; margin-bottom: 20px; }

/* Slide left, narration right -- the field-tested presenter layout
   (current slide on the left, the script as the hero on the right). */
.duo { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(300px, 1fr); gap: 44px; align-items: start; }
.script-slide {
  border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);
  padding: 14px 0;
}
.script-slide svg { display: block; width: 100%; height: auto; }

.notes p { font-size: 20px; line-height: 1.7; margin: 0 0 16px; }
.notes p:last-child { margin-bottom: 0; }
.notes p.no-notes { color: var(--muted); font-style: italic; }
body.lang-ja .notes p { line-height: 1.9; font-feature-settings: 'palt'; }

@media (max-width: 900px) {
  .page { padding: 32px 20px; }
  .cover-inner { padding: 64px 20px; }
  .duo { display: block; }
  .script-slide { margin-bottom: 24px; }
}

@media print {
  /* Landscape so the slide (left) and the script (right) share the page
     the same way they share the presenter screen. */
  @page { size: A4 landscape; margin: 12mm; }
  html, body { background: #FFFFFF; }
  .page { max-width: none; margin: 0; padding: 0; border-bottom: none; break-after: page; page-break-after: always; }
  .page:last-child { break-after: auto; page-break-after: auto; }
  .duo { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10mm; }
  .cover-page {
    -webkit-print-color-adjust: exact; print-color-adjust: exact;
    min-height: 182mm; box-sizing: border-box;
    display: flex; align-items: center;
  }
  .cover-inner { max-width: none; padding: 0; width: 100%; }
  .notes p { font-size: 13.5pt; }
  .script-slide, .notes p { break-inside: avoid; page-break-inside: avoid; }
}
"""


def build_script(spec_paths: list[Path], deck_title: str, lang: str = "en") -> str:
    """Build the speaker-script HTML from an ordered list of slide spec paths.

    ``lang`` selects the narration language furniture ("Speaker script" /
    "発表原稿" kicker, the missing-notes marker, ja line-height); an
    unrecognized value falls back to "en" rather than raising.
    """
    lang = lang if lang in ("en", "ja") else "en"
    total = len(spec_paths)

    cover_date = ""
    pages: list[str] = []
    for index, spec_path in enumerate(spec_paths, start=1):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        if not cover_date and spec.get("pattern") == "cover":
            cover_date = str(spec.get("date", ""))
        svg = _strip_xmlns(_renderer.render(spec))
        label = _slide_label(spec, spec_path)
        paragraphs = notes_paragraphs(spec.get("notes"))
        pages.append(_render_slide_page(index, total, label, svg, paragraphs, lang))

    cover_html = _render_cover_page(deck_title, cover_date, lang)
    body_class = ' class="lang-ja"' if lang == "ja" else ""
    lang_attr = "ja" if lang == "ja" else "en"

    return f"""<!DOCTYPE html>
<html lang="{lang_attr}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(deck_title)}</title>
<style>{STYLE}</style>
</head>
<body{body_class}>
{cover_html}
{''.join(pages)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a self-contained, print-first speaker script from a slide deck manifest."
    )
    parser.add_argument(
        "--manifest", required=True, help="Deck manifest JSON with {title, slides} (same format as build_html_deck.py)"
    )
    parser.add_argument("-o", "--output", required=True, help="Output HTML path")
    parser.add_argument(
        "--lang", choices=("en", "ja"), default="en", help="Speaker-script narration language (default: en)"
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
        print("ERROR: manifest must include a non-empty 'slides' list", file=sys.stderr)
        raise SystemExit(1)

    base = manifest_path.parent
    spec_paths = [base / p for p in slides]
    for path in spec_paths:
        if not path.exists():
            print(f"ERROR: spec not found: {path}", file=sys.stderr)
            raise SystemExit(1)

    title = manifest.get("title", "Slide Deck")
    html = build_script(spec_paths, title, args.lang)

    output_path = Path(args.output)
    output_path.write_text(html, encoding="utf-8")
    print(f"OK: built {len(spec_paths)}-page speaker script at {output_path}")


if __name__ == "__main__":
    main()
