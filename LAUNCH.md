# Launch Kit

Use this file to announce releases, collect demand signals, and avoid rewriting launch copy from scratch.

## Launch Goal

Get the skill in front of agent users who create business, strategy, board, investment, or consulting-style materials.

Primary outcome: marketplace listings, GitHub stars, forks, saves, replies, and inbound requests for rendered slide examples or paid templates.

## Release Copy (v1.9.0)

Attach `assets/readme/demo.gif` to every post — the animated deck carries the message. For platforms that need stills, use the gallery SVGs exported to PNG.

### Show HN (Hacker News)

```text
Title: Show HN: Turn messy notes into board-ready slides – SVG, animated HTML, PDF (zero deps)

I built an agent skill + renderer that turns raw notes and metrics into
consulting-style slides. Everything is Python 3 stdlib — no installs, no
API keys, no network calls.

- 16 chart patterns render to real SVG (waterfall, 2x2, heatmap, small
  multiples, scatter...); the gallery in the README is committed renderer
  output, and CI fails if it drifts from the code.
- One command bundles slides into a self-contained animated HTML deck:
  staggered reveals, keyboard nav, and a print stylesheet so the browser
  exports it straight to PDF. SVGs also drop into PowerPoint/Keynote.
- Japanese business documents are first-class: CJK-aware wrapping,
  dedicated profiles for board papers and approval documents.
- The part I enjoyed most: I ran the whole visual system through a
  five-perspective design review (Tufte's data-ink rules, an ex-McKinsey
  chart lens, Swiss grid typography, FT data journalism, modern design
  engineering), and they found real bugs — waterfalls drawing off-canvas
  on negative bridges, palette colors that collapse in greyscale print,
  WCAG contrast failures. v1.9.0 ships every fix, with the integrity
  rules (Lie Factor, contrast, greyscale separation) asserted in tests
  instead of promised in prose.

https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### X Version (EN)

```text
Messy notes in. Board-ready slides out.

v1.9.0 of my strategy-visualization skill:
- 16 patterns render to real SVG (CI-verified gallery)
- 1 command -> animated HTML deck -> print -> PDF
- SVGs drop into PowerPoint / Keynote
- Japanese business docs supported (CJK wrapping that actually works)
- reviewed & hardened by a 5-perspective design panel (Tufte, ex-McKinsey, Swiss grid, FT, design engineering)

Zero dependencies. Zero API keys.
https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### X Version (JP)

```text
雑なメモを入れると、役員会スライドが出てくる。

v1.9.0の目玉:
- 16パターンを本物のSVGスライドに描画（ギャラリーはCIが鮮度検証）
- 1コマンドでアニメ付きHTMLデッキ → ブラウザ印刷でそのままPDF
- SVGはPowerPoint/Keynoteに直接挿入OK
- 日本語対応が本物（CJK折返し・稟議書/役員会資料プロファイル）
- Tufte・元McKinsey・スイス派・FT・デザインエンジニアの5視点パネルに酷評させて全部修正

依存ゼロ・APIキー不要。
https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### Reddit (r/ClaudeAI or r/LocalLLaMA)

```text
Title: I made my agent's charts survive a design audit — 5-perspective panel review, then fixed everything (open source, zero deps)

Most AI-generated charts look fine until someone checks the numbers. I
wanted charts I could defend, so after building a slide renderer for my
agent, I convened a brutal five-perspective design review — Tufte
data-ink rules, an ex-McKinsey chart discipline lens, Swiss grid
typography, FT-style data journalism, and modern design engineering.

They tore it apart (5.8/10 average): waterfalls drew off-canvas on
negative bridges, the palette collapsed in greyscale print, Japanese
text overflowed the canvas, heatmap text failed WCAG contrast.

v1.9.0 ships every fix, with the integrity rules asserted in the test
suite. It renders 16 chart patterns to SVG, bundles them into animated
HTML decks (print -> PDF), and the whole thing is Python stdlib.

The full panel transcripts and fix list are in the changelog. Repo:
https://github.com/kgraph57/mckinsey-style-visualization-skill
```

## Release Copy (v1.8.0)

Attach the hero image (`assets/readme/hero-before-after.svg` exported to PNG) to every post. The image carries the message; the text supports it.

### Short Post

```text
I released Strategy Consulting Visualization Skill v1.8.0.

Messy notes in, board-ready slide out. It now renders actual SVG slides —
not just specs — across 12 patterns: waterfalls, funnels, gantts,
heatmaps, scorecards, 2x2s, benchmark tables, and more, with role packs
for sales, PMO, HR, engineering, and research.

One command, zero dependencies:
python3 scripts/render_slide_spec.py spec.json

It also generalized beyond board slides: reports, proposals, training
materials, technical diagrams, and infographics, with input triage that
maps any input — numbers, prose, processes — to the right pattern.

https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### X Version (EN)

```text
v1.8.0: the skill now RENDERS slides — and has packs for every role.

Messy notes -> consulting-style SVG slide, one command, zero deps.

- 12 rendered patterns (waterfall, funnel, gantt, heatmap...)
- 28 visualization patterns total
- works for reports, proposals, docs, infographics too
- input triage: feed it anything

https://github.com/kgraph57/mckinsey-style-visualization-skill
```

### X Version (JP)

