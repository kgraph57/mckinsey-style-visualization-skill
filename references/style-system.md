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
- Body sans: **Helvetica Neue** (fallbacks: Helvetica, Arial; Japanese: Noto Sans JP, Hiragino Sans, Yu Gothic, Meiryo). The CJK fallbacks are part of the stack, not an afterthought — outputs must render on machines without Latin-only fonts.

Type sizes are fixed tokens (px on the 1280x720 canvas), not ranges:

| Role | Size | Weight |
| --- | --- | --- |
| Content headline (up to 2 lines) | 30 | bold serif |
| Content headline (3 lines) | 24 | bold serif |
| Cover title | 52 | regular serif |
| Subline | 17 | regular |
| Section/claim text | 16-17 | bold |
| Body, labels, values | 13-15 | regular to semibold |
| Footnotes, ticks, furniture | 11-12 | regular |

### Japanese Typography

- Use the sans stack for body and labels; the mincho fallbacks are for headlines only.
- Line feed: CJK body text needs looser leading than Latin — use 1.75-1.8x line height where Latin uses ~1.5x.
- The renderer wraps CJK text per character (no spaces needed) and measures fullwidth characters as double width; do not pre-break Japanese strings.
- Break lines at meaning boundaries when hand-tuning (bunsetsu), never mid-word for katakana loanwords.
- Avoid starting a line with closing punctuation (。、）」); when hand-tuning, pull the preceding character down.

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

## Ink Discipline

Every mark must carry information (data-ink rule). The one sanctioned decorative motif is the kicker bar above the headline — a single signature, used once per slide. Do not echo it as accent bars on annotations, column headers, or cards; a repeated motif reads as template filler and competes with the emphasis ladder.

## Anti-Patterns

- Neon, pastel, or startup-style palettes — including gold-on-navy "premium" accents.
- Gradients on analytical content slides.
- Decorative icons that do not encode meaning.
- Repeating the kicker-bar motif on multiple elements of one slide.
- Legend swatches where a direct label would do.
- Generic descriptive titles such as "Revenue Chart" or "Market Comparison".
- Tiny labels that will not survive export or screen sharing.
- Faux affiliation language with named consulting firms.
