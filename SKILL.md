---
name: strategy-consulting-visualization
description: Use when turning content into clear strategy-consulting visualizations, including board slides, reports, diagrams, quiet animated decks, or explicit dynamic and interactive decks with clickable evidence, scenario controls, what-if sliders, and deterministic presenter demos.
---

# Strategy Consulting Visualization

## Purpose

Use this skill to turn any content into professional visualization specs with strategy-consulting clarity: insight-led headlines, disciplined layout, accurate data, restrained design, and explicit implications. It covers board slides first, and generalizes to reports, proposals, training materials, technical diagrams, infographics, and any input that benefits from visual structure.

## Fast Path

Skip the pattern-by-pattern build when the user just wants a complete, real deck or document immediately.

**Full deck** — scaffold a ready-made archetype from `templates/decks/`, then fill in the illustrative placeholders with real data:

```bash
python3 scripts/scaffold_deck.py --list                       # 6 archetypes with slide counts
python3 scripts/scaffold_deck.py board-update -o my-deck       # copies deck.json + specs/
# edit my-deck/specs/*.json with real data, keeping the pattern shapes intact
python3 scripts/build_html_deck.py --manifest my-deck/deck.json -o my-deck/deck.html
```

**Click-through motion presentation** — when the reader should enter a page
from an overview, press the exhibit or its main number for supporting detail,
and verify the claim through an operation, use the story-led presentation
route. This is the preferred route for a reference-led request for うちた-style
動く資料 or クリックで深掘り. Read `references/motion-story.md` and author a
small `motion.json`; the six-page Japanese example demonstrates the components:

```bash
python3 scripts/build_motion_deck.py --manifest examples/interactive-deck/motion.json -o deck.motion.html
python3 scripts/build_motion_deck.py --manifest examples/interactive-deck/motion.json --static -o deck.motion.static.html
```

The opening is a navigable argument, followed by evidence-led pages with one
primary operation each. Exhibits and prominent numbers open a source-bearing
drawer; classification sorts, comparison retains the prior shape, a slider
recalculates the displayed formula, actions fill a gap, and a timeline advances
through real decisions. Review the entire flow and run the visible cursor demo
through its ending in the page overview. A single redesigned comparison page
does not satisfy a request for this whole-deck experience.

**Contract-backed interactive companion** — “animated” alone keeps the classic quiet-
reveal path above. An explicit request for an interactive/dynamic deck, 動く・
動的スライド, clickable evidence, what-if recalculation, a slider, drill-down,
or auto-demo builds the classic artifact first and then a companion from the
same manifest:

```bash
python3 scripts/build_html_deck.py --manifest my-deck/deck.json -o my-deck/deck.html
python3 scripts/build_interactive_deck.py --manifest my-deck/deck.json -o my-deck/deck.interactive.html
```

Before adding a scene, use `references/interaction-selection.md`. Author the
closed scene contract with `references/interactive-scene-schema.md`, review
`references/interactive-accessibility.md`, and hand off with
`references/presenter-operation.md`. Always report both paths. The interactive
artifact never replaces the static/print baseline.

**Document** — write Markdown (with `spec:`/`svg:` exhibit references where a chart belongs) and build it straight to a browser-ready, print-to-A4 HTML report:

```bash
python3 scripts/build_html_report.py my-report.md -o my-report.html --lang en
```

`templates/reports/` has three starting points (board pre-read, one-pager, proposal memo).

**Speaker script** — the podium version of any deck: add a top-level `"notes"` field (a string, or a list of paragraph strings) to the slides that need narration, then build a print-first, one-slide-per-page HTML script with the narration set below each slide. The renderer ignores `notes` entirely, so adding it never changes the rendered slide, and a slide with no notes still gets its own page with a muted "no script" marker.

```bash
python3 scripts/build_speaker_script.py --manifest my-deck/deck.json -o my-deck/script.html --lang en
```

