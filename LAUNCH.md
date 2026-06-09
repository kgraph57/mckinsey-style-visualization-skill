# Launch Kit

Use this file to announce releases, collect demand signals, and avoid rewriting launch copy from scratch.

## Launch Goal

Get the skill in front of agent users who create business, strategy, board, investment, or consulting-style materials.

Primary outcome: marketplace listings, GitHub stars, forks, saves, replies, and inbound requests for rendered slide examples or paid templates.

## Release Copy (v1.7.0)

Attach the hero image (`assets/readme/hero-before-after.svg` exported to PNG) to every post. The image carries the message; the text supports it.

### Short Post

```text
I released Strategy Consulting Visualization Skill v1.7.0.

Messy notes in, board-ready slide out. It now renders actual SVG slides —
not just specs — for waterfalls, gaps, before/after, time series,
benchmark tables, summary strips, and process flows.

One command, zero dependencies:
python3 scripts/render_slide_spec.py spec.json

It also generalized beyond board slides: reports, proposals, training
materials, technical diagrams, and infographics, with input triage that
maps any input — numbers, prose, processes — to the right pattern.

https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### X Version (EN)

```text
v1.7.0: the skill now RENDERS slides, not just specs.

Messy notes -> consulting-style SVG slide, one command, zero deps.

- 7 rendered patterns (waterfall, gap, benchmark, flow...)
- 28 visualization patterns total
- works for reports, proposals, docs, infographics too
- input triage: feed it anything

https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### X Version (JP)

```text
v1.7.0をリリース。スペック生成だけじゃなく、実際にスライドを描画できるようになりました。

雑なメモ → コンサル風SVGスライド。1コマンド、依存ライブラリゼロ。

- ウォーターフォール等7パターンをレンダリング
- 可視化パターンは全28種
- 役員会資料だけでなくレポート・提案書・研修資料・図解にも対応
- 数値でも文章でもプロセスでも、何を投げてもOK

https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### Show HN Draft

```text
Title: Show HN: An agent skill that turns messy notes into consulting-style slides

First comment:
I kept seeing AI-generated business charts that looked like generic
dashboards, so I built a SKILL.md package that gives agents a stricter
operating system: insight-led headlines, honest scales, restrained
palette, explicit assumptions.

v1.7.0 adds a renderer — spec JSON to styled SVG slide, Python stdlib
only — plus input triage so it can visualize anything: metrics, prose,
processes, hierarchies, decision logic.

What it does NOT do: render PPTX, invent data, or imply affiliation
with any consulting firm. Scope and caveats are in the README.
```

### Reddit Draft (r/ClaudeAI)

```text
Title: I built a Claude skill that turns messy notes into board-ready slides (now with an actual SVG renderer)

Body: Walk through one real example end to end: paste raw notes, show
the generated spec, show the rendered SVG. Include the before/after
hero image. Close with the repo link and ask what patterns or document
types readers want next.
```

### LinkedIn Version

```text
I published Strategy Consulting Visualization Skill v1.7.0.

The skill helps AI agents turn raw input into executive-ready visuals.
New in this release: an SVG renderer (spec JSON to finished slide, no
dependencies), a Japanese README, and generalization beyond board
slides to reports, proposals, training materials, technical diagrams,
and infographics.

Use cases include board updates, vendor selection, investment memos,
capacity gaps, process bottleneck analysis, and competitive benchmarks.

Repository:
https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### Community Post

```text
I built an open-source SKILL.md package for professional visualization.

The goal: give an AI agent enough structure to turn any input into a
disciplined visual — insight-led headline, right pattern, honest data —
instead of a generic chart prompt.

What is included:
- portable SKILL.md entrypoint
- input triage: maps numbers, prose, processes to the right pattern
- 28 visualization patterns, 12 document-type profiles
- SVG renderer for 7 patterns (Python stdlib only)
- style system, prompt templates, quality rubric
- draft -> review -> revise examples and local validation

Repo:
https://github.com/kgraph57/mckinsey-style-visualization-skill
```

## Social Asset

Primary: `assets/readme/hero-before-after.svg` exported to PNG (messy notes -> rendered slide).
Secondary: `assets/social/launch-card.svg`.

Alt text: Strategy Consulting Visualization Skill turns raw notes into a rendered, board-ready SVG slide with one command, plus specs for reports, proposals, and infographics.

## 7-Day Launch Plan

| Day | Action | Success Signal |
| --- | --- | --- |
| 1 | Post short copy on X/Threads and LinkedIn | Replies, reposts, bookmarks |
| 1 | Submit to P0 marketplace targets | Submission received or listing live |
| 2 | Post community version in relevant agent/Claude/Codex communities | Comments asking how it works |
| 3 | Publish one mini case study: raw notes -> draft -> review -> revised spec | Saves and example requests |
| 4 | Submit to P1 marketplace targets | Additional listings |
| 5 | Ask 5 target users to try a board-update prompt | Usability feedback |
| 6 | Add any requested example scenario | New issue, fork, or PR |
| 7 | Summarize metrics and decide premium-pack scope | Evidence for next release |

## Metrics

Track these weekly:

| Metric | Why It Matters |
| --- | --- |
| GitHub stars | Lightweight discovery and trust signal |
| Forks | Developer interest |
| Issues/discussions | Real usage and confusion points |
| Marketplace listings | Distribution footprint |
| Marketplace installs/saves | Demand signal |
| Social bookmarks | Buyer/user intent |
| Replies requesting PPTX/PDF | Premium pack signal |
| Direct messages | Sales and acquisition signal |

Record the weekly numbers in [TRACTION.md](TRACTION.md).

## Launch Claims To Avoid

- Do not claim affiliation with any consulting firm.
- Do not claim the skill renders final PowerPoint decks by itself.
- Do not claim marketplace approval before a listing is live.
- Do not claim revenue or usage traction until tracked.

## Follow-Up Case Study Format

```text
Input:
[Paste 4-8 lines of raw business notes]

Draft:
[Show the first slide-spec output]

Review:
[Show 3-5 review findings]

Revision:
[Show the revised decision headline, chart choice, assumptions, and quality score]
```
