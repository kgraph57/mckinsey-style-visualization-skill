# Quality Rubric

Score each output out of 20 before presenting it as marketplace-quality work.

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

## Portability: 0-3

- 3: The spec can be rendered by an agent, designer, or slide tool without extra explanation.
- 2: The spec is mostly reproducible but leaves some layout choices open.
- 1: The spec is a prompt fragment, not an implementation-ready direction.
- 0: The output cannot be reliably reproduced.

## Marketplace Safety: 0-3

- 3: No affiliation claims, unsafe automation, hidden dependencies, or unsupported factual claims.
- 2: Minor wording or assumption caveats need cleanup.
- 1: Risky brand, source, or claim language remains.
- 0: The output implies affiliation, fabricates evidence, or hides behavior.

## Passing Threshold

- 17-20: Marketplace-quality.
- 14-16: Usable draft; revise before publishing as proof.
- 10-13: Internal draft only.
- 0-9: Restart from the strategic question.

## Blocking Gates

Even with a passing score, revise before publishing if any of these are true:

- The visual uses universal or guaranteed language beyond the evidence.
- The primary reader or decision is not named.
- The recommendation would change under a plausible missing-data scenario that is not disclosed.
- The meaning depends on color alone, tiny labels, cultural shorthand, or insider jargon.
- The output implies professional verification, legal/medical/financial advice, or affiliation that does not exist.
