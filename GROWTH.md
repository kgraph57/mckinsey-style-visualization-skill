# Growth Playbook: Road to 1,000 Stars

Goal: grow from 32 stars (2026-06-09) to 1,000 stars. This file is the operating plan; log results in `TRACTION.md`.

## Star Math

Visitor-to-star conversion for a polished tool repo is roughly 5-10%. Reaching 1,000 stars needs on the order of 10,000-20,000 unique repo visitors. Drip traffic from directories will not get there alone; the plan needs 2-4 front-page moments plus a steady content engine.

| Channel Type | Realistic Yield per Event | Examples |
| --- | ---: | --- |
| Hacker News front page (Show HN) | 200-500 stars | One strong launch |
| Reddit top post (r/ClaudeAI, r/ChatGPTCoding) | 50-200 stars | Per successful post |
| Viral X thread with visuals (JP or EN) | 50-300 stars | Repeatable with new examples |
| Zenn / Qiita trending article (JP) | 50-150 stars | Repeatable per release |
| Awesome-list inclusion | 1-5 stars/day drip | Compounding, permanent |
| Skill directories / marketplaces | 1-3 stars/day drip | Compounding, permanent |
| Product Hunt launch | 50-150 stars | One-shot |

## The Core Conversion Problem

People star repos that **show** results, not repos that describe specs. The current README sells "visualization specs" with hand-made preview SVGs. The single highest-leverage change is closing the loop:

> messy notes in → actual rendered slide out, in one screenshot.

Priority order of product work that drives stars:

1. **Renderer**: a script that turns a slide spec into a rendered SVG/HTML slide (`scripts/render_slide_spec.py` or HTML template). This converts the repo from "prompt pack" to "tool". Tools get starred; prompt packs get bookmarked.
2. **Hero demo**: one before/after image or GIF at the top of the README — raw notes on the left, board-ready slide on the right. This is also the shareable asset for every social post.
3. **30-second quickstart**: one copy-paste command + one prompt + one visible result. Reduce time-to-wow below a minute.
4. **Bilingual README**: `README.ja.md` for the Japanese audience, where the author already has distribution.

## Milestone Ladder

### Phase 1: 32 → 100 (Weeks 1-2) — Drip Infrastructure

- Submit to all P0/P1/P2 targets in `MARKETPLACE_TARGETS.md` and log listings.
- PR the repo into awesome lists: awesome-claude-code, awesome-claude-skills, awesome-ai-agents, awesome-chatgpt (skill-compatible sections). Follow each list's contribution rules; one-line factual descriptions.
- Publish one Zenn article (JP): "Claude Codeにスキルを入れて、メモから役員会資料のスペックを作る" — walkthrough with real input/output, link at top and bottom.
- Add `README.ja.md` and the hero before/after image.
- Post the v1.6.0 universal-visualization release on X (JP+EN) with a visual, not a text wall.

### Phase 2: 100 → 300 (Weeks 3-6) — First Front-Page Moment

- Ship the renderer (even minimal: spec → styled SVG for 3-4 patterns).
- Launch Show HN: "Show HN: An agent skill that turns messy notes into consulting-style slides". Post 8-10am ET Tue-Thu. Lead with the rendered output image. First comment: honest scope, what it does NOT do.
- Reddit r/ClaudeAI and r/ChatGPTCoding: tutorial-style post ("I built a skill that...") with the before/after image, not a bare link.
- Answer every comment within hours; ship fixes from feedback same week and reply with the commit.

### Phase 3: 300 → 600 (Months 2-3) — Repeatable Content Engine

- Weekly "one visual" X post: take a public dataset or common business scenario, show input → rendered output. Each post is a mini-demo, JP and EN.
- Monthly Zenn/Qiita article per release or use case (proposal docs, study notes, technical diagrams — the universal patterns are the content calendar).
- Product Hunt launch once the renderer demo is solid.
- Encourage shares: add a "share your output" discussion or issue template; feature community outputs in the README gallery with credit.

### Phase 4: 600 → 1,000 (Months 3-6) — Ecosystem Compounding

- Integrations: example workflows for Claude Code, Cursor, and plugin marketplaces; submit to the Anthropic skills ecosystem and community plugin marketplaces as they open.
- Template packs as new releases (SaaS board pack, research report pack, lecture notes pack) — each release is a launch event.
- Talk/video content: a 3-minute demo video or conference lightning talk reused across channels.
- Localized launches: repeat the Show HN formula on JP channels (Zenn trending, hatena bookmark) and LinkedIn for the consulting audience.

## Weekly Operating Cadence

1. Monday: update `TRACTION.md` weekly log (stars, forks, listings, replies).
2. Ship one visible improvement (example, pattern, render quality) — repos with fresh commits convert better.
3. Publish one piece of content with a visual (X post minimum; article on release weeks).
4. Respond to all issues/comments within 24-48 hours.
5. Log what worked; double down on the single best channel, drop the worst.

## Conversion Checklist (Repo Side)

- [x] Hero before/after image above the fold in README
- [x] 30-second quickstart with copy-paste install + prompt
- [x] `README.ja.md`
- [x] Renderer script with sample output committed (`scripts/render_slide_spec.py`, 12 patterns)
- [x] GitHub Discussions enabled for community outputs
- [ ] Social preview image set in repo settings (use `assets/social/launch-card.svg` exported to PNG)
- [ ] Star history chart in README once growth starts (star-history.com)
- [ ] Pinned repo on the author profile

## What Not to Do

- No star-for-star exchanges, paid stars, or bot engagement — GitHub removes fake stars and the credibility damage is permanent.
- No reposting identical copy across channels; each channel gets native framing.
- No daily posting without new substance; one strong visual beats five text posts.
- No engagement-bait replies to big accounts; ship examples instead.

## Measurement

Track in `TRACTION.md`:

- Stars/week and which event drove each spike (annotate the weekly log).
- Referrer traffic via GitHub Insights → Traffic after each launch.
- Conversion proxy: stars gained ÷ unique visitors that week.

Review monthly: if a phase stalls for 3+ weeks, the bottleneck is almost always conversion (repo not impressive enough at first glance), not distribution. Fix the demo before adding channels.
