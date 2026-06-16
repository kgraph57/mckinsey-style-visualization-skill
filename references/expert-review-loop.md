# Expert Review Loop

Use this when an output is public, high-stakes, cross-functional, or intended for a broad audience. Treat the reviewers as lenses, not authorities. The goal is to remove blind spots and make the visual easier to use.

## Review Lenses

| Lens | What to challenge | Pass signal |
| --- | --- | --- |
| Research methods professor | Causality, sampling, source quality, uncertainty | Claims are scoped to the evidence and assumptions are explicit. |
| Behavioral scientist | Framing effects, confirmation bias, default choices | The slide shows what would change the conclusion. |
| Executive operator | Decision, owner, timing, trade-off | A leader knows the next action after 10 seconds. |
| CFO / investor | Unit economics, reconciliation, downside risk | Numbers tie out and the risk case is visible. |
| Product / UX lead | Reader path, jargon, first-use friction | A non-expert can explain the message without instructions. |
| Data visualization expert | Chart fit, scale honesty, label load | The pattern does not imply precision the data cannot support. |
| Accessibility reviewer | Color, contrast, reading order, alt text | Meaning does not depend on color alone or tiny labels. |
| Cross-cultural reviewer | Idioms, local norms, translation risk | Labels survive localization and avoid insider shorthand. |
| Security / legal reviewer | Confidentiality, regulated claims, affiliations | No private data, fabricated sources, or endorsement language appears. |

## Bias Breakers

Before presenting the final spec, answer these briefly:

1. What assumption would most likely be wrong?
2. What audience might misunderstand or reject this framing?
3. What missing data would change the recommendation?
4. Does any wording sound certain beyond the evidence?
5. Does the visual work without color, cultural shorthand, or insider jargon?

## Subtract Before Adding

Prefer removing friction over adding explanation:

- Remove unsupported adjectives before adding caveats.
- Remove chart precision before adding footnotes.
- Remove jargon before adding a glossary.
- Split an overloaded visual before adding more annotations.
- Use the simplest pattern that answers the reader's job.

## Output Add-On

When this loop applies, add a short `Expert review notes` block:

```text
Expert review notes:
- Assumption challenged: [most fragile assumption and how it is labeled]
- Reader fit: [primary audience and likely misunderstanding]
- Accessibility/localization: [color, label, jargon, or translation check]
- Counterpoint: [what would change the recommendation]
```
