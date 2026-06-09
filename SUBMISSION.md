# Marketplace Submission Draft

## Title

Strategy Consulting Visualization Skill

## Short Description

Turn raw business metrics into board-ready visualization specs with consulting-style structure, visual examples, quality checks, and iterative review loops.

## Long Description

Strategy Consulting Visualization Skill helps AI agents turn messy business notes into executive-ready slide specs. It supports common strategy visuals such as waterfalls, 2x2 maps, benchmark tables, timelines, capacity gaps, before/after comparisons, market adoption visuals, market-entry comparisons, and executive summary strips.

The package includes a portable `SKILL.md`, reusable references, visual README examples, validation scripts, marketplace metadata, security notes, and a draft -> review -> revise loop for improving slide specs before publication.

## Who It Is For

- founders preparing board updates
- consultants creating executive visuals
- operators converting metrics into decision narratives
- analysts writing investment or vendor-selection memos
- agent users who want repeatable slide-spec workflows

## Key Features

- Produces structured slide specs, not only prompts.
- Selects visualization patterns based on the strategic decision.
- Adds insight-led headlines, annotations, assumptions, and source notes.
- Includes 13 visual README examples.
- Includes 4 iterative review-loop scenarios.
- Includes local validation and review scripts.
- Requires no network access during normal skill use.

## Tags

`SKILL.md`, `agent-skills`, `strategy`, `consulting`, `data-visualization`, `executive-presentations`, `board-slides`, `waterfall-chart`, `benchmark-table`, `2x2-matrix`, `investment-memo`

## Install

```bash
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git ~/.claude/skills/strategy-consulting-visualization
```

## Validation

```bash
python3 scripts/validate_skill.py
python3 scripts/review_slide_spec.py examples/review-loop/market-entry-draft-v2.md
```

## Safety Note

Independent package. Not affiliated with, endorsed by, or sponsored by any consulting firm. Public reference sources are used only to study reusable patterns and review criteria.

