# Input Triage: Visualize Anything

Use this file first when the input is not an obvious chart request. It maps any kind of input — numbers, prose, processes, ideas, transcripts, code, research — to a visualization pattern in `references/visualization-patterns.md`.

## Triage Steps

1. Identify what the input fundamentally *is* (see Input Types below).
2. Identify what the reader must *do* with it: decide, understand, follow, compare, remember, or act.
3. Pick the pattern family that matches the input type and reader job.
4. Pick the document profile from `references/document-type-profiles.md` to set format, density, and tone.
5. If the input is mixed, split it into one visual per message rather than one visual that says everything.

## Input Types and Pattern Mapping

| Input Type | Typical Raw Material | Reader Job | Pattern Family |
| --- | --- | --- | --- |
| Quantity over time | Metrics, KPIs, logs, sales history | Spot momentum or inflection | Time-series growth, before-after |
| Comparison across items | Vendors, options, products, regions | Pick or rank | Benchmark table, gap visualization, ranked bars |
| Part-to-whole | Budget split, market segments, survey results | See composition | Market share / adoption, stacked composition |
| Change decomposition | Variance, bridge, budget delta | Understand what drove the change | Waterfall chart |
| Process or workflow | SOPs, onboarding steps, pipelines, algorithms | Follow or improve a sequence | Process flow, funnel, cycle diagram |
| Plan over time | Project plans, rollouts, curricula, regulation | Know what happens when | Timeline, Gantt / roadmap |
| Hierarchy or structure | Org charts, taxonomies, file trees, outlines | Navigate levels | Hierarchy / tree, pyramid |
| Relationships or systems | Stakeholders, dependencies, causal loops | See how parts interact | Concept / system map, flow (Sankey-style) |
| Position across two drivers | Strategic options, competitors, risks | Choose a position | 2x2 framework, scatter / correlation |
| Many-by-many intensity | Skills matrices, risk grids, schedules | Find hot spots | Heatmap matrix |
| Distribution | Test scores, response times, prices | See spread and outliers | Distribution chart |
| Status snapshot | Dashboards, OKR check-ins, health checks | Scan state at a glance | KPI scorecard, checklist / maturity grid |
| Decision logic | Eligibility rules, escalation policies, troubleshooting | Branch correctly | Decision tree |
| Qualitative argument | Essays, memos, meeting notes, interviews | Grasp the claim and support | Executive summary strip, pyramid, contrast diagram |
| Instructional content | Lessons, tutorials, explanations | Learn and retain | Process flow, concept map, before-after, cycle |
| Geographic data | Stores, markets, incidents by location | See spatial concentration | Annotated map description, ranked bars by region |

## Handling Difficult Inputs

### Pure prose with no numbers

Extract the argument structure: main claim, supporting points, evidence, implication. Visualize the structure (pyramid, summary strip, contrast diagram), not invented statistics. Never fabricate numbers to make prose look quantitative.

### Long or messy documents

Summarize into 3-7 message units first, then assign one pattern per unit. Offer a single overview visual (summary strip or concept map) plus detail visuals per section.

### Vague requests ("visualize this")

State the assumed reader, decision or job, and chosen pattern explicitly in the output so the user can correct course. Choose the simplest pattern that does the job.

### Mixed quantitative and qualitative input

Lead with the qualitative claim as the headline; use the quantitative material as proof inside the visual. Do not present two disconnected visuals when one claim-plus-proof unit works.

### Data that is too thin to chart

If there are fewer than three data points or the values are unverifiable, prefer a scorecard, contrast diagram, or annotated statement over a chart that implies false precision. Flag the gap in `Data and assumptions`.

### Sensitive or regulated content

Medical, legal, and financial inputs can be visualized for structure and communication, but mark conclusions as user-provided and avoid implying verified professional judgment.

## One-Question Shortcut

If triage stalls, ask: **"What should the reader be able to do after ten seconds with this visual?"**

- Decide between options → comparison family
- Understand why something changed → waterfall or before-after
- Follow steps without help → process flow or decision tree
- See where they stand → gap, scorecard, or maturity grid
- Remember the message → summary strip or pyramid
