# v2.0.0 — Full Presentation System (design contract)

Date: 2026-08-02. Status: approved direction, implementation in progress.

## Goal

"Install the skill and you can produce a complete strategy-consulting-style
presentation or document immediately." Three pillars:

1. **Structural slide patterns** — the deck furniture beyond charts: section
   dividers (小扉), agenda, action-title bullet slides, closing/next-steps,
   quote, and back cover. Every slide of a real deck becomes renderable.
2. **Deck templates + scaffolder** — ready-made deck archetypes with
   illustrative placeholder specs, plus `scripts/scaffold_deck.py` so the path
   is: pick template → swap data → one command → animated HTML deck / PDF.
3. **HTML report mode** — `scripts/build_html_report.py`: Markdown (+ slide-spec
   references) → a single self-contained consulting-style HTML document with
   numbered exhibits, TOC, and print-to-A4-PDF CSS. Browser-first documents in
   the same visual system as the decks.

All output stays zero-dependency (Python 3 stdlib only, no network, single-file
HTML artifacts). All visuals obey `references/style-system.md` tokens exactly
(palette, type sizes, 8px grid, kicker-bar discipline, emphasis ladder).

## Non-goals

- No new chart patterns (the 16 existing ones stay untouched).
- No JS frameworks, no external fonts/CDNs, no PPTX export.
- No change to existing renderer functions or shared helpers
  (`header`, `footer`, `wrap`, `text_el`, …) — existing committed SVGs must
  stay byte-identical (CI freshness check).

## Pillar 1 — six new renderable patterns

Add to `scripts/render_slide_spec.py` (`RENDERERS` + `VALIDATORS`), each with a
validator raising `RenderSpecError` on missing required fields. Update module
docstring pattern list. New count: 22.

Full-bleed navy family (bypass header/footer chrome, like `cover` — extend the
`render()` dispatch so a set `CHROMELESS = {"cover", "section_divider", "end_cover"}`
controls chrome; aria-label falls back to `title`):

### `section_divider` (小扉)
```json
{ "pattern": "section_divider", "section_number": 2, "title": "Where to play",
  "subtitle": "Market selection and entry sequence",
  "sections": ["Context", "Where to play", "How to win", "Roadmap"],
  "classification": "Draft — illustrative" }
```
- Navy `#15296B` full bleed; white kicker bar (56x5) at ML, y=200 (same anchor as cover).
- Small-caps label `SECTION 02` (sans 15, `#E5E7EB`, letter-spacing) above title.
- Title serif 40 white, wrap 40 units, max 2 lines; subtitle sans 18 `#E5E7EB`.
- Optional `sections` rail near the bottom (y≈600): items laid out horizontally,
  `NN Title` in sans 13; the current one (index = section_number-1) solid white
  weight 600, others `#E5E7EB` with `opacity="0.55"`. Skip the rail if the
  combined width would overflow ML..W-MR (measure with `_text_width`).
- Required: `title`, `section_number` (int >= 1).

### `end_cover` (裏表紙)
```json
{ "pattern": "end_cover", "title": "Thank you",
  "subtitle": "Questions and discussion",
  "contact": ["Strategy Office", "strategy@example.com"],
  "presenter": "Jane Doe", "date": "March 2026", "classification": "Confidential — illustrative" }
```
- Mirrors `render_cover` geometry: navy, white kicker, serif 52 title
  (default "Thank you" when omitted), subtitle 20 `#E5E7EB`.
- `contact` lines sans 15 `#E5E7EB` starting y=560, 24px leading (max 4).
- presenter/date meta line and classification same slots as cover (y=640).
- Required: none (all fields optional — must render a bare `{"pattern":"end_cover"}`).

White content family (standard header/footer chrome; `headline` drives the
header exactly like chart slides — insight-led headlines still apply):