**Deck as an article** — the same deck read top-to-bottom on a single 680px reading column instead of click-through slides or a side-nav document: a paper-first hero (kicker/lead from the manifest's optional `series`/`lead` keys), then each slide's SVG followed by its `notes` as reading prose, with optional per-slide `label`/`refs` fields adding a section tag and a "Links" aside that rolls up into an end-of-article links section.

```bash
python3 scripts/build_html_article.py --manifest my-deck/deck.json -o my-deck/article.html --lang en
```

All classic fast paths and the optional interactive companion still obey the style system and quality rubric below — they only skip writing specs from a blank page. Fall back to the full workflow for anything the templates don't already cover.

## Use When

- The user needs a board slide, executive memo visual, market map, competitor benchmark, investment view, performance bridge, or strategic timeline.
- The user needs visuals for any other document: internal reports, research summaries, sales proposals, project status updates, training or education materials, technical documentation, one-pagers, infographics, or study notes.
- The user has raw data, prose, notes, a process description, or a question and needs a visual direction — even if they only say "visualize this".
- The user asks for McKinsey-style, BCG-style, Bain-style, consulting-style, boardroom-ready, executive-ready, or strategy-deck visuals.
- The output should feel like a top-tier professional deliverable without implying affiliation with any consulting firm.

## Do Not Use When

- The user wants decorative art with no informational content, brand campaigns, or low-density inspirational visuals.
- The user needs regulated financial, medical, or legal conclusions without source verification.
- The user asks for a final rendered chart but has not provided enough data to check labels, scales, and claims.

## Workflow

1. Identify the decision, question, or job the visual should support for its reader.
2. If the input is not an obvious chart request, triage it with `references/input-triage.md` to map any input type to a pattern family.
3. Pick the document profile from `references/document-type-profiles.md` to set canvas, density, and tone.
4. Convert the request into an insight-led headline that answers the reader's question. The headline must be a single proposition — one answer or one tension, never several claims joined by "and".
   For an explicit interactive request, write the title-only storyboard first and add `Evidence`, `Main interaction`, `May change`, and `Must not change`. Reject any interaction that does not improve verification, insight, action, a decision, or evidence retrieval. See `references/interaction-selection.md`.
5. Select the visualization pattern from `references/visualization-patterns.md`, starting from the comparison-type gate at the top of that file. Structural patterns (`section_divider`, `agenda`, `bullet_list`, `closing`, `quote`, `end_cover`, `cover`) are deck furniture, not the argument — use them for connective tissue between slides (opening, orienting, transitioning, closing) and spend the insight-headline discipline on the content slides they connect.
6. Apply the visual system in `references/style-system.md`, using the canvas from the document profile. Write copy to its Word Budget: when text does not fit, cut words or split the slide — never shrink type.
7. Produce a structured spec, diagram-as-code source, or image-generation prompt using `references/prompt-templates.md`.
   When the environment allows running scripts, render supported patterns to SVG with `python3 scripts/render_slide_spec.py <spec.json>`. Twenty-two patterns render (cover, section_divider, end_cover, agenda, bullet_list, closing, quote, waterfall, gap, before_after, time_series, benchmark_table, summary_strip, process_flow, funnel, heatmap, gantt, kpi_scorecard, two_by_two, scatter, distribution, small_multiples), on a 16:9 canvas only; every other pattern and canvas is spec-only. `cover`, `section_divider`, and `end_cover` are full-bleed navy and skip the header/footer chrome; every other renderable pattern uses the standard white content chrome. Tell the user which they are getting — never imply a spec-only pattern will render. Spec examples are in `examples/render-specs/`.
8. Score the output against `references/quality-rubric.md`. For decks, also run its deck-level headline check.
   Inspect every rendered page at intended viewing size. A test pass or contact sheet alone is not completion. Numerical assertions need proportional visual evidence: bars for magnitude, a full model line and gate for a threshold, and contributions or a counterfactual for an additive score. Do not substitute a list of numbers, equal-width bands, or an isolated dot for that proof.
   For an interactive companion, validate the scene, inspect live and declared static states, run the author audit, and keep every unperformed manual/physical check explicit. See `references/interactive-accessibility.md` and `references/presenter-operation.md`.
9. Flag missing data, unverifiable claims, source-sensitive assumptions, or trademark-sensitive wording.
10. For public, high-stakes, cross-functional, or broad-audience work, run `references/expert-review-loop.md` to remove blind spots, overclaims, jargon, accessibility issues, and cultural assumptions.
11. For polished executive work, run the draft through `references/iterative-review-loop.md` until the output reaches the stopping criteria.

## Output Contract

Return a concise deliverable with:

- `Strategic question` (or the reader's key question for non-strategy documents)
- `Insight headline`
- `Recommended visualization`
- `Slide spec` (or figure, page, or diagram spec matching the document profile)
- `Data and assumptions`
- `Quality check`
- `Expert review notes` when the output is public, high-stakes, cross-functional, or broad-audience

When the user requests a batch, deck, or multi-figure document, repeat the contract per visual and add a brief flow summary explaining how the visuals build the argument.

## Reference-led reproduction

When the user requests a particular firm's style or supplies a reference, read `references/reference-reproduction.md` before selecting a theme. Consult `references/consulting-reference-evidence.json` and inspect the specific source page. Record geometry, hierarchy, chart encoding, notes and deviations. Choose presentation, analytical pre-read, or reading document explicitly. Do not claim exact fidelity from a colour preset alone. The worked examples are in `templates/reference-layouts/`.

## Default Visual Standards

- For business presentation requests, prefer `"theme": "executive"` consistently across the deck: sans-serif headlines, neutral comparison marks, and navy for the main outcome. In a metric-led summary, use `focus_block` only for the single decision-critical column. For diagrams, keep executive process flows to five steps with optional owner/duration fields and priority matrices to six numbered options; split denser content across slides. See `references/style-system.md` for the supported options; retain `classic` when the user requests serif styling.

- Slides render to 16:9. Supported chart/diagram patterns also render compact document exhibits with `--exhibit`; arbitrary canvases remain spec-only. HTML reports support A4 briefing/editorial layouts with editable captions and sources. Optional `scripts/build_briefing_docx.cjs` creates editable A4 Word briefs and requires Node packages `docx` and `sharp`.
- White content slides with black text, a single navy accent (`#15296B`), and grey hierarchy.
- Navy full-bleed slides only when opening a deck (`cover`), opening a section (`section_divider`), or closing a deck (`end_cover`) — never for a content slide.
- Classic uses serif headlines; executive and analytical content use sans-serif headlines. A reference-led request takes precedence over these defaults.
- High information density with clear hierarchy; no decorative clutter.
- All numbers must be visible, consistently formatted, and tied to the user's data or cited assumptions.
- Keep action titles self-contained; omit subtitles that merely restate the title. Preserve the fixed title baseline and a clear gap before the exhibit.
- Presentation body copy uses 26px and primary exhibit labels 22px on the 1280 × 720 canvas. Reduce content or split the page before reducing these sizes.
- Interactive desktop slides are one composition: exhibit, inputs and decision visible together at 1280 × 720 and 1440 × 900. Hide redundant semantic copies visually while retaining accessible equivalents. Narrow screens reflow; never shrink the entire interface into unreadable text.
- Choose control placement for the argument, not a fixed dashboard template. For a small scenario comparison, retain the reference state beside the changing state and place the selector near the comparison. A rank bridge encodes ordinal position; label the scores directly rather than implying its slope measures score change. Emphasize the decision-changing item and keep supporting actions visually secondary.
- Check the decision sequence across the deck. A gated action cannot precede its review, and “approve today” must not conflict with a later conditional decision.

## Marketplace Safety

This skill is not affiliated with, endorsed by, or sponsored by McKinsey & Company, Boston Consulting Group, Bain & Company, or any other consulting firm. Use category language such as "strategy consulting visualization" in user-facing outputs unless the user specifically asks for comparative style references.

Do not invent client names, confidential labels, benchmark data, or source citations. If a visual depends on uncertain or missing data, mark the assumption explicitly in `Data and assumptions`.

## Reference Files

- `references/motion-story.md` for the story-led motion presentation builder,
  six component contracts, whole-deck navigation and direct evidence access.

- `references/consulting-design-study.md` for the six-firm page-level design study.
- `references/reference-reproduction.md` for measured reproduction, supported routes and fidelity review.

- `references/persona-playbook.md` for role-based entry points (sales, marketing, product, PMO, HR, engineering, research, finance, executive) with prompts and example specs.
- `references/input-triage.md` for mapping any input — numbers, prose, processes, ideas — to a pattern family.
- `references/document-type-profiles.md` for adapting format, density, and tone to slides, reports, proposals, training materials, technical docs, and infographics.
- `references/visualization-patterns.md` for pattern selection and use cases.
- `references/style-system.md` for palette, typography, spacing, and layout rules.
- `references/prompt-templates.md` for slide specs and image-generation prompts.
- `references/quality-rubric.md` for final scoring and marketplace-quality checks.
- `references/expert-review-loop.md` for challenging assumptions, overclaims, accessibility, localization, and audience-fit risks.
- `references/public-reference-corpus.md` for public executive-report sources to study without copying.
- `references/iterative-review-loop.md` for draft, review, revise, and score cycles.
- `references/interaction-selection.md` for the classic/animated/interactive routing boundary and the static-first deletion gate.
- `references/interactive-scene-schema.md` for the six scenes, model/control/view matrix, exact values, lineage, and build commands.
- `references/interactive-accessibility.md` for semantic, focus, compact, print, automated, and manual review obligations.
- `references/presenter-operation.md` for live controls, demo, safe links, offline use, printing, and the physical-device checklist.
- `templates/decks/` and `scripts/scaffold_deck.py` for ready-made deck archetypes (`--list` to see all six).
- `templates/reports/` and `scripts/build_html_report.py` for Markdown-to-report documents with numbered exhibits.
- `scripts/build_speaker_script.py` for a print-first, one-slide-per-page podium script built from a deck's `notes` field.
- `scripts/build_html_article.py` for reading the same deck top-to-bottom as a single web-page article, slide by slide with its `notes` as prose.

## HTML to PDF

Use JSON for charts and Markdown for the narrative. Generate HTML, review it in the browser, and export that same HTML to PDF. HTML is the primary layout artifact; Word is an optional separate export. Reports use A4 print styles; decks use one 16:9 slide per page.

```bash
python3 -m pip install playwright
python3 scripts/build_html_report.py templates/reference-layouts/decision-brief.md -o brief.html
python3 scripts/export_pdf.py brief.html -o brief.pdf
python3 scripts/export_pdf.py examples/demo-deck.html -o deck.pdf
```

PDF export requires installed Google Chrome or Chromium (`--browser /path/to/browser` for a custom executable). SVG and HTML generation remain Python-standard-library only. Alternatively, open the generated HTML, choose **Save as PDF**, and select the browser’s PDF destination. Inspect every page after changing content; longer reports may need deliberate page breaks.
