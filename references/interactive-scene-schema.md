# Interactive scene authoring map

Use this reference after the title-first storyboard has shown that operating a
page improves a decision. The executable contract is
[`interactive-scene-v1.schema.json`](../schemas/interactive-scene-v1.schema.json);
this page explains how the pieces fit together.

## Files and commands

Each interactive manifest slide is an object with `id`, `spec`, and `scene`.
`id` is stable across revisions, the deck declares `lang`, and every scene uses
`"version": 1`. Paths resolve under the manifest directory and cannot escape
it. See [Project Relay](../examples/interactive-deck/deck.json) and the focused
[fixtures](../examples/interactive-fixtures/).

```bash
python3 scripts/build_html_deck.py --manifest examples/interactive-deck/deck.json -o deck.html
python3 scripts/build_interactive_deck.py --manifest examples/interactive-deck/deck.json -o deck.interactive.html
python3 scripts/audit_interactive_deck.py --manifest examples/interactive-deck/deck.json --audit-out build/project-relay-audit
```

The first command is always the distributable baseline. Explicit interactive
work adds the second artifact; it does not replace the first. Audit output is
author evidence, never an audience artifact.

## Closed v1 vocabulary

- Scene types: `evidence_only`, `state_toggle`, `slider_model`, `score_model`,
  `drilldown`, `accordion`.
- Model kinds: `linear`, `lookup`, `piecewise`, `operation_graph`, `score_sum`,
  `state_map`.
- Controls: `range`, `segmented`, `toggle`, `select`.
- View components: `ranked_list`, `bar_compare`, `dot_plot`,
  `recommendation_panel`.

The compiler enforces the supported pairs: state toggles use ranked lists, bar
comparisons, or dot plots; slider models use bar comparisons or dot plots;
score models use recommendation panels. Evidence, drilldown, and accordion
have their own fixed semantic views. An unsupported pair is a build error.

## Numerical and decision contract

In v1, `initialState` equals `printState`. Quantities, units, domains,
baselines, rounding, and decision thresholds are typed and fixed before the
runtime starts. Decimal strings remain exact; JavaScript does not invent a
second formula. A decision declares the outcome text for below/exact/above
states, and static, live, print, and accessible summaries must agree.

Use a fixed scale across state changes. A two-dimensional plot may use two
spatial axes and one scenario control; add another page rather than another
analytical axis.

## Evidence and lineage

### Optional visible model context in the static spec

The static `spec` may add `model_context` to explain a model instead of showing
only its print-state result. This is not a new scene field. The builder validates
the extra proof against the scene's executable model; a mismatch fails the build.

- `scatter`: `{"kind":"linear_model","intercept":-1.5,"coefficient":0.06}`
  draws a full single-input model line and the declared decision hurdle. Its
  point must reference that input on x and that output on y. Other model kinds
  cannot use this context.
- `summary_strip`: `{"kind":"score_breakdown","components":[{"label":"Manager capacity","value":18}],"comparison":{"label":"Without manager capacity","remove_index":0}}`
  uses one component per score control, in declaration order, with exact labels
  and print-state contributions. The removed component must have a reachable
  zero-point control alternative. The example above shows the shape only;
  a real four-control model needs all four components.
- Metric `bullet_list`: `{"kind":"scenario_compare","label":"Technician constrained","values":[{"item_id":"north","value":82,"rank":1}]}`
  draws paired base/alternate bars. Include every item exactly once. The label
  must identify an authored control option, and the values/ranks must match its
  resolved scene state. Both series use the same zero baseline and domain.

See Project Relay pages 4–6 for complete runnable examples. `presentation:
"editorial"` is a separate opt-in static layout for cover, multi-block summary,
and closing pages; it changes composition, not the scene's facts.

Every value is labelled `measured`, `estimated`, `assumed`, or `illustrative`.
Declare source and assumption records, connect every leaf to its lineage, and
show the badge in both visual and semantic output. Source links are optional,
validated `https:` or bounded `mailto:` links and open only after an explicit
presenter action. Missing, unsafe, or unverified links render as text.

## Demo and build limits

`targetKey` identifies a stable visual/control target. `stepKey` identifies a
presenter demo action. They are separate registries. Demo actions are limited
to `set`, `select`, evidence/panel open and close, bounded `wait`, and terminal
`goto`. Deck/state/string/SVG/demo/audit budgets fail at build time. Invalid
JSON, duplicate IDs, unknown fields, unsafe paths, unsupported pairs, stale
fallbacks, or incomplete lineage produce a nonzero exit and no partial output.

Continue with [interaction selection](interaction-selection.md),
[accessibility](interactive-accessibility.md), and
[presenter operation](presenter-operation.md).