### `agenda`
```json
{ "pattern": "agenda", "headline": "Three questions decide this investment",
  "items": [ {"title": "Context", "detail": "What changed since January"},
             {"title": "Options", "detail": "Three entry paths, one recommendation"} ],
  "current": 2, "page_number": 2, "source": "" }
```
- 1–8 items. Rows on hairlines (`GREY_BORDER`), starting CHART_TOP, laid out to
  fill the chart band. Number `01`-style serif 24 navy at ML; title sans 17
  weight 600 black; `detail` sans 14 `GREY_MED` on the same row, right column
  (x = ML+320) or under the title when detail is long — pick one and be consistent.
- If `current` given (1-based): that row gets emphasis rung 2 — `BLUE_TINT`
  fill behind the row, title in `BLUE`. At most one row emphasized.
- >6 items: two columns (4+4), same row height. >8 items: `RenderSpecError`.
- Required: `items` (non-empty list of objects with `title`).

### `bullet_list` (action-title text slide)
```json
{ "pattern": "bullet_list", "headline": "Three constraints shape the rollout",
  "bullets": [ {"text": "Capacity is fixed until Q3", "sub": ["Hiring freeze through June"], "emphasis": false} ],
  "columns": 1, "annotation": "", "source": "" }
```
- 1–6 top-level bullets (7+ → `RenderSpecError`; the fix is a better slide, not
  smaller type). Marker: 6x6 navy square at text baseline; text sans 16 black,
  wrap to the column width, 24px leading.
- `sub`: 0–3 items, en-dash marker, sans 14 `GREY_DARK`, indented 24px.
- `emphasis: true` on at most one bullet → weight 600 + `BLUE` text (rung 4;
  validator errors if more than one bullet sets it).
- `columns: 2` splits bullets into two equal columns.
- Required: `bullets` with non-empty `text` each.

### `closing` (key takeaways / next steps)
```json
{ "pattern": "closing", "headline": "Decide the pilot now, scale in Q3",
  "takeaways": ["Unit economics clear the bar", "Risk is concentrated in supply"],
  "next_steps": [ {"action": "Approve pilot budget", "owner": "CFO", "timing": "This week"} ],
  "call_to_action": "Decision requested today: approve the Q2 pilot",
  "page_number": 12, "source": "" }
```
- With `takeaways` (1–4): two columns. Left (width ≈ 45%): label
  `KEY TAKEAWAYS` (sans 12, `GREY_MED`, letter-spaced), numbered serif navy
  digits, text sans 16. Right: label `NEXT STEPS`, rows with `action` sans 16
  weight 600, owner/timing sans 13 `GREY_MED` on a second line ("Owner · Timing").
- Without `takeaways`: next_steps rows full width on hairlines, owner/timing
  right-aligned at W-MR.
- 1–5 next_steps; `action` required per step.
- `call_to_action` renders via the existing footer `annotation` slot mechanics
  (blue 600) — implement by writing it into the annotation position, not by a
  new motif.
- Required: `next_steps`.

### `quote`
```json
{ "pattern": "quote", "headline": "Customers already describe the switch as done",
  "text": "We moved 80% of volume in six weeks — the old tool is a backup now.",
  "attribution": "COO, mid-market logistics customer", "context": "Interview, February 2026",
  "source": "Customer interviews (n=14), Feb 2026" }
```
- Oversized opening quotation mark: serif, 90px, `BLUE_TINT` fill, positioned
  above-left of the quote block (single structural motif, no closing mark).
- Quote text serif 28 black, wrap 58 units, max 4 lines, left-aligned starting
  x=ML+60; attribution sans 15 `GREY_DARK` weight 600 prefixed with an
  em-dash; `context` sans 13 `GREY_MED` below.
- Required: `text`.

### Renderer tests
Extend `tests/test_render_slide_spec.py`: happy path per pattern (SVG contains
expected strings), validator errors (missing required, >8 agenda items,
>6 bullets, two emphasized bullets), JP text renders (wrap), chromeless set
honored (no header kicker on navy family), and the existing invariants
(escaping, contrast) still pass. Do not weaken existing tests.

### Example specs (also serve as documentation)
New files in `examples/render-specs/`, rendered SVGs committed to
`assets/rendered/` (CI enforces freshness):
`strategy-agenda.json`, `phase-divider.json`, `rollout-constraints.json`
(bullet_list), `board-closing.json`, `customer-quote.json`, `deck-end-cover.json`.
Illustrative data only; `source` lines say "Illustrative data".

