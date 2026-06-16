# Changelog

## Unreleased

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
