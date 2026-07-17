#!/usr/bin/env python3
"""Build a self-contained animated HTML slide deck from slide spec JSON files.

Each spec is rendered to SVG with scripts/render_slide_spec.py and embedded
inline, so the output is a single HTML file with zero external requests and
zero dependencies. Slides animate in with a quiet staggered reveal; printing
the page produces one slide per page (browser print -> PDF export).

Usage:
    python3 scripts/build_html_deck.py spec1.json spec2.json -o deck.html --title "Q4 Review"
    python3 scripts/build_html_deck.py --manifest deck.json -o deck.html

Manifest format:
    {"title": "Q4 Review", "slides": ["specs/cover.json", "specs/bridge.json"]}

Navigation: arrow keys, space, click on the right/left third of the slide,
or the dots in the footer. Press "p" (or use the browser's print dialog)
to export to PDF.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_renderer():
    module_path = ROOT / "render_slide_spec.py"
    spec = importlib.util.spec_from_file_location("render_slide_spec", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ELEMENT_TAGS = ("<rect", "<text", "<line", "<polyline", "<circle", "<path")

# Quiet reveal: cap the stagger so long slides do not crawl.
STAGGER_STEP_MS = 28
STAGGER_MAX_MS = 1100


def animate_svg(svg: str) -> str:
    """Tag each top-level SVG element with a capped, staggered reveal delay.

    The renderer emits one element per line, so line-level tagging is safe.
    The background rect (first element) is left static to avoid a white flash.
    """
    out_lines: list[str] = []
    index = 0
    for line in svg.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(ELEMENT_TAGS):
            if index > 0:  # keep the background rect static
                delay = min((index - 1) * STAGGER_STEP_MS, STAGGER_MAX_MS)
                tag_end = line.index(stripped.split()[0]) + len(stripped.split()[0])
                line = f'{line[:tag_end]} class="el" style="animation-delay:{delay}ms"{line[tag_end:]}'
            index += 1
        out_lines.append(line)
    return "\n".join(out_lines)


STYLE = """
:root { color-scheme: light; }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { height: 100%; background: #0B1220; }
body { font-family: 'Helvetica Neue', Helvetica, Arial, 'Noto Sans JP', 'Hiragino Sans', sans-serif; }
.deck { position: relative; height: 100%; display: flex; align-items: center; justify-content: center; }
.slide {
  position: absolute; inset: 0; display: none; align-items: center; justify-content: center;
  padding: 24px;
}
.slide.active { display: flex; }
.frame {
  width: min(96vw, calc(96vh * 16 / 9)); aspect-ratio: 16 / 9;
  box-shadow: 0 24px 80px rgba(0, 0, 0, 0.55); border-radius: 6px; overflow: hidden; background: #fff;
}
.frame svg { display: block; width: 100%; height: 100%; }
.slide.active .frame { animation: slidein 480ms cubic-bezier(0.22, 1, 0.36, 1) both; }
.slide.active svg .el { opacity: 0; animation: reveal 420ms ease-out both; }
@keyframes slidein { from { opacity: 0; transform: translateY(14px) scale(0.992); } to { opacity: 1; transform: none; } }
@keyframes reveal { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) {
  .slide.active .frame, .slide.active svg .el { animation: none; opacity: 1; }
}
.hud {
  position: fixed; left: 0; right: 0; bottom: 0; display: flex; align-items: center; gap: 14px;
  padding: 12px 20px; color: #93A3BC; font-size: 12px; user-select: none;
}
.hud .dots { display: flex; gap: 7px; }
.hud .dot { width: 7px; height: 7px; border-radius: 50%; background: #33415C; cursor: pointer; border: 0; padding: 0; }
.hud .dot.on { background: #E5E7EB; }
.hud .counter { margin-left: auto; font-variant-numeric: tabular-nums; letter-spacing: 0.06em; }
.progress { position: fixed; top: 0; left: 0; height: 2px; background: #E5E7EB; width: 0; transition: width 240ms ease; }
@media print {
  html, body { background: #fff; height: auto; }
  .hud, .progress { display: none; }
  .slide { display: block !important; position: static; padding: 0; page-break-after: always; break-after: page; }
  .frame { width: 100%; box-shadow: none; border-radius: 0; }
  .slide svg .el, .slide .frame { opacity: 1 !important; animation: none !important; }
}
"""

SCRIPT = """
(function () {
  var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var dots = Array.prototype.slice.call(document.querySelectorAll('.dot'));
  var bar = document.querySelector('.progress');
  var counter = document.querySelector('.counter');
  var current = Math.min(Math.max((parseInt(location.hash.slice(1), 10) || 1) - 1, 0), slides.length - 1);
  function show(index) {
    current = Math.min(Math.max(index, 0), slides.length - 1);
    slides.forEach(function (slide, i) {
      slide.classList.toggle('active', i === current);
      if (i === current) {
        // restart the reveal animation on revisit
        slide.querySelectorAll('.el').forEach(function (el) {
          el.style.animation = 'none';
          void el.getBoundingClientRect();
          el.style.animation = '';
        });
      }
    });
    dots.forEach(function (dot, i) { dot.classList.toggle('on', i === current); });
    bar.style.width = (100 * (current + 1) / slides.length) + '%';
    counter.textContent = (current + 1) + ' / ' + slides.length;
    history.replaceState(null, '', '#' + (current + 1));
  }
  document.addEventListener('keydown', function (event) {
    if (event.key === 'ArrowRight' || event.key === ' ' || event.key === 'PageDown') { show(current + 1); event.preventDefault(); }
    if (event.key === 'ArrowLeft' || event.key === 'PageUp') { show(current - 1); event.preventDefault(); }
    if (event.key === 'Home') show(0);
    if (event.key === 'End') show(slides.length - 1);
    if (event.key === 'p') window.print();
  });
  document.querySelector('.deck').addEventListener('click', function (event) {
    if (event.target.closest('.hud')) return;
    var x = event.clientX / window.innerWidth;
    show(x < 0.33 ? current - 1 : current + 1);
  });
  dots.forEach(function (dot, i) { dot.addEventListener('click', function () { show(i); }); });
  show(current);
})();
"""


def build_deck(spec_paths: list[Path], title: str) -> str:
    renderer = load_renderer()
    sections: list[str] = []
    dots: list[str] = []
    for i, spec_path in enumerate(spec_paths):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        svg = animate_svg(renderer.render(spec))
        label = spec.get("headline") or spec.get("title") or spec_path.stem
        sections.append(
            f'<section class="slide" aria-label="{renderer.esc(label)}"><div class="frame">\n{svg}\n</div></section>'
        )
        dots.append(f'<button class="dot" aria-label="Slide {i + 1}"></button>')
    body = "\n".join(sections)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{renderer.esc(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="progress"></div>
<main class="deck">
{body}
</main>
<footer class="hud">
  <div class="dots">{''.join(dots)}</div>
  <span>&#8592; &#8594; navigate &middot; p = print / PDF</span>
  <span class="counter"></span>
</footer>
<script>{SCRIPT}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an animated HTML deck from slide spec JSONs.")
    parser.add_argument("specs", nargs="*", help="Slide spec JSON files, in slide order")
    parser.add_argument("--manifest", help="Deck manifest JSON with {title, slides}")
    parser.add_argument("--title", default="Slide Deck", help="Deck title (browser tab)")
    parser.add_argument("-o", "--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    title = args.title
    spec_paths = [Path(p) for p in args.specs]
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        title = manifest.get("title", title)
        base = Path(args.manifest).parent
        spec_paths = [base / p for p in manifest["slides"]] + spec_paths
    if not spec_paths:
        print("ERROR: no slide specs given", file=sys.stderr)
        raise SystemExit(1)
    for path in spec_paths:
        if not path.exists():
            print(f"ERROR: spec not found: {path}", file=sys.stderr)
            raise SystemExit(1)

    html = build_deck(spec_paths, title)
    output = Path(args.output)
    output.write_text(html, encoding="utf-8")
    print(f"OK: built {len(spec_paths)}-slide deck at {output}")


if __name__ == "__main__":
    main()
