# Prompt Templates

## Structured Slide Spec

Use this when the user needs a reproducible slide direction.

```text
Strategic question:
[Decision the slide supports]

Insight headline:
[One sentence that states the answer or tension]

Recommended visualization:
[Pattern name from visualization-patterns.md]

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
```

## Image Generation Prompt

Use this when the user explicitly wants an image-generation prompt.

```text
Create an executive-ready strategy consulting visualization in landscape 16:9 format.
Use a white background, black text, royal blue (#1E3A8A) primary accents, and restrained grey hierarchy.
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
