# Skill Marketplace Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the repository into a marketplace-ready Agent Skill package for strategy consulting visualizations.

**Architecture:** Keep `SKILL.md` as the portable entrypoint and move reusable detail into progressive `references/` files. Add marketplace-facing metadata, proof examples, and a local validation script so the package is discoverable, reviewable, and diligence-friendly without becoming a SaaS.

**Tech Stack:** Markdown, YAML frontmatter, JSON metadata, Python standard library validation.

---

## File Structure

- Modify `SKILL.md`: rewrite as a concise, portable skill with progressive references.
- Modify `README.md`: convert from basic repo README to marketplace/product overview.
- Modify `QUICKSTART.md`: update naming and correct install commands.
- Modify `INSTALLATION.md`: update naming, paths, verification, and correct URLs.
- Modify `EXAMPLES.md`: align terminology and link to proof examples.
- Modify `CONTRIBUTING.md`: add marketplace-quality contribution standards.
- Create `MARKETPLACE.md`: storefront-style listing copy and review checklist.
- Create `SECURITY.md`: install safety, permissions, data handling, and reporting.
- Create `CHANGELOG.md`: release history with a marketplace-readiness release.
- Create `ROADMAP.md`: product roadmap focused on skill marketplace readiness.
- Create `marketplace/manifest.json`: future marketplace metadata.
- Create `references/style-system.md`: visual system reference.
- Create `references/visualization-patterns.md`: pattern selection reference.
- Create `references/prompt-templates.md`: reusable prompt/spec templates.
- Create `references/quality-rubric.md`: quality scoring rubric.
- Create `examples/board-update-input.md`: sample raw business input.
- Create `examples/board-update-slide-spec.md`: expected structured output.
- Create `examples/evaluation-report.md`: quality rubric proof.
- Create `scripts/validate_skill.py`: structural package validation.

## Task 1: Rewrite Skill Entrypoint

**Files:**
- Modify: `SKILL.md`
- Create: `references/style-system.md`
- Create: `references/visualization-patterns.md`
- Create: `references/prompt-templates.md`
- Create: `references/quality-rubric.md`

- [ ] **Step 1: Replace `SKILL.md` with marketplace-ready entrypoint**

Use frontmatter:

```yaml
---
name: strategy-consulting-visualization
description: Use when creating executive-ready strategy consulting visualizations, board slides, competitive benchmarks, investment memos, market maps, timelines, waterfall charts, or data-backed slide specs for decision makers.
license: MIT
---
```

Then define workflow sections:

```markdown
# Strategy Consulting Visualization

## Purpose

Use this skill to turn business inputs into executive-ready visualization specs with strategy-consulting clarity: insight-led headlines, disciplined layout, accurate data, restrained design, and explicit decision implications.

## Use When

- The user needs a board slide, executive memo visual, market map, competitor benchmark, investment view, performance bridge, or strategic timeline.
- The output should feel like a top-tier consulting deliverable without implying affiliation with any consulting firm.
- The user has raw data, notes, or a business question and needs a slide-ready visual direction.

## Do Not Use When

- The user wants decorative marketing graphics, social posts, generic dashboards, brand campaigns, or low-density inspirational visuals.
- The user needs regulated financial, medical, or legal conclusions without source verification.

## Workflow

1. Identify the strategic decision the visual should support.
2. Convert the request into an insight-led headline.
3. Select the visualization pattern from `references/visualization-patterns.md`.
4. Apply the visual system in `references/style-system.md`.
5. Produce a structured slide spec or image-generation prompt using `references/prompt-templates.md`.
6. Score the output against `references/quality-rubric.md`.
7. Flag missing data, unverifiable claims, or source-sensitive assumptions.

## Output Contract

Return a concise deliverable with:

- `Strategic question`
- `Insight headline`
- `Recommended visualization`
- `Slide spec`
- `Data and assumptions`
- `Quality check`

## Marketplace Safety

This skill is not affiliated with, endorsed by, or sponsored by McKinsey & Company, Boston Consulting Group, Bain & Company, or any other consulting firm. Use category language such as "strategy consulting visualization" in user-facing outputs unless the user specifically asks for comparative style references.
```

- [ ] **Step 2: Add `references/style-system.md`**

Include palette, typography, layout density, spacing, chart rules, and anti-patterns.

- [ ] **Step 3: Add `references/visualization-patterns.md`**

Include 12 patterns: time-series, gap, before-after, market share, investment scale, timeline, contrast, 2x2, benchmarking table, waterfall, cover slide, executive summary strip.

- [ ] **Step 4: Add `references/prompt-templates.md`**

Include reusable templates for slide specs and image generation prompts.

