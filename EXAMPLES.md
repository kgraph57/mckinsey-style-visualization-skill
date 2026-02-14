# Usage Examples

This document provides practical examples of using the McKinsey/BCG Style Visualization skill in Claude Code.

## Table of Contents

- [Basic Usage](#basic-usage)
- [Visualization Type Examples](#visualization-type-examples)
- [Real-World Scenarios](#real-world-scenarios)
- [Advanced Techniques](#advanced-techniques)

## Basic Usage

### Automatic Invocation

Claude will automatically use this skill when you ask for consulting-style visualizations:

```
Create a professional consulting-style chart showing our Q4 revenue growth
```

```
Generate a McKinsey-style competitive analysis comparing these three companies
```

```
Build a strategic framework visualization for market positioning
```

### Manual Invocation

You can also invoke the skill directly using the slash command:

```
/mckinsey-style-visualization Create a timeline showing our product milestones for 2025
```

## Visualization Type Examples

### 1. Time-Series Growth Chart

**Scenario:** Show AI adoption growth over time

**Prompt:**
```
Create a professional consulting-style time-series growth chart in landscape 16:9 format.
White background, black text, royal blue (#1E3A8A) line chart.
Serif headline in bold: "AI Adoption Accelerates: From Experimentation to Enterprise Scale"
X-axis: 2023, 2024, 2025
Y-axis: Adoption Rate (%) with gridlines every 20%
Large percentage labels above data points: 38% (2023), 55% (2024), 72% (2025)
Annotation box in top right: "2x growth in 2 years"
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Quarterly business reviews, investor presentations, strategic planning

---

### 2. Gap/Funnel Visualization

**Scenario:** Highlight the maturity gap in AI implementation

**Prompt:**
```
Create a professional consulting-style gap visualization in landscape 16:9 format.
White background, black text. Serif headline in bold: "The AI Maturity Gap: Most Organizations Stuck in Pilot Phase"
Two horizontal bars:
- Top bar (royal blue #1E3A8A): 90% - "Organizations using AI"
- Bottom bar (light grey #D1D5DB): 1% - "Organizations with mature AI operations"
Extreme contrast in bar lengths to emphasize gap.
Large percentage labels on right side of each bar.
Annotation below: "Only 1 in 90 organizations have scaled AI beyond pilots"
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Change management presentations, strategic recommendations, board reports

---

### 3. Before/After Comparison

**Scenario:** Demonstrate training impact on diagnostic accuracy

**Prompt:**
```
Create a professional consulting-style before/after comparison chart in landscape 16:9 format.
White background, black text. Serif headline in bold: "AI-Assisted Training Drives 58% Improvement in Diagnostic Accuracy"
Two vertical bars side by side:
- Left bar (grey #6B7280): 50% - labeled "Before Training"
- Right bar (royal blue #1E3A8A): 78.8% - labeled "After Training"
Curved arrow between bars with improvement metric: "+28.8 points"
Y-axis with clear scale from 0 to 100%
Annotation box: "RCT study with 200 physicians, 20-hour training program"
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** ROI presentations, program evaluation, impact reports

---

### 4. Market Share / Adoption Rate

**Scenario:** Show medical school AI curriculum adoption

**Prompt:**
```
Create a professional consulting-style market share visualization in landscape 16:9 format.
White background, black text. Serif headline in bold: "Three-Quarters of US Medical Schools Have Adopted AI Curriculum"
Left side: Donut chart with 77% in royal blue (#1E3A8A), 23% in light grey (#D1D5DB)
Center of donut: "77%" in large text
Right side: Key statistics in large text:
- "77% Adopted AI curriculum"
- "23% No formal AI training"
- "150+ Medical schools surveyed"
Legend with color-coded boxes below chart
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Market analysis, competitive intelligence, sector reports

---

### 5. Investment / Scale Infographic

**Scenario:** Compare healthcare AI investments

**Prompt:**
```
Create a professional consulting-style investment comparison infographic in landscape 16:9 format.
White background, black text. Serif headline in bold: "Healthcare AI Investment: Scale vs. Scope"
Horizontal layout with vertical divider in center
Left section - Kaiser Permanente:
- Hospital icon in royal blue
- "40 hospitals" in large text
- "600+ facilities" below
- "Integrated care network" in smaller text
Right section - Mayo Clinic:
- Research icon in royal blue
- "$1B+ invested" in large text
- "200+ AI projects" below
- "Research-focused approach" in smaller text
Hairline divider between sections
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Investment memos, strategic partnerships, M&A analysis

---

### 6. Timeline Visualization

**Scenario:** Show 2025 medical education AI milestones

**Prompt:**
```
Create a professional consulting-style timeline visualization in landscape 16:9 format.
White background, black text. Serif headline in bold: "2025: The Year AI Integration Became Standard in Medical Education"
Horizontal timeline with three circular nodes in royal blue (#1E3A8A)
Event 1: Icon above, "AAMC Guidelines" above line, "July 2025" below line
Event 2: Icon above, "Stanford Curriculum Launch" above line, "September 2025" below line
Event 3: Icon above, "AMA Certification" above line, "November 2025" below line
Connecting line in royal blue between nodes
Clean sans-serif labels
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Project planning, roadmap presentations, historical analysis

---

### 7. Comparison / Contrast Diagram

**Scenario:** Compare US vs. Japan AI adoption in healthcare

**Prompt:**
```
Create a professional consulting-style comparison diagram in landscape 16:9 format.
White background, black text. Serif headline in bold: "AI in Healthcare: The US-Japan Implementation Gap"
Split design with vertical divider in center
Left side - US/Global Leaders:
- Header: "United States"
- Bullet points with icons in royal blue:
  - "72% of hospitals using AI"
  - "77% of medical schools with AI curriculum"
  - "$1B+ in research funding"
Right side - Japan:
- Header: "Japan"
- Question marks and sparse data:
  - "Status unclear"
  - "Limited public data"
  - "Regulatory framework under development"
High contrast between data-rich left and sparse right
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Market entry analysis, competitive positioning, regional strategy

---

### 8. Strategic Framework (2×2 Matrix)

**Scenario:** Position GenAI video model competitors

**Prompt:**
```
Create a professional consulting-style 2×2 strategic framework in landscape 16:9 format.
White background, black text. Serif headline in bold: "GenAI Video Market: Technical Leaders Face Ecosystem Challenges"
X-axis: "Market Share & Ecosystem" (Low to High)
Y-axis: "Technical Capability" (Low to High)
Thin vector lines for grid in light grey
Four quadrants with labels:
- Top-left: "Innovators" (Seedance 2.0, Kling AI)
- Top-right: "Leaders" (empty)
- Bottom-left: "Challengers" (Luma Dream Machine)
- Bottom-right: "Fast Followers" (Runway Gen-3, Pika 2.0)
Position markers as circles with company names
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Strategic planning, competitive analysis, portfolio review

---

### 9. Competitive Benchmarking Table

**Scenario:** Compare GenAI video models across dimensions

**Prompt:**
```
Create a professional consulting-style competitive benchmarking table in landscape 16:9 format.
White background, black text. Serif headline in bold: "GenAI Video Models: Technical Benchmarking Reveals Clear Leaders"
Multi-row, multi-column table with hairline borders in light grey (#D1D5DB)
Columns: Model | Architecture | Temporal Consistency | Prompt Adherence | Overall Score
Rows:
- Seedance 2.0 | DiT-based | 9.2/10 | 8.8/10 | 9.0/10
- Kling AI | Proprietary | 8.9/10 | 8.5/10 | 8.7/10
- Runway Gen-3 | Diffusion | 8.1/10 | 8.9/10 | 8.5/10
- Pika 2.0 | Hybrid | 7.8/10 | 8.2/10 | 8.0/10
- Luma Dream | Transformer | 7.5/10 | 7.9/10 | 7.7/10
Color coding: Top scores in royal blue (#1E3A8A), others in black
Numeric alignment, clear hierarchy
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Vendor selection, technology assessment, procurement decisions

---

### 10. Waterfall Chart

**Scenario:** Show revenue bridge from Q1 to Q4

**Prompt:**
```
Create a professional consulting-style waterfall chart in landscape 16:9 format.
White background, black text. Serif headline in bold: "Q4 Revenue Growth Driven by Enterprise Expansion"
Horizontal bars showing incremental changes:
- Starting bar: "Q1 Revenue: $10M" (royal blue #1E3A8A)
- Positive bar: "+$3M New Customers" (royal blue #1E3A8A)
- Positive bar: "+$2M Expansion" (royal blue #1E3A8A)
- Negative bar: "-$0.5M Churn" (grey #6B7280)
- Ending bar: "Q4 Revenue: $14.5M" (royal blue #1E3A8A)
Connecting lines between bars in light grey
Clear labels for each step
Y-axis from $0 to $15M
Clean, minimal, institutional aesthetic. No gradients, no decorative elements.
```

**Use case:** Financial reporting, variance analysis, performance reviews

---

### 11. Cover Slide

**Scenario:** Create opening slide for strategic presentation

**Prompt:**
```
Create a professional consulting-style cover slide in landscape 16:9 format.
Deep navy blue background (#1E3A5F) with subtle gradient to (#2C4A6F).
Large serif font title in white (#FFFFFF), centered: "The Future of AI in Healthcare"
Subtitle in smaller sans-serif font, light grey (#E5E7EB): "Strategic Implications for 2026"
Metadata at bottom in small text: "February 2026 | Executive Board Review | Confidential"
Optional subtle gold accent (#D4AF37) as thin horizontal line above title
Minimal graphics — focus on elegant typography
Clean, institutional, boardroom-ready aesthetic.
```

**Use case:** Executive presentations, board meetings, client deliverables

---

## Real-World Scenarios

### Scenario 1: Quarterly Business Review

**Objective:** Present Q4 performance to executive team

**Visualizations needed:**
1. Cover slide with presentation title
2. Time-series growth chart showing quarterly revenue
3. Waterfall chart explaining revenue drivers
4. Before/after comparison showing KPI improvements
5. Gap visualization showing target vs. actual performance

**Workflow:**
```
/mckinsey-style-visualization Create a cover slide for Q4 2025 Business Review

/mckinsey-style-visualization Create a time-series chart showing quarterly revenue from Q1 to Q4

/mckinsey-style-visualization Create a waterfall chart showing revenue bridge from Q1 ($10M) to Q4 ($14.5M)

/mckinsey-style-visualization Create a before/after comparison showing customer satisfaction improvement from 72% to 89%

/mckinsey-style-visualization Create a gap visualization comparing Q4 target (95%) vs. actual (89%)
```

---

### Scenario 2: Market Entry Analysis

**Objective:** Evaluate entering the Japanese healthcare AI market

**Visualizations needed:**
1. Comparison diagram (US vs. Japan market maturity)
2. Strategic framework (competitive positioning)
3. Timeline (regulatory milestones)
4. Investment infographic (required resources)

**Workflow:**
```
/mckinsey-style-visualization Create a comparison diagram showing US (mature, $5B market, 70% adoption) vs. Japan (emerging, $500M market, 15% adoption)

/mckinsey-style-visualization Create a 2×2 strategic framework positioning our company and 4 competitors on market share vs. technical capability

/mckinsey-style-visualization Create a timeline showing Japan regulatory approval process from Q1 2026 to Q4 2027

/mckinsey-style-visualization Create an investment infographic comparing required investment for US expansion ($2M) vs. Japan entry ($8M)
```

---

### Scenario 3: Technology Assessment

**Objective:** Select GenAI video generation platform for marketing

**Visualizations needed:**
1. Competitive benchmarking table
2. Strategic framework (positioning)
3. Before/after comparison (expected improvement)

**Workflow:**
```
/mckinsey-style-visualization Create a competitive benchmarking table comparing 5 GenAI video models across architecture, consistency, prompt adherence, and pricing

/mckinsey-style-visualization Create a 2×2 framework positioning these models on technical capability vs. ecosystem maturity

/mckinsey-style-visualization Create a before/after comparison showing expected video production time reduction from 40 hours to 8 hours
```

---

## Advanced Techniques

### Batch Generation

When creating multiple visualizations for a single presentation:

1. **Plan the narrative flow** first
2. **Generate all visualizations** in sequence
3. **Maintain consistency** across all charts
4. **Review as a set** before finalizing

### Customization

You can customize the standard templates by:

- Adjusting color intensity (lighter or darker blues)
- Modifying font sizes for different contexts
- Adding specific data points relevant to your analysis
- Incorporating your organization's branding (while maintaining the consulting aesthetic)

### Integration with Other Skills

Combine with other Claude Code skills for enhanced workflows:

```
# Use with design-sensei for accessibility review
/design-sensei Review this McKinsey-style visualization for accessibility

# Use with paper-presentation-slides for academic context
/paper-presentation-slides Incorporate this consulting-style chart into an academic presentation
```

---

## Tips for Best Results

1. **Be specific with data:** Provide exact numbers, labels, and annotations
2. **State the insight:** Always include a hypothesis-driven headline
3. **Choose the right type:** Match visualization type to your data and message
4. **Maintain consistency:** Use the same aspect ratio and color palette across a set
5. **Test and iterate:** Generate, review, and refine as needed

---

For more information, see:
- [README.md](README.md) - Overview and installation
- [SKILL.md](SKILL.md) - Complete skill documentation
- [INSTALLATION.md](INSTALLATION.md) - Installation guide
