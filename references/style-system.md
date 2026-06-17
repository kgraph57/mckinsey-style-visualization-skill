# Style System

## Design Intent

Create analytical, executive-ready visuals with institutional restraint. The visual should make a strategic point quickly, then reward a second read with clear data structure.

## Palette

### Content Slides

| Role | Color |
| --- | --- |
| Background | `#FFFFFF` |
| Primary text | `#000000` |
| Primary accent | `#1E3A8A` |
| Secondary accent | `#2563EB` |
| Dark grey | `#374151` |
| Medium grey | `#6B7280` |
| Border grey | `#D1D5DB` |
| Light fill | `#F3F4F6` |
| Risk accent, sparingly | `#B91C1C` |

### Cover Slides

| Role | Color |
| --- | --- |
| Background | `#1E3A5F` |
| Secondary background | `#2C4A6F` |
| Primary text | `#FFFFFF` |
| Secondary text | `#E5E7EB` |
| Premium accent, sparingly | `#D4AF37` |

## Emphasis Hierarchy

Emphasis has a ranked strength order. Apply it deliberately, never on a whim — undisciplined highlighting is the most common cause of cluttered, low-hierarchy slides. Memorize the order as **fill > line > text**: a filled shape outranks a bordered one, and a border outranks styled text. Pick rungs from the top down only as far as the message needs, and reserve the strongest rung for the single element that carries the takeaway.

| Rung | Technique | Tokens | Use for |
| --- | --- | --- | --- |
| 1 (strongest) | Solid fill, reversed text | fill `#1E3A8A`, text `#FFFFFF` | The one box that states the conclusion or focus zone |
| 2 | Tinted fill, accent text | fill `#F3F4F6` or light blue, text `#1E3A8A` | A secondary highlighted block or grouping |
| 3 | Outline only | border `#1E3A8A`, fill `#FFFFFF`, text `#1E3A8A` | A called-out item that should not dominate |
| 4 | Accent-colored text | text `#2563EB` | Keywords and key numbers inline |
| 5 | Bold text | text `#000000`, bold | Sub-labels and minor headings |
| Baseline | Body | text `#000000`, regular | Everything else |

Discipline rules:

- Cap strong emphasis (rungs 1-2) at one element per visual, two only when the message genuinely has two anchors. If everything is emphasized, nothing is.
- Do not stack rungs on the same element. A solid fill already wins; adding colored and bold text on top only adds noise.
- Keep each rung's meaning consistent across a deck so the reader learns the code instead of re-decoding every slide.
- The red risk accent (`#B91C1C`) is orthogonal to this ladder. It marks negative variance or risk, not strength of emphasis, so it never substitutes for a rung.

## Typography

- Content headline: serif, bold, 24-36 pt equivalent.
- Cover title: serif, regular or medium, 48-72 pt equivalent.
- Body and labels: sans-serif, regular to semibold, 12-16 pt equivalent.
- Data labels: sans-serif, medium or semibold, aligned to chart geometry.
- Japanese text: prefer sans-serif only and increase size by 10-20% for legibility.

## Canvas Formats

The default canvas is a 16:9 landscape slide, but the system adapts to other deliverables. Pick the canvas from the document profile in `references/document-type-profiles.md`.

| Canvas | Use For | Adjustments |
| --- | --- | --- |
| 16:9 landscape | Slides, decks, steering materials | Default rules apply |
| A4 / Letter portrait | Reports, memos, whitepapers, one-pagers | Smaller headlines, numbered figures, figures sized to text column |
| Vertical 4:5 or 9:16 | Infographics, public explainers | Larger type, lower density, top-to-bottom narrative |
| Square 1:1 | Compact summaries, social-format cards | One message, one visual, one annotation |
| Inline figure | Technical docs, README diagrams | Flexible width, diagram-as-code friendly, no decorative framing |

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
- Align comparable numbers to the same baseline.
- Label important values directly when possible; avoid legend hunting.
- Use blue for the main argument and grey for context.
- Use red only for negative variance, risk, or loss.
- Add source notes when the user provides sources or when assumptions are material.

## Anti-Patterns

- Neon, pastel, or startup-style palettes.
- Gradients on analytical content slides.
- Decorative icons that do not encode meaning.
- Generic descriptive titles such as "Revenue Chart" or "Market Comparison".
- Tiny labels that will not survive export or screen sharing.
- Faux affiliation language with named consulting firms.