- [ ] **Step 5: Add `references/quality-rubric.md`**

Include a 20-point rubric across strategy, data, visual hierarchy, portability, and marketplace safety.

## Task 2: Add Marketplace and Business Layer

**Files:**
- Modify: `README.md`
- Create: `MARKETPLACE.md`
- Create: `marketplace/manifest.json`
- Create: `SECURITY.md`
- Create: `CHANGELOG.md`
- Create: `ROADMAP.md`

- [ ] **Step 1: Rewrite `README.md` as product overview**

Include:

- value proposition
- install commands with correct repository URL
- what the skill produces
- marketplace readiness badges as text
- repo structure
- non-affiliation disclaimer
- validation command
- links to examples and marketplace listing copy

- [ ] **Step 2: Add `MARKETPLACE.md`**

Include listing title, short description, long description, target users, categories, keywords, proof checklist, screenshot checklist, and support model.

- [ ] **Step 3: Add `marketplace/manifest.json`**

Include:

```json
{
  "schema_version": "0.1.0",
  "name": "strategy-consulting-visualization",
  "display_name": "Strategy Consulting Visualization Skill",
  "version": "1.2.0",
  "category": "visualization",
  "tags": ["strategy", "consulting", "executive-presentations", "data-visualization", "board-slides"],
  "license": "MIT",
  "entrypoint": "SKILL.md",
  "compatibility": ["Claude Code", "Codex", "Cursor", "Gemini CLI", "GitHub Copilot"],
  "permissions": {
    "network": false,
    "filesystem_write": false,
    "external_tools": false
  },
  "disclaimer": "Independent skill package. Not affiliated with or endorsed by any consulting firm."
}
```

- [ ] **Step 4: Add `SECURITY.md`**

Document no required network access, no hidden scripts during normal skill use, no sensitive-data retention, and issue reporting.

- [ ] **Step 5: Add `CHANGELOG.md`**

Add `1.2.0 - Marketplace readiness` plus previous versions.

- [ ] **Step 6: Add `ROADMAP.md`**

Add phases: marketplace listing, proof gallery, paid template pack, renderer integration, SaaS exploration.

## Task 3: Add Proof Examples

**Files:**
- Create: `examples/board-update-input.md`
- Create: `examples/board-update-slide-spec.md`
- Create: `examples/evaluation-report.md`
- Modify: `EXAMPLES.md`

- [ ] **Step 1: Add sample raw input**

Use a board update scenario with revenue, churn, enterprise expansion, AI adoption, and forecast risk.

- [ ] **Step 2: Add expected slide spec**

Show the structured output contract for five slides: cover, revenue waterfall, adoption time-series, churn gap, executive recommendation.

- [ ] **Step 3: Add evaluation report**

Score the example against the 20-point rubric and note remaining risks.

- [ ] **Step 4: Update `EXAMPLES.md`**

Add a marketplace proof section linking to the three example files.

## Task 4: Add Validation Script

**Files:**
- Create: `scripts/validate_skill.py`
- Modify: `QUICKSTART.md`
- Modify: `INSTALLATION.md`

- [ ] **Step 1: Add Python validator**

Implement with only the standard library. Check frontmatter, manifest JSON, required files, stale `Helix` URLs, non-affiliation disclaimer, and required reference files.

- [ ] **Step 2: Run validator**

Run:

```bash
python3 scripts/validate_skill.py
```

Expected output:

```text
OK: skill package passed validation
```

- [ ] **Step 3: Update install docs**

Add the validation command to `QUICKSTART.md` and `INSTALLATION.md`.

## Task 5: Contributor and Repository Polish

**Files:**
- Modify: `CONTRIBUTING.md`
- Modify: `.gitignore`

- [ ] **Step 1: Update contributor standards**

Add standards for marketplace-safe language, reference file updates, examples, and validation before PR.

- [ ] **Step 2: Update `.gitignore`**

Add generated proof assets and local output folders:

```gitignore
outputs/
*.png
*.jpg
*.jpeg
*.pdf
```

- [ ] **Step 3: Run package checks**

Run:

```bash
python3 scripts/validate_skill.py
rg -n "github.com/kgraph57/Helix|raw.githubusercontent.com/kgraph57/Helix|official McKinsey|official BCG|official Bain|McKinsey-approved|BCG-approved|Bain-approved" .
```

Expected: validator passes; search returns no stale URL or affiliation claims.

## Self-Review

- Spec coverage: all acceptance criteria map to Tasks 1-5.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: skill name is consistently `strategy-consulting-visualization`; repository URL remains `kgraph57/mckinsey-style-visualization-skill`.
