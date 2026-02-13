# McKinsey/BCG Style Visualization - Claude Code Skill

> Professional consulting-style data visualization and infographics creation skill for strategic analysis and executive presentations.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code](https://img.shields.io/badge/Claude-Code%20Skill-blue.svg)](https://code.claude.com/)

## Overview

This Claude Code Skill enables the creation of high-density, professional consulting presentation slides and data visualizations in the style of top-tier strategy firms (McKinsey, BCG, Bain). The output combines institutional authority with editorial financial-report aesthetics, designed for boardroom-ready executive presentations.

## Features

- **11 Visualization Types:** Time-series growth charts, gap/funnel visualizations, before/after comparisons, market share charts, investment infographics, timelines, comparison diagrams, strategic frameworks, competitive benchmarking tables, waterfall charts, and cover slides
- **Detailed Design System:** Comprehensive color palettes with hex codes, typography specifications, and aspect ratio standards
- **Prompt Engineering Templates:** Ready-to-use templates for generating each visualization type
- **Strategic Framing Guidance:** Instructions for creating hypothesis-driven, insight-led visualizations
- **Quality Checklist:** Comprehensive checklist to ensure professional output

## Installation

### Method 1: Clone this repository

```bash
# Clone to your personal skills directory
git clone https://github.com/kgraph57/Helix.git ~/.claude/skills/mckinsey-style-visualization

# Or clone to a project-specific skills directory
git clone https://github.com/kgraph57/Helix.git .claude/skills/mckinsey-style-visualization
```

### Method 2: Manual installation

1. Download the `SKILL.md` file from this repository
2. Create a directory in your Claude skills folder:
   ```bash
   mkdir -p ~/.claude/skills/mckinsey-style-visualization
   ```
3. Copy `SKILL.md` into the directory

### Method 3: Direct download

```bash
# Personal skills
mkdir -p ~/.claude/skills/mckinsey-style-visualization
curl -o ~/.claude/skills/mckinsey-style-visualization/SKILL.md https://raw.githubusercontent.com/kgraph57/Helix/main/SKILL.md

# Project skills
mkdir -p .claude/skills/mckinsey-style-visualization
curl -o .claude/skills/mckinsey-style-visualization/SKILL.md https://raw.githubusercontent.com/kgraph57/Helix/main/SKILL.md
```

## Usage

### Automatic Invocation

Claude will automatically use this skill when you ask for:
- Strategic analysis visualizations
- Competitive benchmarking charts
- Executive presentation slides
- Market analysis infographics
- Consulting-style data visualizations

Example prompts:
- "Create a McKinsey-style competitive benchmarking table comparing these AI models"
- "Generate a professional consulting-style timeline showing our product milestones"
- "Build a strategic framework visualization for market positioning analysis"

### Manual Invocation

You can also invoke the skill directly using the slash command:

```
/mckinsey-style-visualization [your request]
```

Example:
```
/mckinsey-style-visualization Create a before/after comparison showing ROI improvement
```

## When to Use This Skill

✅ **Use this skill when:**
- Creating strategic analysis presentations for executive audiences
- Developing competitive benchmarking visualizations
- Building data-driven consulting deliverables
- Designing market analysis infographics
- Producing high-information-density business reports
- Visualizing complex strategic frameworks and comparisons

❌ **Do NOT use for:**
- Marketing materials or promotional content
- Startup pitch decks with bright colors
- Decorative or artistic visualizations
- Low-information-density slides

## Visualization Types

This skill supports 11 professional visualization types:

1. **Time-Series Growth Charts** - Adoption rates, market growth, performance over time
2. **Gap/Funnel Visualizations** - Dramatic differences, maturity gaps, conversion funnels
3. **Before/After Comparisons** - Impact, ROI, performance improvement
4. **Market Share / Adoption Rate** - Percentage breakdowns, market penetration
5. **Investment / Scale Infographics** - Organizational investments, scale of operations
6. **Timeline Visualizations** - Chronological events, policy changes, milestones
7. **Comparison / Contrast Diagrams** - Regional, organizational, or strategic differences
8. **Strategic Frameworks** - 2×2 matrices, positioning analysis, capability assessment
9. **Competitive Benchmarking Tables** - Multi-dimensional comparisons across players
10. **Waterfall Charts** - Cumulative effects, step-by-step changes, variance analysis
11. **Cover Slides** - Professional opening slides for consulting presentations

## Design Principles

### Color Palette

**Content Slides:**
- Background: Pure White `#FFFFFF`
- Primary Text: Sharp Black `#000000`
- Primary Accent: Deep Royal Blue `#1E3A8A`
- Secondary Accent: Medium Blue `#2563EB`
- Grey Hierarchy: `#374151`, `#6B7280`, `#D1D5DB`, `#F3F4F6`

**Cover Slides:**
- Background: Deep Navy Blue `#1E3A5F`
- Primary Text: Pure White `#FFFFFF`
- Secondary Text: Light Grey `#E5E7EB`
- Optional Accent: Subtle Gold `#D4AF37`

### Typography

**Content Slides:**
- Headlines: Serif (Times New Roman / Georgia) - Bold
- Body Text: Sans-serif (Inter / Helvetica / Arial) - Regular
- Data Labels: Sans-serif - Medium or Semibold

**Cover Slides:**
- Main Title: Serif - Regular or Medium (48-72pt equivalent)
- Subtitle: Sans-serif - Light or Regular (18-24pt equivalent)
- Metadata: Sans-serif - Light (10-12pt equivalent)

### Aspect Ratio

- **Default:** Landscape 16:9 (recommended for all visualizations)
- **Alternative:** Landscape 3:2
- **Avoid:** Portrait orientation (unless specifically requested)

## Examples

### Example 1: Time-Series Growth Chart
```
Create a professional consulting-style time-series growth chart showing AI adoption 
from 38% in 2023 to 72% in 2025. Use landscape 16:9 format, white background, 
royal blue line chart, with annotation "2x growth in 2 years".
```

### Example 2: Competitive Benchmarking Table
```
Create a McKinsey-style competitive benchmarking table comparing 5 GenAI video models 
across architecture, temporal consistency, and prompt adherence. Use landscape 16:9 format, 
white background, hairline borders, and clear ranking indicators.
```

### Example 3: Cover Slide
```
Create a professional consulting-style cover slide with deep navy blue background, 
large serif title "The Future of AI in Healthcare: Strategic Implications for 2026", 
and subtitle "Executive Summary for Board Review".
```

## Quality Checklist

Before delivering any visualization, verify:

- [ ] Aspect ratio: Landscape orientation used
- [ ] Color palette: White background, black text, royal blue accents (for content slides)
- [ ] Typography: Serif headline, sans-serif data labels
- [ ] Data accuracy: All numbers, percentages, and labels are correct
- [ ] Strategic insight: Headline is insight-driven, not descriptive
- [ ] Visual clarity: No clutter, every element serves a purpose
- [ ] Annotations: Key insights and context provided
- [ ] Consistency: If multiple charts, all follow same design system

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

**KEN**  
小児科医 | アートコレクター | クロスフィッター

## Acknowledgments

- Inspired by McKinsey & Company presentation style guidelines
- Based on BCG visual identity and data visualization standards
- Influenced by Financial Times editorial design principles
- Informed by Harvard Business Review chart design best practices

## Related Skills

This skill works well with:
- **design-sensei** - Additional design principles and accessibility
- **paper-presentation-slides** - Academic presentation context
- **paper-article-generator** - Article-embedded visualizations

## Version History

- **v1.1** (2026-02-11): Added Type 11 Cover Slide, detailed color palette with hex codes, enhanced typography specifications, and cover slide prompt templates
- **v1.0** (2026-02-11): Initial skill creation with comprehensive visualization types, aspect ratio standards, and prompt engineering templates

## Support

If you encounter any issues or have questions, please [open an issue](https://github.com/kgraph57/Helix/issues) on GitHub.

---

**Note:** This skill is designed for use with Claude Code and follows the [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) open standard.