## Pillar 2 — deck templates + scaffolder

### Layout
```
templates/decks/<archetype>/deck.json        # build_html_deck-compatible manifest
templates/decks/<archetype>/specs/*.json     # numbered: 01-cover.json, 02-agenda.json, …
```
Archetypes (5 EN + 1 JA), each 9–12 slides, every slide renderable, every spec
filled with coherent illustrative data (one consistent fictional storyline per
deck, generic actors like "the company", "Vendor A"; sources say "Illustrative
data — replace"). Each deck must open cover → agenda, use section_divider at
act boundaries, and close with closing → end_cover.

1. `board-update` — cover, agenda, executive summary (summary_strip),
   KPI scorecard, ARR waterfall, trend (time_series), risk heatmap or
   bullet_list of risks, closing, end_cover.
2. `strategy-recommendation` — cover, agenda, context bullet_list,
   section_divider ×2 (Where to play / How to win), two_by_two, benchmark_table,
   gap or waterfall, gantt roadmap, closing, end_cover.
3. `project-status` — cover, summary_strip, gantt, kpi_scorecard,
   bullet_list (blockers), process_flow (path to green), closing, end_cover.
4. `market-entry` — cover, agenda, time_series (market), benchmark_table
   (competitors), two_by_two (segments), process_flow (entry options),
   distribution or scatter, closing, end_cover.
5. `sales-proposal` — cover, bullet_list (client situation), before_after,
   process_flow (approach), gantt (plan), benchmark_table (why us), quote
   (reference customer), closing, end_cover.
6. `board-update-ja` — the board-update storyline in natural Japanese
   (headlines are insight-led sentences, not translations of labels), honoring
   the JP typography rules in style-system.md.

### `scripts/scaffold_deck.py`
- `--list` prints archetypes with one-line descriptions and slide counts.
- `scaffold_deck.py <archetype> -o <dir> [--title T] [--force]` copies
  deck.json + specs/, rewrites the manifest title (and cover title when
  `--title` given), refuses to overwrite an existing non-empty dir without
  `--force`, and prints the next two commands (render check + build deck).
- Pure stdlib, same error style as sibling scripts (`ERROR: …` to stderr,
  exit 1). Tests in `tests/test_scaffold_deck.py` (tmp dirs; list, copy,
  title rewrite, overwrite refusal, unknown archetype).

## Pillar 3 — HTML report mode (browser documents)

### `scripts/build_html_report.py`
CLI: `python3 scripts/build_html_report.py input.md -o report.html [--lang en|ja]`.

Input = Markdown with an optional leading front-matter block:
```
---
title: FY26 growth review
subtitle: Pre-read for the March board meeting
author: Strategy Office
date: March 2026
classification: Confidential — illustrative
lang: en
---
```

Markdown subset (own stdlib parser, documented in the module docstring;
anything outside the subset passes through as escaped text — never crash):
`##`/`###` headings (h1 is reserved for the title block), paragraphs, `-` bullets
(one nesting level), `1.` ordered lists, `**bold**`, `*italic*`, `` `code` ``,
`> blockquote`, GFM tables, `---` hr, `[text](url)` links. All HTML-escaped
first; markdown syntax applied on the escaped text.

Exhibits: a paragraph consisting solely of `![Caption](spec:relative/path.json)`
renders that slide-spec via `render_slide_spec.render()` (chart body without
slide header/footer chrome is NOT required — embed the full slide SVG) inside
a bordered figure: label `Exhibit N — Caption` (auto-numbered, sans 13,
letter-spaced small caps) above the SVG. `spec:` paths resolve relative to the
markdown file. `![Caption](svg:path.svg)` embeds an existing SVG file inline
the same way. Unknown/missing refs → hard error listing the path.

Output: single self-contained HTML.
- Screen: max-width 900px column, generous margins, `#FFFFFF` background.
  Title block: navy band (`#15296B`) full-bleed — white kicker bar, serif title
  44, subtitle, meta line (author · date), classification top-right — the only
  navy surface in the document.
- Auto-numbered h2 (`1.`, `2.` …) with hairline top rules; h3 unnumbered
  weight 600. TOC ("Contents") after the title block, from h2s, with anchor
  links. Serif for headings, sans for body (same stacks as the renderer;
  body 16px/1.6, `--lang ja` → 1.9 line-height and `lang="ja"`).
- Exhibit figures: hairline border `#D1D5DB`, no shadow; caption style as above.
- Print CSS: A4 portrait `@page` with margins; title band prints as first page
  (full navy, `print-color-adjust: exact`); h2 starts a new page when it would
  orphan; figures `break-inside: avoid`; footer "…" not required (page counters
  in margin boxes are not portable — omit rather than fake).
- Zero external requests, zero JS required (a tiny inline script for TOC
  active-state is allowed but optional).

### Templates + demo
- `templates/reports/board-pre-read.md` (report with 2 exhibit refs into
  `../../examples/render-specs/…` — no, keep template self-contained: refer to
  specs copied under `templates/reports/specs/`), `templates/reports/one-pager.md`,
  `templates/reports/proposal-memo.md`.
- `examples/demo-report.md` + committed `examples/demo-report.html`
  (built from it; validator gains a freshness check identical in spirit to
  `validate_demo_deck`).
- Tests `tests/test_build_html_report.py`: front-matter parsing, subset
  rendering (headings/lists/tables/inline), escaping (`<script>` in input stays
  escaped), exhibit numbering and spec embedding, missing-ref error, ja mode.

## Docs, validator, versioning (integration)

- `SKILL.md`: workflow gains the fast path — "for a full deck, scaffold from
  `templates/decks/` and fill data; for documents, write Markdown and run
  build_html_report" — plus the 22-pattern list and the structural-pattern
  guidance (dividers/agenda/closing are furniture: the insight lives in content
  slides). Keep frontmatter constraints (name unchanged, description starts
  "Use when ", ≤500 chars).
- `references/visualization-patterns.md`: add the six patterns with use-when
  rows. `references/style-system.md`: add "Structural Slides" section (navy
  family rules, agenda/closing layout tokens as implemented).
  `references/prompt-templates.md`: spec templates for the six patterns.
  `references/document-type-profiles.md`: report profile is now renderable via
  build_html_report (A4 print), note the exception to "renderer outputs 16:9 only".
- `README.md` / `README.ja.md`: "instant deck" quickstart (scaffold → build),
  template gallery table, report mode section. `QUICKSTART.md`, `EXAMPLES.md`
  updated. `CHANGELOG.md` v2.0.0. `ROADMAP.md` items ticked.
- `scripts/validate_skill.py`: version expectation → `2.0.0`; add new required
  files (scripts, one spec+rendered pair per new pattern, template deck.jsons,
  report templates, demo-report pair); add `validate_demo_report()`; extend
  renderer validation to also render every `templates/decks/*/specs/*.json`
  (render must succeed; no committed SVGs required for templates).
- `marketplace/manifest.json`: version 2.0.0. Sync every stated version/date
  (`grep -rn "1\.9\.0"` must come back only in CHANGELOG history).
- `examples/demo-deck.json`: extend to showcase the full arc (cover, agenda,
  divider, 4 content, closing, end_cover) and rebuild demo-deck.html.

## Acceptance (all must pass)

1. `python3 -m pytest tests/ -q` green.
2. `python3 scripts/validate_skill.py` green.
3. `python3 scripts/scaffold_deck.py board-update -o /tmp/d && cd /tmp/d && python3 <repo>/scripts/build_html_deck.py --manifest deck.json -o deck.html` works for every archetype.
4. `python3 scripts/build_html_report.py examples/demo-report.md -o /tmp/r.html` works; output has zero `http`/`https` references.
5. Existing committed SVGs byte-identical (no drift in the 16 chart patterns).
6. No TODO/stub/placeholder-implementation text anywhere in shipped files.
