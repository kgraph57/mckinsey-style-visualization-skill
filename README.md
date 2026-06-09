# Strategy Consulting Visualization Skill

> Marketplace-ready Agent Skill for executive strategy visualizations, board slides, competitive benchmarks, investment memos, market maps, timelines, waterfall charts, and data-backed slide specifications.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Skill Format](https://img.shields.io/badge/SKILL.md-ready-blue.svg)](SKILL.md)
[![Validation](https://img.shields.io/badge/Validation-local%20script-green.svg)](scripts/validate_skill.py)

## Why This Exists

Most AI-generated business charts are either generic dashboards or decorative slide art. This skill gives agents a stricter operating system for strategy-consulting visualization:

- insight-led headlines instead of descriptive titles
- pattern selection tied to executive decisions
- disciplined visual hierarchy, palette, typography, and density
- explicit data assumptions and source-sensitive caveats
- reusable slide specs that can be rendered by designers, agents, or presentation tools

The repository is prepared for future skill marketplaces: lightweight `SKILL.md` entrypoint, progressive reference files, validation script, storefront copy, security notes, proof examples, and metadata.

## What It Produces

The skill returns a structured deliverable:

```text
Strategic question
Insight headline
Recommended visualization
Slide spec
Data and assumptions
Quality check
```

It supports common executive visualization patterns:

- time-series growth charts
- gap visualizations
- before/after comparisons
- market share and adoption views
- investment and scale infographics
- timelines
- contrast diagrams
- 2x2 strategic frameworks
- competitive benchmarking tables
- waterfall charts
- cover slides
- executive summary strips

## Install

### Personal Skill

```bash
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git ~/.claude/skills/strategy-consulting-visualization
```

### Project Skill

```bash
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git .claude/skills/strategy-consulting-visualization
```

### Direct Download

```bash
mkdir -p ~/.claude/skills/strategy-consulting-visualization
curl -o ~/.claude/skills/strategy-consulting-visualization/SKILL.md https://raw.githubusercontent.com/kgraph57/mckinsey-style-visualization-skill/main/SKILL.md
```

## Validate

Run the local package check before publishing, listing, or submitting changes:

```bash
python3 scripts/validate_skill.py
```

Expected output:

```text
OK: skill package passed validation
```

## Example Prompt

```text
Use the strategy consulting visualization skill to turn this board update into five slide specs:
- ARR grew from $10M to $15M over four quarters.
- Enterprise expansion contributed $3M.
- Churn reduced revenue by $0.5M.
- AI workflow adoption grew from 18% to 64%.
- Forecast risk is concentrated in implementation capacity.
```

See the proof set:

- [Board update input](examples/board-update-input.md)
- [Expected slide spec](examples/board-update-slide-spec.md)
- [Evaluation report](examples/evaluation-report.md)

## Repository Structure

```text
.
├── SKILL.md
├── references/
│   ├── style-system.md
│   ├── visualization-patterns.md
│   ├── prompt-templates.md
│   └── quality-rubric.md
├── examples/
│   ├── board-update-input.md
│   ├── board-update-slide-spec.md
│   └── evaluation-report.md
├── marketplace/
│   └── manifest.json
├── scripts/
│   └── validate_skill.py
├── MARKETPLACE.md
├── SECURITY.md
├── CHANGELOG.md
└── ROADMAP.md
```

## Marketplace Readiness

- Portable `SKILL.md` entrypoint.
- Concise discovery frontmatter.
- Progressive loading through `references/`.
- No required network access or external tools during normal skill use.
- Local validation script.
- Marketplace listing draft in [MARKETPLACE.md](MARKETPLACE.md).
- Speculative listing metadata in [marketplace/manifest.json](marketplace/manifest.json).

## Commercial Angle

This package is designed to become:

- a listed skill in future agent-skill marketplaces
- a premium template pack for executive visualization workflows
- a proof library for agents that create board-ready slide specs
- a foundation for later renderer or SaaS integration

## Disclaimer

This is an independent skill package. It is not affiliated with, endorsed by, or sponsored by McKinsey & Company, Boston Consulting Group, Bain & Company, or any other consulting firm. Named firms may appear only as common style references or search terms.

## License

MIT. See [LICENSE](LICENSE).
