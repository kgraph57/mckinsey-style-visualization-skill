# Document Type Profiles

The same visual discipline adapts to many document formats. Pick the profile that matches the deliverable, then keep the core rules from `references/style-system.md`: insight-led headline, honest scales, restrained palette, explicit assumptions.

## Profile Table

| Profile | Canvas | Density | Tone | Preferred Patterns |
| --- | --- | --- | --- | --- |
| Board / executive deck | 16:9 landscape | High | Decisive, analytical | Waterfall, benchmark, 2x2, summary strip |
| Internal report / memo | A4 portrait, inline figures | Medium | Neutral, factual | Time-series, gap, scorecard, tables |
| Research report / whitepaper | A4 portrait, numbered figures | High | Cautious, sourced | Distribution, scatter, heatmap, methodology flow |
| Sales proposal / pitch | 16:9 landscape | Medium | Confident, customer-framed | Before-after, contrast, timeline, funnel |
| Project status / steering | 16:9 landscape or A4 | High | Direct, risk-aware | Gantt / roadmap, scorecard, heatmap, decision tree |
| Training / education material | 16:9 or 4:3 landscape | Low-medium | Patient, sequential | Process flow, cycle, concept map, before-after |
| Technical documentation | Inline figures, flexible width | Medium | Precise, unambiguous | Architecture / system map, process flow, decision tree, hierarchy |
| One-pager / fact sheet | A4 portrait, single page | Very high | Compressed, scannable | Summary strip, scorecard, mini-charts |
| Infographic / public explainer | Vertical 4:5 or 9:16 | Low | Accessible, plain-language | Pyramid, cycle, annotated map, big-number blocks |
| Policy brief / public sector | A4 portrait | Medium | Balanced, evidence-led | Timeline, contrast, gap, distribution |
| Academic / clinical summary | A4 portrait or poster | High | Conservative, caveated | Distribution, before-after, methodology flow, tables |
| Personal notes / study aids | Flexible | Low | Informal but accurate | Concept map, hierarchy, checklist, timeline |

## Profile Notes

### Board / Executive Deck

The default profile and the strictest. One message per slide, decision-linked headlines, and the full quality rubric. Use `references/iterative-review-loop.md` for polished work.

### Internal Report / Memo

Figures support running text instead of standing alone. Keep figure titles descriptive-plus-insight ("Churn concentrated in SMB tier") and number figures so prose can reference them. Smaller headline sizes than slides.

### Research Report / Whitepaper

Every figure needs a source or methodology note. Show uncertainty honestly: ranges, confidence notes, sample sizes. Avoid persuasion-first layouts; let structure carry the argument.

### Sales Proposal / Pitch

Frame headlines around the customer's outcome, not the seller's features. Before-after and contrast patterns dominate. Keep claims tied to evidence the customer can verify; flag estimates clearly.

### Project Status / Steering

Status visuals must show plan vs. actual, not just plan. Use consistent RAG conventions sparingly (red only for true risk, per the style system). Always include the decision or ask, not just status.

### Training / Education Material

Lower density: one concept per visual, generous whitespace, sequential build. Prefer concrete examples inside the visual. Repetition of a consistent visual grammar across lessons beats variety.

### Technical Documentation

Precision over polish: exact labels, real component names, directional arrows with meaning. System maps and flows should be reproducible as diagram-as-code (Mermaid, PlantUML) when the user works in a repo. State the diagram source format in the spec.

### One-Pager / Fact Sheet

Everything competes for one page: use a strict grid, 2-4 compact visuals, and one dominant number or claim. Cut anything the reader cannot absorb in 60 seconds.

### Infographic / Public Explainer

Plain language replaces business jargon. Bigger type, fewer numbers, every number rounded to what a general reader retains. Vertical scroll formats read top-to-bottom as a single narrative.

### Policy Brief / Public Sector

Balanced presentation of trade-offs; avoid advocacy styling. Cite public sources. Accessibility matters: high contrast, no color-only encoding.

### Academic / Clinical Summary

Conservative claims, explicit methods, no decorative emphasis. Visuals for structure and findings only; the skill must not generate clinical or scientific conclusions beyond user-provided content.

### Personal Notes / Study Aids

The lightest profile: speed over polish. Concept maps, hierarchies, and checklists that aid recall. Style rules relax, but accuracy rules never do.

## Japanese Business Document Profiles

Japanese workplaces use document formats with conventions of their own. Apply these on top of the base profiles; use sans-serif type for Japanese text and increase sizes 10-20% per the style system.

| Profile | Base Profile | Key Conventions |
| --- | --- | --- |
| 稟議書 (ringi approval request) | Internal report / memo | A4 portrait, one page preferred. Lead with the request and amount, then background, options considered, risks, and approval line. One compact visual (cost comparison or gap) beats many. |
| 週報・月報 (weekly/monthly report) | Internal report / memo | Fixed recurring structure: progress vs. plan, issues, next actions. Use the same KPI scorecard or gantt layout every period so deltas are instantly visible. |
| 役員会・経営会議資料 (board/executive meeting) | Board / executive deck | Often A4 landscape or 16:9. One decision per page, conclusion first (結論ファースト). Appendix carries detail; the body stays at one message per visual. |
| 学会抄録・抄読会 (conference abstract / journal club) | Academic / clinical summary | Methods and limitations stated explicitly. Before-after and distribution patterns; no claims beyond the cited study. Keep the original study's units and population visible. |
| 社内勉強会資料 (internal study session) | Training / education material | Lower formality, one concept per slide, concrete examples. Concept maps and process flows; encourage questions with an explicit "discussion" slide. |
| 提案書 (client proposal) | Sales proposal / pitch | Customer's issue first, proposal second, evidence third. Contrast and before-after patterns; pricing on its own page with assumptions itemized. |

## Adapting the Output Contract

The output contract in `SKILL.md` generalizes across profiles:

- `Strategic question` becomes the reader's key question or job for non-strategy documents.
- `Slide spec` becomes a figure, page, or diagram spec with the profile's canvas.
- `Quality check` always applies; reinterpret "Strategy" as message clarity for non-decision documents.
