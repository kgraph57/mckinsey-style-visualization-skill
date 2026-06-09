# Traction Tracker

Use this file to track demand signals that matter for marketplace listings, premium-pack validation, and eventual acquisition conversations.

Growth target: 1,000 GitHub stars. The operating plan is in `GROWTH.md`; this file logs the results.

## Baseline

Baseline date: 2026-06-09

| Signal | Baseline | Source |
| --- | ---: | --- |
| GitHub stars | 29 | GitHub repository page |
| GitHub forks | 10 | GitHub repository page |
| GitHub watchers | 2 | GitHub repository page |
| Marketplace listings | 0 | `MARKETPLACE_TARGETS.md` |
| Marketplace installs/saves | 0 | Marketplace dashboards |
| Social launch posts | 2 | `LAUNCH.md` |
| Direct user replies | 0 | Social, issues, discussions |
| Example requests | 0 | GitHub Issues |
| Buyer inquiries | 0 | GitHub Issues, email, direct messages |
| Paid customers | 0 | Payment provider or invoice log |

Baseline captured with GitHub repository metadata on 2026-06-09.

## Weekly Log

| Week Starting | Stars | Forks | Watchers | Listings | Installs/Saves | Social Replies | Example Requests | Buyer Inquiries | Paid Customers | Notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2026-06-09 | 29 | 10 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | English and Japanese X launch posts published |

## Launch Posts

| Date | Channel | URL | Notes |
| --- | --- | --- | --- |
| 2026-06-09 | X | https://x.com/kgraph_/status/2064211558461567218 | v1.5.0 launch post |
| 2026-06-09 | X | https://x.com/kgraph_/status/2064213710495993900 | v1.5.0 Japanese launch post |

## Qualified Signals

Not all attention has equal value. Count these as high-intent signals:

- A user asks for a PPTX, PDF, HTML, or image-rendered version.
- A user requests a scenario-specific pack, such as SaaS board update or investment memo.
- A marketplace operator asks for submission, curation, or paid listing details.
- A team asks whether the skill can be adapted to internal reporting workflows.
- A buyer asks about ownership, license, roadmap, or revenue potential.

## Decision Gates

| Gate | Threshold | Action |
| --- | --- | --- |
| Distribution signal | Listed in 5+ directories | Create a public case-study thread |
| Usage signal | 100+ stars, installs, or saves | Build premium template pack |
| Commercial signal | 3+ PPTX/PDF/rendered example requests | Prototype renderer workflow |
| Buyer signal | 2+ serious acquisition or partnership inquiries | Prepare data room |
| Revenue signal | 10 paid customers | Add commercial license and support terms |

## Data Room Checklist

Prepare these files when acquisition interest appears:

- `BUYER_BRIEF.md`
- `TRACTION.md`
- `COMMERCIALIZATION.md`
- `MARKETPLACE_TARGETS.md`
- `CHANGELOG.md`
- Export of GitHub stars/forks/issues
- Marketplace listing screenshots or URLs
- Social post analytics screenshots
- Revenue export, if paid products exist

## Weekly Review Prompt

```text
Review TRACTION.md and current GitHub/marketplace/social metrics.
Update the weekly log.
Identify the strongest demand signal.
Recommend the next release or commercial experiment.
```
