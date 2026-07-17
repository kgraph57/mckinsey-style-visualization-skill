# Changelog

## Unreleased

## 1.9.0 - 2026-07-17 - Design-Panel Review Hardening

### Animated HTML decks and README relaunch

- Added `scripts/build_html_deck.py` (stdlib-only): combines slide specs into a single self-contained HTML deck — staggered element reveals with `prefers-reduced-motion` support, keyboard/click navigation, progress bar, deep links, and a print stylesheet that exports one slide per page to PDF. No external requests; SVGs, styles, and scripts are inline.
- Committed a six-slide demo deck (`examples/demo-deck.json` → `examples/demo-deck.html`) and an animated README demo (`assets/readme/demo.gif`) generated from real renderer output.
- Added a committed Japanese board-summary example (`jp-board-summary`) proving CJK wrapping, classification markers, and page furniture in a rendered slide.
- Extended `scripts/validate_skill.py`: the committed demo deck must match a fresh build from its manifest (same drift protection the rendered SVGs already have), plus required-file coverage for the new assets.
- Added `tests/test_build_html_deck.py` (deck structure, self-containment, animation caps, static background rule); suite now 28 tests.
- Rewrote README.md and README.ja.md around show-don't-tell: animated hero GIF, verified gallery, 60-second start, HTML-deck/PDF/PowerPoint export paths, the five-perspective design-panel story, and honest 16-rendered/12-spec-only framing; commercial documents moved into a collapsed details section.

## 1.9.0 - 2026-07-17 - Design-Panel Review Hardening

Fixes and additions from an independent, five-perspective design review (Edward Tufte; Gene Zelazny; Vignelli × Müller-Brockmann; Alan Smith / FT; a modern design engineer). The panel scored the package 5.8/10 on average with a unanimous “conditional yes”; this release clears the blockers they raised.

### Renderer integrity
- **Waterfall integrity**: bars now scale to the full cumulative range with a zero floor, so negative-running bridges (large churn, impairments) stay inside the chart band instead of drawing past the canvas; the zero baseline carries an explicit "0" tick; negative currency renders `-$4`, not `$-4`.
- **CJK text support**: `wrap()` measures fullwidth characters as double width and breaks CJK runs per character, so Japanese headlines and labels wrap instead of overflowing the 1280px canvas; unbreakable ASCII tokens (URLs, cert codes) hard-break instead of overflowing.
- **No silent truncation**: clamped text now ends with an ellipsis (…) and keeps the full string in an SVG `<title>` element; benchmark-table row labels and cell values wrap instead of colliding across columns.
- **Slide furniture**: optional `page_number`, `classification`, and `footnotes` spec fields render as standard board-deck furniture.

### Palette and accessibility
- **Palette re-derived**: single navy `#15296B` across content accents and cover backgrounds (replaces the two unrelated navies `#1E3A8A`/`#1E3A5F`, both Tailwind-default-adjacent); the new primary accent stays distinguishable from dark-grey text in greyscale print (relative-luminance ratio ≥ 1.5, asserted in tests); removed the gold-on-navy premium accent as a self-violation of the anti-pattern list.
- **Heatmap honesty and accessibility**: signed data automatically switches to a diverging ramp anchored at zero (blue positive, red negative); cell text color is chosen by measured WCAG contrast, keeping every tone ≥ 4.5:1 (asserted across the full ramp in tests).

### Ink discipline and honesty
- **Data-ink discipline**: removed the decorative annotation accent bar and per-block kicker bars (the headline kicker is now the single sanctioned motif); before/after legend swatches replaced with direct labels on the first pair; zero ticks added to zero-based charts.
- **Renderer scope honesty**: pattern tables in `references/visualization-patterns.md` now mark each pattern ✓ SVG or spec-only; SKILL.md, README, and the rubric say plainly that 16 patterns render on a 16:9 canvas and everything else is spec-only.

### New rendered patterns
- **Four new rendered patterns**: `scatter`, `distribution`, `small_multiples` (shared-scale sparkline grid — the high-density counterpart to one-message slides), and `cover` (navy title slide), with example specs, committed SVGs, and validation.

### Method, rubric, and docs
- **Message discipline**: added a comparison-type gate (component / item / time series / distribution / correlation) ahead of pattern selection; headline rule tightened to a single proposition (the flagship executive-summary example was itself violating it and has been rewritten); added a deck-level headline pyramid check to the rubric.
- **Rubric**: new "Data-Ink and Graphical Integrity" axis (Lie Factor, decoration test, marked baselines, visible truncation); total now 24 points with rescaled thresholds.
- **Style-system as source of truth**: documented design tokens (8px grid, margins, chart band, fixed type scale) that match the renderer constants; named the full font stacks including Japanese fallbacks; added a Japanese typography section (leading, per-character wrapping, line-break etiquette).

