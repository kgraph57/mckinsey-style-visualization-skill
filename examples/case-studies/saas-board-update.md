# Case Study: SaaS Board Update — Raw Notes to a Board-Ready Slide

A two-minute read of one real pass through the skill's pipeline: anonymized founder notes go in, the first draft gets rejected by the packaged reviewer, and the revision comes out decision-first, scored, and rendered. Every artifact below is committed in this repository — nothing is staged.

> **The loop:** Input → Draft → Review → Revision → Rendered proof

## 1. Input — the notes a founder actually has

Anonymized from a real board-prep situation. This is the entire input; no cleanup, no structure:

```text
Q4 board meeting in two weeks. Need one slide that carries the ask.
ARR closed the year at $15.0M, up from $10.0M.
Bridge: +$3.0M new enterprise logos, +$2.5M expansion, -$0.5M churn.
AI workflow adoption across the customer base went 18% -> 64% this year.
Sales wants higher enterprise targets. Forecast assumes 18 implementations next quarter.
Implementation team currently handles 12 per quarter. That gap is the real conversation.
Ask: approve implementation capacity investment before raising targets.
```

## 2. Draft — the first output is honest, but weak

The first slide spec ([full draft](../review-loop/board-update-draft-v1.md)) captured the facts and nothing else:

> **Insight headline:** "The company is growing fast but has some capacity issues."
>
> **Slide spec:** Show ARR growth. Show adoption. Mention capacity is 12 but demand is 18. Add recommendation to hire.

Accurate — and useless to a board. It describes the year instead of framing the decision, and the "spec" is a list of facts, not a renderable visual structure.

## 3. Review — the packaged reviewer rejects it

The repo ships a structural reviewer. Run it on the draft yourself:

```bash
python3 scripts/review_slide_spec.py examples/review-loop/board-update-draft-v1.md
```

Actual output (exit code 1 — revise):

```text
Score: 14/20
- Strategy: 5
- Data Integrity: 5
- Visual Hierarchy: 0
- Portability: 2
- Marketplace Safety: 2

Issues:
- Visual hierarchy needs clearer labels, annotations, or primary numbers.
- Portability is partial: add canvas, layout, and source note details.
- Marketplace safety could improve: add originality or source-awareness language.
- Accessibility is underspecified: check contrast, color independence, reading order, and jargon/localization risk.

Decision: revise; score is below 18.
```

The [expert-lens review](../review-loop/board-update-review-v1.md) sharpened the same verdict into four blocking findings:

1. The headline is descriptive — it never states the board decision.
2. The spec lists facts but defines no visual structure.
3. The capacity gap is not annotated as the central constraint.
4. No source note or originality language is included.

## 4. Revision — decision-first, structured, scored

The revised spec ([full revision](../review-loop/board-update-draft-v2.md)) changes exactly what the review demanded:

| | Draft v1 | Revision v2 |
| --- | --- | --- |
| **Headline** | "Growing fast but has some capacity issues" | **"Approve implementation capacity investment before raising enterprise targets"** |
| **Chart choice** | "Board update summary" | Executive summary strip + capacity gap visual, 16:9 canvas |
| **Structure** | Facts in bullets | Three primary numbers ($15M ARR · 64% adoption · 12/18 capacity), direct labels, implication box |
| **Assumptions** | Implicit | Coverage = 12 ÷ 18 = 67%; hiring cost and ROI flagged as *not provided* |
| **Source note** | None | "User-provided board metrics; hiring cost and ROI assumptions not provided" |

Re-run the reviewer on the revision:

```bash
python3 scripts/review_slide_spec.py examples/review-loop/board-update-draft-v2.md
```

```text
Score: 20/20
Decision: pass; score meets 18.
```

## 5. Proof — the rendered slides

The same storyline renders to real SVG with the repo's zero-dependency renderer. Both images below are committed renderer output, freshness-verified by CI on every push:

**The decision slide** — capacity framed as the binding constraint:

![Rendered executive summary strip: capacity, not demand, is the binding constraint](../../assets/rendered/executive-summary.svg)

**The ARR bridge** — where the $5M of growth actually came from:

![Rendered ARR waterfall: enterprise acquisition and expansion added $5.5M, offsetting $0.5M churn](../../assets/rendered/arr-waterfall.svg)

## Reproduce it end to end

```bash
npx skills add kgraph57/mckinsey-style-visualization-skill   # or: git clone into ~/.claude/skills/

# review the committed draft and revision
python3 scripts/review_slide_spec.py examples/review-loop/board-update-draft-v1.md
python3 scripts/review_slide_spec.py examples/review-loop/board-update-draft-v2.md

# render the proof slides
python3 scripts/render_slide_spec.py examples/render-specs/executive-summary.json -o decision.svg
python3 scripts/render_slide_spec.py examples/render-specs/arr-waterfall.json -o bridge.svg

# or scaffold the full nine-slide board deck this scenario belongs to
python3 scripts/scaffold_deck.py board-update -o my-deck
python3 scripts/build_html_deck.py --manifest my-deck/deck.json -o my-deck/deck.html
```

## Related material

- Full worked example with all five slide specs: [input](../board-update-input.md) → [slide specs](../board-update-slide-spec.md) → [evaluation](../evaluation-report.md)
- Three more draft → review → revision scenarios: [examples/review-loop/](../review-loop/)
- The rubric the reviewer enforces: [references/quality-rubric.md](../../references/quality-rubric.md)

---

_All figures are anonymized and illustrative. This is an independent skill package — not affiliated with, endorsed by, or sponsored by McKinsey & Company, Boston Consulting Group, Bain & Company, or any other consulting firm._
