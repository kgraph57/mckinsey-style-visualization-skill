---
name: strategy-consulting-visualization
description: Use when turning any content into clear, professional visualizations - board slides, reports, proposals, research summaries, training materials, technical diagrams, infographics, process flows, timelines, benchmarks, waterfall charts, or data-backed visual specs for any audience.
license: MIT
---

# Strategy Consulting Visualization

## Purpose

Use this skill to turn any content into professional visualization specs with strategy-consulting clarity: insight-led headlines, disciplined layout, accurate data, restrained design, and explicit implications. It covers board slides first, and generalizes to reports, proposals, training materials, technical diagrams, infographics, and any input that benefits from visual structure.

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
4. Convert the request into an insight-led headline that answers the reader's question.
5. Select the visualization pattern from `references/visualization-patterns.md`.
6. Apply the visual system in `references/style-system.md`, using the canvas from the document profile.
7. Produce a structured spec, diagram-as-code source, or image-generation prompt using `references/prompt-templates.md`.
   When the environment allows running scripts, optionally render supported patterns (waterfall, gap, before_after, time_series, benchmark_table, summary_strip, process_flow, funnel, heatmap, gantt, kpi_scorecard, two_by_two) to SVG with `python3 scripts/render_slide_spec.py <spec.json>`; spec examples are in `examples/render-specs/`.
8. Score the output against `references/quality-rubric.md`.
9. Flag missing data, unverifiable claims, source-sensitive assumptions, or trademark-sensitive wording.
10. For polished executive work, run the draft through `references/iterative-review-loop.md` until the output reaches the stopping criteria.

## Output Contract

Return a concise deliverable with:

- `Strategic question` (or the reader's key question for non-strategy documents)
- `Insight headline`
- `Recommended visualization`
- `Slide spec` (or figure, page, or diagram spec matching the document profile)
- `Data and assumptions`
- `Quality check`

When the user requests a batch, deck, or multi-figure document, repeat the contract per visual and add a brief flow summary explaining how the visuals build the argument.

## Default Visual Standards

- Landscape 16:9 unless the document profile or the user gives another delivery format (A4 report figures, vertical infographics, inline diagrams).
- White content slides with black text, royal blue accents, and grey hierarchy.
- Navy cover slides only when opening a deck or section.
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
- `references/public-reference-corpus.md` for public executive-report sources to study without copying.
- `references/iterative-review-loop.md` for draft, review, revise, and score cycles.