### Also in this release (previously unreleased)
- Added an `Emphasis Hierarchy` section to `references/style-system.md`: a ranked fill > line > text strength ladder mapped to existing palette tokens, with discipline rules against undisciplined highlighting; reinforced it in the `references/quality-rubric.md` Visual Hierarchy axis.
- Added `unittest` coverage for renderer errors, SVG escaping, zero-value funnel conversions, and stale committed SVG detection.
- Added `references/expert-review-loop.md` and bias/usability warnings so public outputs challenge assumptions, overclaims, reader fit, accessibility, and localization risk.
- Added expert review notes to the board-update proof example and safer first-use prompts to README, README.ja.md, and QUICKSTART.md.
- Improved `scripts/review_slide_spec.py` so it recognizes both `## Section` headings and bold-label proof examples such as `**Strategic question:**`.
- Added GitHub Actions CI for unit tests, package validation, Python compile checks, and whitespace checks; exposed it in README badges and marketplace operations metadata.
- Hardened `scripts/render_slide_spec.py` with structured `RenderSpecError` failures, time-series label validation, benchmark/heatmap shape validation, and safe `n/a` funnel conversions when the prior stage is zero.
- Strengthened `scripts/validate_skill.py` so committed rendered SVG examples must match fresh renderer output.
- Aligned `SKILL.md` frontmatter with portable skill discovery by keeping only `name` and `description`; license remains in `LICENSE` and `marketplace/manifest.json`.
- Refined README positioning for star conversion and corrected stale renderer pattern counts from 7 to 12.

## 1.8.0 - Persona Packs and Renderer Expansion

- Added `references/persona-playbook.md`: role-based entry points for sales, marketing, product, PMO, HR, engineering, research, finance, and executives with copy-paste prompts and rendered examples.
- Expanded the renderer from 7 to 12 patterns: added `funnel`, `heatmap`, `gantt`, `kpi_scorecard`, and `two_by_two`.
- Added 7 persona render specs and their committed SVG outputs (sales funnel, marketing heatmap, product 2x2, PMO gantt, HR scorecard, incident flow, research before-after).
- Added Japanese business document profiles (稟議書, 週報・月報, 役員会資料, 学会抄録・抄読会, 社内勉強会, 提案書) to `references/document-type-profiles.md`.
- Added "By Role" sections to README and README.ja.md; updated manifest and validator for v1.8.0.

## 1.7.0 - Renderer and Hero Demo

- Added `scripts/render_slide_spec.py`: renders spec JSON into styled SVG slides for seven patterns (waterfall, gap, before_after, time_series, benchmark_table, summary_strip, process_flow) using only the Python standard library.
- Added seven sample render specs in `examples/render-specs/` and their committed SVG outputs in `assets/rendered/`.
- Added a hero before/after image to the README showing raw notes turning into a rendered board slide.
- Added `README.ja.md` with a Japanese quickstart and rendered gallery.
- Added a 30-second quickstart and rendered output gallery to the README.
- Referenced optional rendering in the `SKILL.md` workflow; updated manifest, validator, and growth checklist for v1.7.0.

## 1.6.0 - Universal Visualization

- Generalized the skill beyond board slides to any document type: reports, research summaries, proposals, project status updates, training materials, technical documentation, one-pagers, infographics, policy briefs, and study notes.
- Added `references/input-triage.md` so any input — numbers, prose, processes, hierarchies, relationships, decision logic, qualitative arguments — maps to a visualization pattern family.
- Added `references/document-type-profiles.md` with 12 document profiles covering canvas, density, tone, and preferred patterns per deliverable.
- Expanded `references/visualization-patterns.md` with 16 universal patterns: process flow, funnel, cycle, hierarchy, pyramid, concept map, Gantt/roadmap, heatmap, scatter, distribution, stacked composition, KPI scorecard, decision tree, Sankey-style flow, maturity grid, and annotated map.
- Added a format-agnostic Universal Visual Spec, a Diagram-as-Code (Mermaid) spec, and nine new pattern starters to `references/prompt-templates.md`.
- Added multi-canvas guidance (16:9, A4 portrait, vertical infographic, square, inline figure) to `references/style-system.md`.
- Updated `SKILL.md` workflow with input triage and document-profile steps, and updated manifest and validator for v1.6.0.

## 1.5.0 - Traction and Inquiry Readiness

- Added `TRACTION.md` for weekly demand-signal tracking and acquisition data-room preparation.
- Added marketplace listing, example request, buyer inquiry, and bug report issue templates.
- Added pull request template with validation and marketplace-readiness checks.
- Linked traction tracking from README, launch, distribution, buyer, and commercialization docs.
- Updated manifest and validator for v1.5.0 operations readiness.

## 1.4.0 - Launch and Buyer Readiness

- Added launch copy, social-card asset, and a 7-day launch plan.
- Added marketplace target list with priority, URLs, submission angles, and a listing tracker.
- Added buyer brief for acquisition-facing diligence and positioning.
- Updated distribution, submission, marketplace, README, manifest, and validator references for launch readiness.

## 1.3.0 - Distribution and Review Loop Expansion

- Added public reference corpus for studying executive-report patterns without copying source material.
- Added iterative draft-review-revise loop for polished executive slide specs.
- Added `scripts/review_slide_spec.py` for lightweight structural review.
- Added review-loop examples showing a draft improving from revise to pass.
- Expanded review-loop examples across board update, vendor selection, investment memo, and market entry scenarios.
- Added distribution, submission, and commercialization docs for marketplace testing.

## 1.2.0 - Marketplace Readiness

- Repositioned the package as Strategy Consulting Visualization Skill.
- Rewrote `SKILL.md` as a concise portable entrypoint.
- Added progressive reference files for visual system, patterns, templates, and quality scoring.
- Added marketplace listing draft and speculative manifest.
- Added security policy, roadmap, proof examples, and validation script.
- Corrected stale installation URLs.
- Added non-affiliation disclaimer for marketplace and diligence readiness.

## 1.1.0 - Cover Slide Expansion

- Added cover slide guidance.
- Added detailed color palette and typography notes.
- Added cover slide prompt template.

## 1.0.0 - Initial Skill

- Added consulting-style visualization guidance.
- Added core visualization types and prompt templates.
- Added initial README, installation guide, quickstart, examples, and contribution guide.
