# Persona Playbook

Ready-to-use entry points for the most common business roles. Each persona lists the documents they typically need, the patterns that fit, a copy-paste prompt, and a rendered example committed in this repo.

Agents: when the user's role is known or inferable, start from this file to pick the pattern and tone, then follow the standard workflow in `SKILL.md`.

## Persona Index

| Persona | Typical Documents | Go-To Patterns | Rendered Example |
| --- | --- | --- | --- |
| Sales | Proposals, QBRs, pipeline reviews | Funnel, before-after, benchmark table | `assets/rendered/sales-pipeline-funnel.svg` |
| Marketing | Campaign reviews, GTM plans | Heatmap, funnel, time-series | `assets/rendered/marketing-channel-heatmap.svg` |
| Product manager | Prioritization, roadmap reviews | 2x2, gantt, KPI scorecard | `assets/rendered/product-priority-two-by-two.svg` |
| Project manager / PMO | Status reports, steering decks | Gantt, KPI scorecard, heatmap | `assets/rendered/pmo-rollout-gantt.svg` |
| HR / People ops | Talent reviews, attrition reports | KPI scorecard, heatmap, maturity grid | `assets/rendered/hr-talent-scorecard.svg` |
| Engineer / Tech lead | Postmortems, architecture docs, tech selection | Process flow, decision tree, benchmark table | `assets/rendered/eng-incident-flow.svg` |
| Researcher / Clinician | Study summaries, journal clubs | Before-after, distribution, methodology flow | `assets/rendered/research-outcomes-before-after.svg` |
| Finance / FP&A | Budget variance, forecasts | Waterfall, gap, time-series | `assets/rendered/arr-waterfall.svg` |
| Founder / Executive | Board updates, investor memos | Waterfall, summary strip, 2x2 | `assets/rendered/executive-summary.svg` |

## Copy-Paste Prompts

### Sales

```text
Use the strategy consulting visualization skill. I run sales.
Turn this pipeline data into a QBR slide that shows where we lose deals:
[stage names and counts, e.g., Leads 480 / Qualified 210 / Demo 124 / Proposal 58 / Won 31]
The audience is the CRO; the decision is where to invest next quarter.
```

### Marketing

```text
Use the strategy consulting visualization skill. I run marketing.
Visualize channel performance by segment so we can reallocate budget:
[channels x segments with leads or CAC]
Highlight where the next dollar should go.
```

### Product Manager

```text
Use the strategy consulting visualization skill. I'm a product manager.
Map these feature candidates on effort vs. impact and tell me what to ship first:
[feature, effort estimate, impact evidence — one per line]
```

### Project Manager / PMO

```text
Use the strategy consulting visualization skill. I run the PMO.
Turn this plan into a steering-committee roadmap with the critical path highlighted:
[workstreams with start/end periods, dependencies, and decision gates]
Include the slip risk in the headline.
```

### HR / People Ops

```text
Use the strategy consulting visualization skill. I work in HR.
Build a talent scorecard for the leadership review from these metrics:
[metric, current value, target, trend — one per line]
Flag anything that crossed its threshold.
```

### Engineer / Tech Lead

```text
Use the strategy consulting visualization skill. I'm a tech lead.
Visualize this incident timeline for the postmortem, highlighting the slowest step:
[step, owner, duration — one per line]
Make the fix recommendation the headline. Emit Mermaid if I ask for an editable diagram.
```

### Researcher / Clinician

```text
Use the strategy consulting visualization skill. I'm presenting study results.
Show baseline vs. follow-up for these endpoints without overstating significance:
[endpoint, baseline, follow-up, n — one per line]
Keep claims conservative and note that this is user-provided data.
```

### Finance / FP&A

```text
Use the strategy consulting visualization skill. I work in FP&A.
Build a variance waterfall from budget to actual:
[start value, drivers with +/- amounts, end value]
The audience is the CFO; reconcile every number.
```

### Founder / Executive

```text
Use the strategy consulting visualization skill. I'm preparing a board update.
Turn these notes into 3-5 slide specs that build to a decision:
[paste raw notes]
End with an executive summary strip and the ask.
```

## Adaptation Notes

- Pick the document profile from `references/document-type-profiles.md` once the persona is known: sales maps to proposals, PMO to status reports, researchers to academic summaries.
- Personas change the framing, not the rules: every output keeps insight-led headlines, honest scales, and explicit assumptions from `references/style-system.md`.
- For regulated domains (clinical, financial), keep conclusions attributed to user-provided data and surface caveats in `Data and assumptions`.
