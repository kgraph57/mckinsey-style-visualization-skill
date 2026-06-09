# Skill Marketplace Readiness Design

## Goal

Prepare this repository to succeed if agent-skill marketplaces become a major distribution channel. The repo should look less like a loose prompt document and more like a marketplace-ready, diligence-friendly skill product: discoverable, portable, validated, legally safer, and easy for a buyer or platform reviewer to understand.

## Market Assumption

Skill marketplaces will likely reward packages that are:

- easy for agents to discover from concise frontmatter
- compatible with the emerging `SKILL.md` convention across multiple coding agents
- structured for progressive loading with optional `references/`, `assets/`, and `scripts/`
- safe to install because they disclose permissions and avoid hidden behavior
- proven with examples, validation scripts, sample inputs, and quality rubrics
- packaged with versioning, release notes, commercial positioning, and support expectations

This design intentionally avoids building a SaaS now. It keeps the asset lightweight while making it credible as a listed marketplace product and as an acquisition target.

## Positioning

The public-facing product should move from trademark-dependent language toward a safer category:

- Preferred category: `strategy consulting visualization`
- Preferred product name: `Strategy Consulting Visualization Skill`
- Search-supporting phrase: `McKinsey-style / BCG-style consulting visuals`
- Required disclaimer: not affiliated with, endorsed by, or sponsored by any named consulting firm

This reduces marketplace review risk and improves buyer confidence while preserving discoverability for people searching for the familiar style.

## Target Users

- consultants producing executive decks
- founders and operators preparing board updates
- analysts turning data into strategy slides
- medical, AI, and enterprise teams that need boardroom-grade visual explanations
- agent users who want reusable visual-spec workflows instead of one-off prompts

## Product Package

### Core Skill

`SKILL.md` remains the installation unit. It should become shorter, more operational, and more trigger-friendly:

- frontmatter optimized for agent discovery
- clear workflow from strategic question to visual specification
- strict quality gates for data accuracy, insight headlines, and layout
- progressive references instead of stuffing every detail into the main file
- platform-neutral language where possible

### Reference Library

Move reusable detail into `references/`:

- `visualization-patterns.md`: reusable visualization patterns and when to use them
- `prompt-templates.md`: prompt/spec templates for each visualization type
- `quality-rubric.md`: scoring checklist for marketplace proof and user trust
- `style-system.md`: typography, palette, spacing, density, and layout rules

### Marketplace Layer

Add files that a future marketplace, curator, or acquirer can scan quickly:

- `marketplace/manifest.json`: speculative listing metadata
- `MARKETPLACE.md`: storefront copy, audience, benefits, examples, screenshots checklist
- `SECURITY.md`: permissions, file access expectations, and safe-use policy
- `CHANGELOG.md`: versioned release history
- `ROADMAP.md`: near-term and commercial expansion roadmap

### Proof Assets

Add lightweight assets that make quality visible without requiring generated images:

- sample business inputs
- expected slide-spec outputs
- example evaluation reports
- before/after prompt comparisons

These can live in `examples/` and `assets/` so future generated screenshots or PDFs can be dropped in without changing the package model.

### Validation

Add `scripts/validate_skill.py` to verify:

- `SKILL.md` has valid frontmatter
- required metadata exists
- description remains within marketplace-friendly length
- referenced files exist
- no stale repository URLs remain
- marketplace manifest parses
- package has security, changelog, roadmap, and examples

Validation is important because a marketplace buyer will trust a skill more if it has a repeatable quality check.

## Repository Shape

```text
.
├── SKILL.md
├── README.md
├── MARKETPLACE.md
├── SECURITY.md
├── CHANGELOG.md
├── ROADMAP.md
├── marketplace/
│   └── manifest.json
├── references/
│   ├── style-system.md
│   ├── visualization-patterns.md
│   ├── prompt-templates.md
│   └── quality-rubric.md
├── examples/
│   ├── board-update-input.md
│   ├── board-update-slide-spec.md
│   └── evaluation-report.md
├── scripts/
│   └── validate_skill.py
└── docs/
    └── superpowers/
        ├── specs/
        └── plans/
```

## Acceptance Criteria

- The root README reads like a credible marketplace listing and product overview.
- Installation URLs point to the correct repository.
- `SKILL.md` is portable, concise, and uses progressive loading.
- The package includes references, examples, manifest, security notes, changelog, and roadmap.
- A local validation command can detect structural problems.
- The repo avoids implying affiliation with McKinsey, BCG, Bain, or any other consulting firm.
- A future buyer can understand the commercial angle within five minutes.

## Non-Goals

- No SaaS app in this phase.
- No paid licensing implementation.
- No generated image asset pipeline yet.
- No claims of official compatibility with future marketplaces that do not exist or have not accepted the package.

## Risks

- Marketplace standards may shift. Mitigation: keep the core package aligned with the minimal `SKILL.md` convention and keep marketplace-specific metadata separate.
- The current repository name includes `mckinsey-style`. Mitigation: public copy and product naming use category language plus a non-affiliation disclaimer.
- Visual quality is hard to prove without rendered examples. Mitigation: include deterministic slide specs and a rubric now; add screenshots later.
