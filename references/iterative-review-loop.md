# Iterative Review Loop

Use this loop when the user asks for polished executive materials, marketplace proof examples, or repeated refinement.

## Loop Overview

```text
public reference scan
-> original draft
-> executive review
-> revision
-> rubric score
-> repeat until threshold
```

## Inputs

- user business question
- raw metrics and assumptions
- target audience
- desired output format
- relevant reference patterns from `references/public-reference-corpus.md`

## Review Roles

Run every draft through five review lenses:

| Lens | Question |
| --- | --- |
| CEO / board lens | Does the slide support a decision, or merely describe a situation? |
| CFO / investor lens | Are numbers, units, deltas, and assumptions explicit and internally consistent? |
| Strategy partner lens | Is the headline a sharp answer to the strategic question? |
| Visual editor lens | Is the hierarchy obvious in the first five seconds? |
| Marketplace safety lens | Is the output original, source-aware, and non-affiliated? |

## Stopping Criteria

Stop the loop only when all conditions are true:

- score is 18 or higher using `references/quality-rubric.md`
- no review lens has a blocking issue
- all data assumptions are visible
- the slide spec can be rendered without extra interpretation
- a reviewer can explain the decision implication in one sentence

If the score is below 18, revise and run the loop again. If a blocking issue repeats twice, return to the strategic question before drafting another visual.

## Review Template

```markdown
# Review N

## Score

- Strategy: /5
- Data integrity: /5
- Visual hierarchy: /4
- Portability: /3
- Marketplace safety: /3
- Total: /20

## Blocking Issues

- [Issue]

## Revision Instructions

- [Specific change]

## Decision

- Revise / Pass
```

## Revision Rules

- Fix the highest-severity issue first.
- Preserve accurate data even if the visual becomes less dramatic.
- Prefer one clear implication over many weak observations.
- Make assumptions more visible instead of hiding weak data.
- Do not borrow layouts, text, or images from reference sources.
