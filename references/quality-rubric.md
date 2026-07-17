# Quality Rubric

Score each output out of 24 before presenting it as marketplace-quality work.

## Strategy: 0-5

- 5: The headline answers a decision-critical question and the visual supports a clear implication.
- 3: The visual is useful but the implication is partly descriptive.
- 1: The output is mostly a chart request with no strategic argument.
- 0: The output does not support a decision.

## Data Integrity: 0-5

- 5: Values, labels, units, assumptions, and sources are explicit and internally consistent.
- 3: Data is usable but has minor ambiguity or missing source notes.
- 1: Important values are missing, unverifiable, or inconsistently formatted.
- 0: The output invents data or hides uncertainty.

## Visual Hierarchy: 0-4

- 4: The eye lands on the headline, key number, and implication in the right order, and emphasis follows the strength ladder in `references/style-system.md` with at most one or two strong-emphasis elements.
- 2: The layout is understandable but has weak hierarchy, crowded labels, or emphasis applied on a whim rather than by rank.
- 1: The visual requires too much interpretation.
- 0: The hierarchy is incoherent.

## Data-Ink and Graphical Integrity: 0-4

- 4: Removing any non-text mark would lose information; visual proportions match data proportions within 5% (Lie Factor ≈ 1.0); zero baselines are marked; floating bars (waterfall middles) carry explicit value labels; nothing is truncated without an ellipsis.
- 2: Minor decorative ink or one undisclosed scale choice, but proportions are honest.
- 1: Decoration competes with data, or a scale choice materially exaggerates the message.
- 0: Visual proportions contradict the data.

## Portability: 0-3

- 3: For renderer-supported patterns, the spec renders without extra explanation; for spec-only patterns, the deliverable states plainly that no SVG is produced and the spec is complete enough for a designer or another tool.
- 2: The spec is mostly reproducible but leaves some layout choices open.
- 1: The spec is a prompt fragment, not an implementation-ready direction, or implies rendering support that does not exist.
- 0: The output cannot be reliably reproduced.

## Marketplace Safety: 0-3

- 3: No affiliation claims, unsafe automation, hidden dependencies, or unsupported factual claims.
- 2: Minor wording or assumption caveats need cleanup.
- 1: Risky brand, source, or claim language remains.
- 0: The output implies affiliation, fabricates evidence, or hides behavior.

## Passing Threshold

- 20-24: Marketplace-quality.
- 17-19: Usable draft; revise before publishing as proof.
- 12-16: Internal draft only.
- 0-11: Restart from the strategic question.

## Deck-Level Check (multi-slide outputs)

Single-slide scores do not guarantee a coherent deck. Before delivering a deck, read only the headlines top to bottom and answer yes/no:

- Do the headlines alone form one logical argument (a pyramid: governing thought supported by grouped reasons)?
- Is each headline a single proposition — one answer or one tension — not multiple claims joined by "and"?
- Does any slide's headline repeat or contradict another's?

If any answer fails, fix the storyline before polishing individual slides. The flow summary in the output contract is this check's written result, not an optional garnish.

## Blocking Gates

Even with a passing score, revise before publishing if any of these are true:

- The visual uses universal or guaranteed language beyond the evidence.
- The primary reader or decision is not named.
- The recommendation would change under a plausible missing-data scenario that is not disclosed.
- The meaning depends on color alone, tiny labels, cultural shorthand, or insider jargon.
- The output implies professional verification, legal/medical/financial advice, or affiliation that does not exist.
- The deliverable implies a rendered file for a spec-only pattern or canvas.
