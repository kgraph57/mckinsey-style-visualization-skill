# Prompt Templates

## Structured Slide Spec

Use this when the user needs a reproducible slide direction.

```text
Strategic question:
[Decision the slide supports]

Insight headline:
[One sentence stating a single proposition — one answer or one tension. Never
join several claims with "and"; when three things are true, the headline
states the governing thought and the body blocks carry the three proofs.]

Recommended visualization:
[Pattern name from visualization-patterns.md — say whether it is renderer-supported or spec-only]

Slide spec:
- Canvas: 16:9 landscape
- Layout: [left/right, top/bottom, grid, matrix, table]
- Primary visual: [chart or diagram details]
- Data labels: [exact labels and formats]
- Annotations: [one to three implications]
- Source note: [source or "User-provided data; assumptions noted below"]

Data and assumptions:
- [Input data used]
- [Missing data or assumptions]

Quality check:
- Strategy:
- Data:
- Visual hierarchy:
- Portability:
- Safety:

Expert review notes:
- Assumption challenged: [most fragile assumption and how it is labeled]
- Reader fit: [primary audience and likely misunderstanding]
- Accessibility/localization: [color, label, jargon, or translation check]
- Counterpoint: [what would change the recommendation]
```

## Universal Visual Spec

Use this for any document type beyond slides: reports, proposals, training materials, technical docs, one-pagers, infographics. Pick the canvas from `references/document-type-profiles.md`.

```text
Reader question:
[What the reader must decide, understand, or do]

Message headline:
[One sentence that states the answer or takeaway]

Document profile:
[Profile from document-type-profiles.md]

Recommended visualization:
[Pattern name from visualization-patterns.md]

Visual spec:
- Canvas: [16:9 slide / A4 portrait figure / vertical infographic / inline diagram / flexible]
- Layout: [geometry: flow direction, grid, levels, axes]
- Primary visual: [chart or diagram details]
- Labels: [exact labels and formats; plain language for general readers]
- Annotations: [one to three takeaways or callouts]
- Source note: [source or "User-provided content; assumptions noted below"]
- Render target: [image prompt / SVG / Mermaid / slide tool / designer handoff]

Content and assumptions:
- [Input content used]
- [Missing information or assumptions]

Quality check:
- Message clarity:
- Content integrity:
- Visual hierarchy:
- Portability:
- Safety:

Expert review notes:
- Assumption challenged: [most fragile assumption and how it is labeled]
- Reader fit: [primary audience and likely misunderstanding]
- Accessibility/localization: [color, label, jargon, or translation check]
- Counterpoint: [what would change the recommendation]
```

## Diagram-as-Code Spec

Use when the user works in a repo or wants an editable diagram. Emit Mermaid (default) or another requested format alongside the spec.

```text
Recommended visualization: [process flow / decision tree / hierarchy / concept map / timeline / Gantt]
Diagram source format: [mermaid flowchart / sequenceDiagram / gantt / mindmap]
Diagram source:
[fenced mermaid block with real labels, direction, and styling kept minimal]
Notes: [what was simplified and why]
```

## Image Generation Prompt

Use this when the user explicitly wants an image-generation prompt.

```text
Create an executive-ready strategy consulting visualization in landscape 16:9 format.
Use a white background, black text, navy (#15296B) primary accents, and restrained grey hierarchy.
Headline in bold serif font: "[Insight headline]"
Visualization type: [pattern]
Data: [exact values, labels, and units]
Layout: [specific geometry]
Annotations: [key implication]
Style: analytical, institutional, boardroom-ready, high information density, precise alignment.
Avoid decorative elements, neon colors, fake logos, and affiliation marks.
```

## Pattern-Specific Starters

### Time-Series Growth

```text
Create a 16:9 strategy consulting time-series chart.
X-axis: [periods]
Y-axis: [metric and units]
Series: [values]
Direct labels: [key values]
Annotation: [inflection or strategic implication]
```

### Gap Visualization

```text
Create a 16:9 strategy consulting gap visualization.
Comparator A: [label and value]
Comparator B: [label and value]
Show horizontal bars with A in royal blue and B in light grey.
Gap label: [absolute and relative gap]
Strategic implication: [why the gap matters]
```

### Waterfall Chart

```text
Create a 16:9 strategy consulting waterfall chart.
Start: [label and value]
Drivers: [positive and negative changes]
End: [label and value]
Use blue for positive drivers, grey or muted red for negative drivers, and thin connector lines.
```

### Competitive Benchmark

```text
Create a 16:9 strategy consulting benchmark table.
Rows: [companies/options]
Columns: [decision criteria]
Highlight leaders in royal blue.
Add caveats for estimated or subjective metrics.
```

### Executive Summary Strip

```text
Create a 16:9 executive summary strip with [3-5] insight blocks.
Each block includes: claim, proof point, implication.
Use compact typography, vertical dividers, and one blue emphasis per block.
```

### Process Flow

```text
Create a [canvas] process flow diagram.
Steps: [ordered steps with owners]
Direction: [left-to-right or top-to-bottom]
Highlight: [bottleneck or decision point] in royal blue.
Annotation: [what the reader should fix or follow]
```

### Funnel

```text
Create a [canvas] funnel visualization.
Stages: [labels with absolute values]
Conversion labels: [stage-to-stage rates]
Annotation: [largest drop and its implication]
```

### Hierarchy / Tree

```text
Create a [canvas] hierarchy diagram.
Root: [top node]
Levels: [max 3 visible levels with sibling order rationale]
Highlight: [the node or branch that carries the message]
```

### Concept / System Map

```text
Create a [canvas] concept map.
Nodes: [up to ~12 entities]
Relationships: [labeled, typed connections]
Clusters: [spatial groupings]
Legend: [line styles per relationship type]
```

### Gantt / Roadmap

```text
Create a [canvas] roadmap.
Workstreams: [rows]
Phases: [bars with start/end]
Dependencies and gates: [explicit markers]
Plan vs. actual: [if tracking, show both]
```

### Heatmap Matrix

```text
Create a [canvas] heatmap.
Rows: [dimension 1, sorted meaningfully]
Columns: [dimension 2]
Values: [metric and scale]
Use a single-hue blue ramp; label the extremes with actual values.
Annotation: [the hot spot that matters]
```

### KPI Scorecard

```text
Create a [canvas] KPI scorecard.
Groups: [metric themes]
Per metric: value, trend, target, status.
Reserve color for status against target only.
Annotation: [the one metric demanding action]
```

### Decision Tree

```text
Create a [canvas] decision tree.
Root question: [yes/no or small-choice question]
Branches: [each labeled with the answer]
Leaves: [concrete actions only]
Highlight: [the most common path]
```

### Infographic Block

```text
Create a vertical [4:5 or 9:16] explainer infographic.
Sections top to bottom: [hook number or claim, 2-4 supporting blocks, takeaway]
Plain language labels; numbers rounded for general readers.
Keep the strategy-consulting palette but increase type size and whitespace.
```
