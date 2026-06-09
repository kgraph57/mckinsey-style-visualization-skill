---
name: strategy-consulting-visualization
description: Use when creating executive-ready strategy consulting visualizations, board slides, competitive benchmarks, investment memos, market maps, timelines, waterfall charts, or data-backed slide specs for decision makers.
license: MIT
---

# Strategy Consulting Visualization

## Purpose

Use this skill to turn business inputs into executive-ready visualization specs with strategy-consulting clarity: insight-led headlines, disciplined layout, accurate data, restrained design, and explicit decision implications.

## Use When

- The user needs a board slide, executive memo visual, market map, competitor benchmark, investment view, performance bridge, or strategic timeline.
- The output should feel like a top-tier consulting deliverable without implying affiliation with any consulting firm.
- The user has raw data, notes, or a business question and needs a slide-ready visual direction.
- The user asks for McKinsey-style, BCG-style, Bain-style, consulting-style, boardroom-ready, executive-ready, or strategy-deck visuals.

## Do Not Use When

- The user wants decorative marketing graphics, social posts, generic dashboards, brand campaigns, or low-density inspirational visuals.
- The user needs regulated financial, medical, or legal conclusions without source verification.
- The user asks for a final rendered chart but has not provided enough data to check labels, scales, and claims.

## Workflow

1. Identify the strategic decision the visual should support.
2. Convert the request into an insight-led headline that answers the decision question.
3. Select the visualization pattern from `references/visualization-patterns.md`.
4. Apply the visual system in `references/style-system.md`.
5. Produce a structured slide spec or image-generation prompt using `references/prompt-templates.md`.
6. Score the output against `references/quality-rubric.md`.
7. Flag missing data, unverifiable claims, source-sensitive assumptions, or trademark-sensitive wording.

## Output Contract

Return a concise deliverable with:

- `Strategic question`
- `Insight headline`
- `Recommended visualization`
- `Slide spec`
- `Data and assumptions`
- `Quality check`

When the user requests a batch or deck, repeat the contract per slide and add a brief flow summary explaining how the slides build the argument.

## Default Visual Standards

- Landscape 16:9 unless the user gives another delivery format.
- White content slides with black text, royal blue accents, and grey hierarchy.
- Navy cover slides only when opening a deck or section.
- Serif headlines and sans-serif labels for English outputs.
- High information density with clear hierarchy; no decorative clutter.
- All numbers must be visible, consistently formatted, and tied to the user's data or cited assumptions.

## Marketplace Safety

This skill is not affiliated with, endorsed by, or sponsored by McKinsey & Company, Boston Consulting Group, Bain & Company, or any other consulting firm. Use category language such as "strategy consulting visualization" in user-facing outputs unless the user specifically asks for comparative style references.

Do not invent client names, confidential labels, benchmark data, or source citations. If a visual depends on uncertain or missing data, mark the assumption explicitly in `Data and assumptions`.

## Reference Files

- `references/visualization-patterns.md` for pattern selection and use cases.
- `references/style-system.md` for palette, typography, spacing, and layout rules.
- `references/prompt-templates.md` for slide specs and image-generation prompts.
- `references/quality-rubric.md` for final scoring and marketplace-quality checks.