```text
v1.8.0をリリース。実際にスライドを描画でき、職種別パックも揃いました。

雑なメモ → コンサル風SVGスライド。1コマンド、依存ライブラリゼロ。

- ウォーターフォール・ファネル・ガント等12パターンをレンダリング
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

Recent releases added a renderer — spec JSON to styled SVG slide,
Python stdlib only — input triage so it can visualize anything, and
role packs for sales, PMO, HR, engineering, and research.

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
I published Strategy Consulting Visualization Skill v1.8.0.

The skill helps AI agents turn raw input into executive-ready visuals.
New in recent releases: an SVG renderer (spec JSON to finished slide,
no dependencies), role-based packs with rendered examples for nine
business roles, Japanese document profiles, and generalization beyond
board slides to reports, proposals, training materials, and diagrams.

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
- 28 visualization patterns, 18 document-type profiles
- SVG renderer for 12 patterns (Python stdlib only)
- persona playbook for 9 business roles
- style system, prompt templates, quality rubric
- draft -> review -> revise examples and local validation

Repo:
https://github.com/kgraph57/mckinsey-style-visualization-skill
```

## Social Asset

Primary: `assets/readme/hero-before-after.svg` exported to PNG (messy notes -> rendered slide).
Secondary: `assets/social/launch-card.svg`.

Alt text: Strategy Consulting Visualization Skill turns raw notes into a rendered, board-ready SVG slide with one command, plus specs for reports, proposals, and infographics.

### X Thread (JP, 7 posts)

Post 1 is the hook with the hero image; the repo link goes in the last post only. Image files referenced below are the committed SVGs exported to PNG.

```text
1/ (画像: hero-before-after)
「雑なメモ → 役員会に出せるスライド」を1コマンドでやるClaude Skillを作りました。

AIにありがちな"それっぽいだけのグラフ"ではなく、コンサルの作法(結論ファーストの見出し・正直な軸・抑えた配色)で描画します。

何ができるか、ツリーで説明します🧵

2/ (画像: arr-waterfall)
仕組みはシンプル。
メモや数値を渡す → スキルが「問い → 見出し → パターン選択 → スペックJSON」まで設計 → 付属レンダラーがSVGスライドを描画。

Python標準ライブラリのみ、依存ゼロ。
python3 scripts/render_slide_spec.py spec.json

3/ (画像4枚: sales-pipeline-funnel, pmo-rollout-gantt, marketing-channel-heatmap, hr-talent-scorecard)
職種別パックがあります。

営業:パイプラインのファネル
PMO:クリティカルパス入りガント
マーケ:チャネル×セグメントのヒートマップ
人事:タレントスコアカード

すべてコピペ用プロンプト付き。

4/ (画像4枚: product-priority-two-by-two, eng-incident-flow, research-outcomes-before-after, executive-summary)
さらに:

PdM:工数×インパクトの2x2
エンジニア:障害ポストモーテムのフロー
研究・医療:過大主張しないアウトカム比較
経営者:取締役会向けサマリー

レンダリング12パターン、設計レベルでは28パターン。

5/
入力は何でもOKです。
数値データ、議事録、プロセスの説明、ただの文章 — 「入力トリアージ」が入力の種類を最適なパターンに対応付けます。

稟議書・週報・学会抄録・提案書など、日本のビジネス文書プロファイルも入っています。

6/
こだわりは"正直さ"です。

・数値を捏造しない(足りないデータは明示)
・軸を誇張しない
・出典と仮定を必ず書く

見た目より先に、意思決定に使える資料であること。

7/
オープンソース(MIT)です。インストールは1行:

git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git ~/.claude/skills/strategy-consulting-visualization

リポジトリはこちら。スターしてもらえると励みになります⭐
https://github.com/kgraph57/mckinsey-style-visualization-skill
```

## Persona Content Calendar

Nine weekly posts, one role each. Format: role-targeted hook + the rendered example image + repo link. Post JP and EN versions; the rendered SVGs convert to PNG with any SVG tool.

| Week | Role | Hook (JP) | Asset |
| --- | --- | --- | --- |
| 1 | 営業 | CRMのエクスポートを貼るだけでQBRのファネルができます | `assets/rendered/sales-pipeline-funnel.svg` |
| 2 | PM/PMO | クリティカルパス入りのロードマップ、ガント図を手で描くのは今日で終わり | `assets/rendered/pmo-rollout-gantt.svg` |
| 3 | マーケター | チャネル×セグメントのヒートマップで予算再配分の議論が5分で終わる | `assets/rendered/marketing-channel-heatmap.svg` |
| 4 | 人事 | 経営会議に出すタレントスコアカード、メトリクスを箇条書きで渡すだけ | `assets/rendered/hr-talent-scorecard.svg` |
| 5 | PdM | 機能の優先順位、工数×インパクトの2x2に自動でマッピング | `assets/rendered/product-priority-two-by-two.svg` |
| 6 | エンジニア | ポストモーテムのタイムライン、ボトルネックを強調したフロー図に | `assets/rendered/eng-incident-flow.svg` |
| 7 | 研究職・医療職 | 抄読会のアウトカム比較、過大な主張をしないビフォーアフターに | `assets/rendered/research-outcomes-before-after.svg` |
| 8 | 財務 | 予実差異のウォーターフォール、数字が必ず合う形で | `assets/rendered/arr-waterfall.svg` |
| 9 | 経営者 | 取締役会の3つのメッセージ、サマリーストリップ1枚に | `assets/rendered/executive-summary.svg` |

Each post doubles as a Zenn/Qiita article seed: expand the hook into a 5-minute walkthrough (input -> spec -> rendered slide).

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
