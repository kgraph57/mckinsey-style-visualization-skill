# Roadmap

## Shipped in v2.0.0 — Full Presentation System

- **Six structural slide patterns**: `section_divider`, `end_cover`, `agenda`, `bullet_list`, `closing`, `quote` — the deck furniture beyond charts. 16 → 22 rendered patterns; every slide of a real deck is now renderable.
- **Deck templates + scaffolder**: six ready-made deck archetypes (`board-update`, `strategy-recommendation`, `project-status`, `market-entry`, `sales-proposal`, `board-update-ja`) under `templates/decks/`, plus `scripts/scaffold_deck.py` so the path is pick template → swap data → one command → animated HTML deck / PDF.
- **A4 / report-canvas rendering — done for the report profile**: `scripts/build_html_report.py` renders Markdown natively to a single self-contained, print-to-A4 HTML document with numbered exhibits. Vertical infographic and other non-16:9 profiles remain spec-only, disclosed, and are tracked in Next Up below.

## Next Up

- **Native PPTX export**: optional `scripts/export_pptx.py` that writes OOXML directly (stdlib zip + XML) embedding the SVG slides with `svgBlip` plus an optional raster fallback. Ship only with a verification path (LibreOffice round-trip in CI) so the exporter can never claim more than it renders.
- **Video export**: turn the HTML deck into a short mp4/GIF via a headless browser recipe for social sharing.
- **Vertical / square canvas rendering**: extend beyond 16:9 and the report profile's A4 so infographic and social-card profiles render natively too (currently spec-only, disclosed).

## Phase 1: Marketplace Readiness

- Keep `SKILL.md` portable and concise.
- Maintain references, examples, security notes, changelog, and validation.
- Add visual proof assets when screenshots or rendered examples are available.
- Tag releases and publish clear release notes.

## Phase 2: Proof Gallery

- Add rendered examples for the highest-value patterns:
  - board update waterfall
  - competitive benchmark table
  - market map 2x2
  - investment scale comparison
  - executive summary strip
- Add before/after prompt comparisons showing why the skill improves agent output.
- Expand the iterative review-loop examples across pricing strategy, M&A screening, cost transformation, and product portfolio scenarios.

## Phase 3: Premium Template Pack

The v2.0.0 archetype scaffolder (`templates/decks/` + `scripts/scaffold_deck.py`) is the generic precursor to this phase — six deck shapes, not yet industry-specific.

- Package industry-specific templates:
  - SaaS board update
  - healthcare market analysis
  - AI vendor benchmark
  - private equity investment memo
  - product strategy review
- Add commercial licensing notes if monetization begins.

## Phase 4: Renderer Integration

- Define a stable JSON slide-spec schema. — done: the spec shape is stable across 22 rendered patterns and is what `scripts/scaffold_deck.py` copies verbatim.
- Add exporters or adapters for HTML, PPTX, or image-generation workflows. — HTML done (`scripts/build_html_deck.py`, `scripts/build_html_report.py`); PPTX still open, tracked in Next Up.
- Add regression examples for visual consistency.

## Phase 5: SaaS Exploration

- Test demand for a web workflow:
  - paste data
  - choose decision type
  - generate slide spec
  - render to PPTX or image
- Keep the skill package as the distribution wedge even if a SaaS product emerges.
