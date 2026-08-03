# Style System

## Design Intent

Create analytical, executive-ready visuals with institutional restraint. The visual should make a strategic point quickly, then reward a second read with clear data structure.

## Design Tokens

The renderer (`scripts/render_slide_spec.py`) and this document share one set of tokens. If a value changes, change it in both places in the same commit — a spec that cannot be reproduced from this document is a bug.

| Token | Value | Meaning |
| --- | --- | --- |
| Canvas | 1280 x 720 (16:9) | The only canvas the renderer produces; other canvases are spec-only |
| Grid unit | 8 px | Margins and fixed anchors sit on multiples of 8; chart geometry is data-driven |
| Margins | 80 px left and right | `ML` / `MR` |
| Headline baseline | y = 96 | First headline line |
| Chart band | y = 208 to 560 | `CHART_TOP` / `CHART_BOTTOM` |
| Annotation baseline | y = 630 | Footer takeaway line |
| Source baseline | y = 692 | Source note and page number |

## Palette

Colors are derived, not copied from a framework default. The primary accent is deliberately darker than a typical UI blue so that a rung-1 solid fill remains distinguishable from dark-grey body text after greyscale conversion (relative-luminance ratio at least 1.5 — asserted in the renderer's test suite). One navy serves both content accents and cover backgrounds; two unrelated navies in one system is drift, not hierarchy.

### Content Slides

| Role | Color |
| --- | --- |
| Background | `#FFFFFF` |
| Primary text | `#000000` |
| Primary accent (single navy) | `#15296B` |
| Secondary accent | `#2563EB` |
| Dark grey | `#374151` |
| Medium grey | `#6B7280` |
| Border grey | `#D1D5DB` |
| Light fill | `#F3F4F6` |
| Light accent tint | `#EFF3FB` |
| Risk accent, sparingly | `#B91C1C` |

### Cover Slides

| Role | Color |
| --- | --- |
| Background (same navy as primary accent) | `#15296B` |
| Primary text | `#FFFFFF` |
| Secondary text | `#E5E7EB` |

There is no metallic or gold accent. A gold-on-navy "premium" flourish is the kind of template cliché this system's own anti-pattern list forbids; restraint is the premium signal.

### Greyscale and Color-Vision Survival

- Meaning must never depend on hue alone (this repeats the quality-rubric blocking gate). Every colored mark carries a direct label, sign, or position that says the same thing.
- The primary accent and dark grey must stay separable in greyscale print. The current pair (`#15296B` vs `#374151`) passes; test any replacement.
- In waterfalls, positive (blue) and negative (red) bars also differ by sign prefix on the value label, so monochrome copies still read correctly.

## Emphasis Hierarchy

Emphasis has a ranked strength order. Apply it deliberately, never on a whim — undisciplined highlighting is the most common cause of cluttered, low-hierarchy slides. Memorize the order as **fill > line > text**: a filled shape outranks a bordered one, and a border outranks styled text. Pick rungs from the top down only as far as the message needs, and reserve the strongest rung for the single element that carries the takeaway.

| Rung | Technique | Tokens | Use for |
| --- | --- | --- | --- |
| 1 (strongest) | Solid fill, reversed text | fill `#15296B`, text `#FFFFFF` | The one box that states the conclusion or focus zone |
| 2 | Tinted fill, accent text | fill `#F3F4F6` or `#EFF3FB`, text `#15296B` | A secondary highlighted block or grouping |
| 3 | Outline only | border `#15296B`, fill `#FFFFFF`, text `#15296B` | A called-out item that should not dominate |
| 4 | Accent-colored text | text `#2563EB` | Keywords and key numbers inline |
| 5 | Bold text | text `#000000`, bold | Sub-labels and minor headings |
| Baseline | Body | text `#000000`, regular | Everything else |

Discipline rules:

- Cap strong emphasis (rungs 1-2) at one element per visual, two only when the message genuinely has two anchors. If everything is emphasized, nothing is.
- Do not stack rungs on the same element. A solid fill already wins; adding colored and bold text on top only adds noise.
- Keep each rung's meaning consistent across a deck so the reader learns the code instead of re-decoding every slide.
- The red risk accent (`#B91C1C`) is orthogonal to this ladder. It marks negative variance or risk, not strength of emphasis, so it never substitutes for a rung.

## Typography

Typefaces are named, not left to fallback chance.

- Headline serif: **Georgia** (fallback: Times New Roman; Japanese: Hiragino Mincho ProN, Yu Mincho). This is a deliberate choice, not a shrug — distributable strategy-consulting templates substitute Georgia for their licensed brand serifs, so Georgia is the accurate portable equivalent.
- Body sans: **Helvetica Neue** (fallbacks: Helvetica, Arial; Japanese: Hiragino Sans, Yu Gothic, Noto Sans JP, Meiryo). The CJK fallbacks are part of the stack, not an afterthought — outputs must render on machines without Latin-only fonts. System Japanese faces come before Noto Sans JP deliberately: a partial Noto install (commonly Black weight only) listed first would set body text ultra-bold.

Type sizes are fixed tokens (px on the 1280x720 canvas, defined once as module constants in `scripts/render_slide_spec.py` and used everywhere — no renderer hardcodes a text-role size literal), not ranges, and they form a **ratio**, not a grab-bag: headline : body : chrome runs roughly **4 : 1.6 : 1** across a slide's full span, reading text (bullets, claims, labels, values) has a hard **floor of 18px** so it survives projection and screen-share, and chrome (source notes, footnotes, page numbers, classification markers) stays deliberately smallest on purpose — never raise it to "balance" a slide.

| Token | Size | Weight | Used for |
| --- | --- | --- | --- |
| `T_COVER_TITLE` | 54 | regular serif | Cover / end-cover title |
| `T_DIVIDER_TITLE` | 48 | regular serif | Section-divider title |
| `T_HEADLINE` | 40 | bold serif | Content headline, up to 2 lines |
| `T_HEADLINE_DENSE` | 32 | bold serif | Content headline, 3 lines |
| `T_STATEMENT` | 32 | regular serif | Quote text; KPI-like big statements |
| `T_KPI_NUM` | 44 | bold | `kpi_scorecard` hero numbers |
| `T_SUBLINE` | 20 | regular | Headline subline; cover/divider subtitle |
| `T_BODY` | 22 | bold/semibold | Bullets, claims, takeaways, actions, agenda item titles, process step titles, benchmark row labels |
| `T_LABEL` | 18 | regular to semibold | Reading floor: sub-bullets, proofs/implications, agenda details, owner-timing metas, chart category/axis/value labels, gantt row labels, small-multiples labels, rail items |
| `T_NUM_AGENDA` | 28 | serif navy | Agenda numbers |
| `T_NUM_CLOSING` | 26 | serif navy | Closing takeaway numbers |
| `T_TICK` | 14 | regular | Axis ticks, min/max range numerals, funnel conversion %; heatmap/benchmark cell values may sit between this and `T_LABEL` in a tight grid, never below it |
| `T_KICKER_LABEL` | 15 | semibold, letter-spaced | Structural small-caps labels: `SECTION NN`, `KEY TAKEAWAYS`, `NEXT STEPS` |
| `T_ANNOTATION` | 22 | semibold | Footer takeaway/annotation line |
| `T_CHROME` | 13 | regular | Source line, footnotes, page number, classification — smallest text on the slide, by design |

Ratio check: `T_HEADLINE / T_BODY` = 1.8 (≥ 1.7), `T_BODY / T_CHROME` = 1.7 (≥ 1.6), deck span `T_COVER_TITLE / T_CHROME` ≈ 4.2. A change that breaks either ratio is wrong, whatever it does for a single slide in isolation. This is a general projection-readability practice — sized for a room, not a monitor two feet away — not a house style borrowed from any one firm.

### Japanese Typography

- Use the sans stack for body and labels; the mincho fallbacks are for headlines only.
- Line feed: CJK body text needs looser leading than Latin — use 1.75-1.8x line height where Latin uses ~1.5x.
- The renderer wraps CJK text per character (no spaces needed) and measures fullwidth characters as double width; do not pre-break Japanese strings.
- Break lines at meaning boundaries when hand-tuning (bunsetsu), never mid-word for katakana loanwords.
- Closing punctuation (。、）」…) never starts a line: the renderer's `wrap()` applies line-start kinsoku automatically by hanging the punctuation off the previous line (ぶら下がり組). When hand-tuning outside the renderer, do the same or pull the preceding character down.

## Canvas Formats

The default canvas is a 16:9 landscape slide, but the system adapts to other deliverables. Pick the canvas from the document profile in `references/document-type-profiles.md`.

| Canvas | Renderer | Use For | Adjustments |
| --- | --- | --- | --- |
| 16:9 landscape | ✓ SVG | Slides, decks, steering materials | Default rules apply |
| A4 / Letter portrait | spec-only | Reports, memos, whitepapers, one-pagers | Smaller headlines, numbered figures, figures sized to text column |
| Vertical 4:5 or 9:16 | spec-only | Infographics, public explainers | Larger type, lower density, top-to-bottom narrative |
| Square 1:1 | spec-only | Compact summaries, social-format cards | One message, one visual, one annotation |
| Inline figure | spec-only | Technical docs, README diagrams | Flexible width, diagram-as-code friendly, no decorative framing |

The bundled renderer produces the 16:9 canvas only. For other canvases the skill delivers a spec or image-generation prompt; say so explicitly in the deliverable.

Across all canvases the constants are: insight-led headline, honest scales, restrained palette, direct labels, and explicit assumptions.

## Layout

- Default canvas: 16:9 landscape.
- Keep outer margins generous enough for projection and screenshots.
- Use a clear top-down reading order: headline, visual body, annotations, source notes.
- Use hairline rules for tables and dividers.
- Keep dense information organized into grid columns, aligned labels, and consistent numeric formats.
- Use whitespace to separate logical groups, not to create decorative emptiness.

## Chart Rules

- Scale axes honestly; do not exaggerate small changes with cropped baselines unless the axis choice is disclosed.
- Mark the zero baseline with an explicit "0" tick so the reader can verify it, not just trust it.
- Align comparable numbers to the same baseline.
- Label important values directly when possible; avoid legend hunting. Direct labels on the first instance replace legend swatches.
- Use blue for the main argument and grey for context.
- Use red only for negative variance, risk, or loss.
- Signed data (variance, deviation, YoY) in heatmaps uses a diverging ramp anchored at zero, never a single-hue ramp.
- Truncated text shows an ellipsis (…) and keeps the full string in a `<title>` element; nothing is cut silently.
- Add source notes when the user provides sources or when assumptions are material.
- Board-facing slides carry their furniture: page number, classification marker, and numbered footnotes where claims need them.
- Bars, cards, and boxes are flat fill, never fill-plus-border. `GREY_FILL` context bars/steps (`gap`, `before_after`'s "before" bar, `distribution`, `gantt`, `process_flow`) and KPI-scorecard cards carry no `GREY_BORDER` stroke — the fill/no-fill (and blue/grey) contrast alone marks emphasis vs. context; a border adds a second, redundant signal for the same distinction. The two_by_two plot frame is the one exception, since that hairline is the axis itself, not a card outline.
- Multi-column layouts (`summary_strip`) separate columns with equal inner margins (whitespace), never a vertical rule — the same principle `closing`'s two-column layout already follows.
- Every text-list pattern's content sits directly under the text (or subhead) that introduces it — `summary_strip`'s subhead, `closing`'s `KEY TAKEAWAYS`/`NEXT STEPS` labels, and `bullet_list`'s headline all function as the immediate label for the band beneath them, and the first line of content anchors to a fixed offset below that label (`band_start`), never centered away from it. This is a **one-step** rule: `y = band_start` (or, for multi-item lists, `y = row_top` where `row_top = band_start + i * row_h` and `row_h = (CHART_BOTTOM - band_start) / len(items)`, the same "divide the band into one row per item" technique `render_agenda`/`render_gap` use). Do **not** add a second centering step that nudges an item — or a whole short list — further down within its row or band. That second step is exactly what caused two regressions in the same slot: whole-block centering (round 2) pushed item 1 away from its label by however much slack a short list left (a 3-item `closing` list measured a 142px gap between `KEY TAKEAWAYS` and item 1); centering *within* a row (round 3, the fix for that) degenerated back to the identical bug whenever a row was most of the band — a 1-item `bullet_list` or 1-item `closing` column left 148-154px of dead air above the item. `band_start` is `CHART_TOP + 34` for `closing`, `CHART_TOP + 20` for `bullet_list` and `summary_strip`. Leftover space from a short list always collects after the last item, right before the footer — never distributed as a gap above item 1 or inside a row. `process_flow`'s box is the one exception (see below): it has no preceding label to anchor under, so centering it as a block between `CHART_TOP` and `CHART_BOTTOM` (via `_center_block_start`, or the equivalent `(CHART_TOP+CHART_BOTTOM)/2 - box_h/2` process_flow uses directly) is safe. `_center_block_start` is currently unused by any renderer but is kept, tested, as that helper for a future no-label pattern.

## Structural Slides

Six patterns are deck furniture rather than charts (see `references/visualization-patterns.md` → Structural / Deck Patterns): `cover`, `section_divider`, `end_cover`, `agenda`, `bullet_list`, `closing`, `quote`. They split into the two chrome families below; the renderer's `CHROMELESS = {"cover", "section_divider", "end_cover"}` set is the single source for which family a pattern belongs to.

### Navy Family (chromeless, full-bleed)

`cover`, `section_divider`, `end_cover` bypass the standard header/footer chrome entirely. None of the three carries a decorative mark: the navy field, the type, and the ML anchor are the family's whole identity.

- **`section_divider`** (小扉): small-caps label `SECTION 02`-style (`T_KICKER_LABEL` 15, `#E5E7EB`, letter-spaced) above the title; title `T_DIVIDER_TITLE` 48 white serif, wrap 33 units, max 2 lines; subtitle `T_SUBLINE` 20 `#E5E7EB`. Optional `sections` rail near y≈600: horizontal `NN Title` items in `T_LABEL` 18 — the current section (index = `section_number` − 1) solid white weight 600, all others `#E5E7EB` at 55% opacity. The rail is skipped, not compressed, if it would overflow the ML..W-MR margins. Required: `title`, `section_number` (integer ≥ 1).
- **`end_cover`** (裏表紙): mirrors the `cover` geometry — `T_COVER_TITLE` 54 serif title (defaults to "Thank you" when omitted), subtitle `T_SUBLINE` 20 `#E5E7EB`. Up to four `contact` lines (`T_LABEL` 18 `#E5E7EB`, 29px leading) start at y=560; presenter/date meta and the classification marker sit in the same slots as `cover` (y=640). Every field is optional — a bare `{"pattern": "end_cover"}` must still render.

### White Content Family (standard chrome)

`agenda`, `bullet_list`, `closing`, `quote` keep the standard header/footer chrome; `headline` drives the header exactly like a chart slide, so the insight-headline discipline still applies even though there is no chart underneath it.

- **`agenda`**: 1–8 rows on hairlines (`GREY_BORDER`), starting at `CHART_TOP` and filling the chart band. `01`-style `T_NUM_AGENDA` 28 navy serif row numbers at ML; title `T_BODY` 22 weight 600 black; `detail` `T_LABEL` 18 `GREY_MED`, either at x = ML+320 or beneath the title when the detail text is long — pick one placement and hold it for the whole deck. More than 6 items splits into two columns (4+4) at the same row height; more than 8 is a spec error, not a smaller row height. At most one row takes rung-2 emphasis via `current` (`BLUE_TINT` fill behind the row, title in `BLUE`).
- **`bullet_list`** (action-title text slide): 1–6 top-level bullets — a 7th is a sign the slide should split in two, so 7+ is a spec error, never smaller type. Marker: a 6×6 navy square at the text baseline; text `T_BODY` 22 black, wrapped to the column width, 30px leading. Each bullet may carry 0–3 `sub` items: en-dash marker, `T_LABEL` 18 `GREY_DARK`, indented 24px, 24px leading. `columns: 2` splits the bullets into two equal columns, each dividing its own share of the chart band into one row per bullet (`row_h = (CHART_BOTTOM - band_start) / len(column_bullets)`, `band_start = CHART_TOP + 20`) and anchoring each bullet's text block (base line(s) + subs) to its row's top edge (`y = row_top`, no further centering within the row) — the same technique `render_gap` uses, so a short list still fills the column edge to edge instead of leaving one dead gap above the footer, and item 1 always sits at `band_start` regardless of bullet count. At most one bullet may set `emphasis: true`, rendered as weight 600 + rung-4 `BLUE` text — the one sanctioned exception to the "do not stack rungs" rule below, reserved for a single inline sentence, never a filled block.
- **`closing`** (key takeaways / next steps): with `takeaways` (1–4) present, two columns — left (~45% width) carries the `KEY TAKEAWAYS` label (`T_KICKER_LABEL` 15, `GREY_MED`, letter-spaced), `T_NUM_CLOSING` 26 numbered serif navy digits, and `T_BODY` 22 text; right carries the `NEXT STEPS` label with `action` `T_BODY` 22 weight 600 and "Owner · Timing" `T_LABEL` 18 `GREY_MED` on a second line. Each label stays pinned at `CHART_TOP`; the list beneath it divides `[CHART_TOP + 34, CHART_BOTTOM]` into one row per item, independently per column since takeaways and next-steps counts (and per-item heights) can differ, and anchors each item's text block to its row's top edge (`y = row_top`, same technique as `bullet_list`, no further centering within the row) — item 1 always sits at `band_start` directly under its label regardless of how many items follow, and the band still fills edge to edge for a short list. Without `takeaways`, 1–5 `next_steps` rows (each requiring `action`) run full width on hairlines with owner/timing right-aligned at W-MR. `call_to_action` renders through the existing footer annotation slot (blue, weight 600) — it reuses that mechanism rather than introducing a new motif.
- **`quote`**: one oversized opening quotation mark (serif 103, decorative — not a reading role, scaled with `T_STATEMENT`; `BLUE_TINT` fill) above-left of the block — the single structural motif this pattern gets, and it never gets a matching closing mark. Quote text `T_STATEMENT` 32 black serif, wrap 50 units, max 4 lines, left-aligned starting at x = ML+60; attribution `T_LABEL` 18 `GREY_DARK` weight 600 prefixed with an em-dash; `context` `T_LABEL` 18 `GREY_MED` below it.

### Deck Arc

The conventional shape a full deck follows: `cover` → `agenda` → content slides (with `section_divider` marking each act boundary) → `closing` → `end_cover`. Not every deck needs every structural pattern, but a `section_divider` with no corresponding `agenda` entry, or a `closing` with no `cover`, reads as an unfinished deck rather than a deliberate one.

## Word Budget

Slides carry claims; prose belongs in the report mode. When text does not
fit, the fix is fewer words or another slide — never smaller type (the type
tokens are floors, not suggestions).

- Headline: one proposition, target 40 half-width units or less (about 20
  Japanese characters). Never two claims joined by a conjunction.
- Bullets, takeaways, next-step actions: aim for one line at body size; two
  lines is the ceiling. Sub-bullets: one line.
- summary_strip: proof and implication each two lines or less at column width.
- Agenda details, owner/timing metas: a phrase, not a sentence.

## Ink Discipline

Every mark must carry information (data-ink rule) — with no exceptions. There is no sanctioned decorative motif: the navy "kicker" bar that used to sit above every headline carried no information and was removed (2026-08-03); the headline itself anchors the slide, and hierarchy comes from typography and position alone. Concretely, this rules out: any decorative bar, horizontal or vertical (a kicker stroke above a headline, a colored left-edge accent bar on a KPI card — `kpi_scorecard` reads status through the trend text color instead); a vertical divider line between `summary_strip` columns (whitespace does that job); and a `GREY_BORDER` stroke paired with a `GREY_FILL` fill on any bar or box (`gap`, `before_after`, `distribution`, `gantt`, `process_flow` — see Chart Rules).

## Anti-Patterns

- Neon, pastel, or startup-style palettes — including gold-on-navy "premium" accents.
- Gradients on analytical content slides.
- Decorative icons that do not encode meaning.
- Any decorative bar: a horizontal "kicker" stroke above a headline, or a left-edge accent bar / colored border on a card, tile, or panel. Bars that carry no data are template filler in any orientation.
- A vertical rule between the columns of a multi-column layout where equal whitespace would separate them just as clearly.
- Legend swatches where a direct label would do.
- Generic descriptive titles such as "Revenue Chart" or "Market Comparison".
- Tiny labels that will not survive export or screen sharing.
- Faux affiliation language with named consulting firms.
