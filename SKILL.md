---
name: strategy-consulting-visualization
description: Use when turning any content into clear, professional visualizations - board slides, reports, proposals, research summaries, training materials, technical diagrams, infographics, process flows, timelines, benchmarks, waterfall charts, or data-backed visual specs for any audience.
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

**Document** — write Markdown (with `spec:`/`svg:` exhibit references where a chart belongs) and build it straight to a browser-ready, print-to-A4 HTML report:

```bash
python3 scripts/build_html_report.py my-report.md -o my-report.html --lang en
```

`templates/reports/` has three starting points (board pre-read, one-pager, proposal memo). Both fast paths still obey the style system and quality rubric below — they only skip writing specs from a blank page. Fall back to the full workflow for anything the templates don't already cover.

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
5. Select the visualization pattern from `references/visualization-patterns.md`, starting from the comparison-type gate at the top of that file. Structural patterns (`section_divider`, `agenda`, `bullet_list`, `closing`, `quote`, `end_cover`, `cover`) are deck furniture, not the argument — use them for connective tissue between slides (opening, orienting, transitioning, closing) and spend the insight-headline discipline on the content slides they connect.
6. Apply the visual system in `references/style-system.md`, using the canvas from the document profile.
7. Produce a structured spec, diagram-as-code source, or image-generation prompt using `references/prompt-templates.md`.
   When the environment allows running scripts, render supported patterns to SVG with `python3 scripts/render_slide_spec.py <spec.json>`. Twenty-two patterns render (cover, section_divider, end_cover, agenda, bullet_list, closing, quote, waterfall, gap, before_after, time_series, benchmark_table, summary_strip, process_flow, funnel, heatmap, gantt, kpi_scorecard, two_by_two, scatter, distribution, small_multiples), on a 16:9 canvas only; every other pattern and canvas is spec-only. `cover`, `section_divider`, and `end_cover` are full-bleed navy and skip the header/footer chrome; every other renderable pattern uses the standard white content chrome. Tell the user which they are getting — never imply a spec-only pattern will render. Spec examples are in `examples/render-specs/`.
8. Score the output against `references/quality-rubric.md`. For decks, also run its deck-level headline check.
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

## Default Visual Standards

- Landscape 16:9 unless the document profile or the user gives another delivery format (A4 report figures, vertical infographics, inline diagrams — spec-only; the renderer outputs 16:9). The one exception: `scripts/build_html_report.py` renders the report profile natively to a browser document with A4 print CSS, embedding 16:9 slide-spec exhibits inline.
- White content slides with black text, a single navy accent (`#15296B`), and grey hierarchy.
- Navy full-bleed slides only when opening a deck (`cover`), opening a section (`section_divider`), or closing a deck (`end_cover`) — never for a content slide.
- Serif headlines and sans-serif labels for English outputs.
- High information density with clear hierarchy; no decorative clutter.
- All numbers must be visible, consistently formatted, and tied to the user's data or cited assumptions.

## Marketplace Safety

This skill is not affiliated with, endorsed by, or sponsored by McKinsey & Company, Boston Consulting Group, Bain & Company, or any other consulting firm. Use category language such as "strategy consulting visualization" in user-facing outputs unless the user specifically asks for comparative style references.

Do not invent client names, confidential labels, benchmark data, or source citations. If a visual depends on uncertain or missing data, mark the assumption explicitly in `Data and assumptions`.

## Reference Files

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
- `templates/decks/` and `scripts/scaffold_deck.py` for ready-made deck archetypes (`--list` to see all six).
- `templates/reports/` and `scripts/build_html_report.py` for Markdown-to-report documents with numbered exhibits.
