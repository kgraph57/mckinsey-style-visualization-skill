---
title: Illustrative growth review
subtitle: A single-file demonstration of every element the report builder supports
author: Strategy Office
date: March 2026
classification: Illustrative — sample data
lang: en
---

## Executive summary

Adoption **more than tripled** over four quarters, and the driver is a shift toward self-serve signups rather than paid acquisition. Cross-checking against raw usage events (`GET /v1/usage` request volume) confirms the same pattern independently, so this is *not* an artifact of how signups happen to be counted.

### What changed this quarter

Nothing structural changed in the product; the shift shows up entirely in the acquisition mix, which is why the recommendation below is about channel investment, not the roadmap.

## Where adoption stands

The adoption curve has not flattened yet.

![Adoption rate by quarter](spec:render-specs/adoption-trend.json)

Delivery capacity, not demand, is now the binding constraint on the next four quarters.

## How we compare to alternatives

Vendor B leads on the two criteria buyers weight most heavily, which is consistent with what the win/loss interviews describe.

![Vendor scoring on integration, support, and cost](svg:../assets/rendered/vendor-benchmark.svg)

## What the team recommends

- **Hold acquisition spend flat** and reallocate the freed budget to onboarding capacity.
  - This is a reallocation, not a net-new budget ask.
- Ship the two integrations already in the backlog before adding new ones.
- Re-run this scorecard next quarter using the same four metrics, no substitutions.

1. Confirm the onboarding headcount plan with the platform team this week.
2. Freeze new integration requests until the backlog above ships.
3. Revisit paid acquisition once delivery capacity catches up.

> "The self-serve motion carried more than half of new logos this quarter for the first time." — Head of growth, illustrative interview note

---

## Assumptions and caveats

| Assumption | Basis | Risk if wrong |
| --- | --- | --- |
| Self-serve mix holds | Trailing two quarters | Medium |
| No pricing change this quarter | Roadmap review, February | Low |
| Support headcount stays flat | Current staffing plan | High |

### A note on how this document is built

This paragraph exists to prove the escaping works: a line like <script>alert(1)</script> renders as inert text, never as a tag, because every line is HTML-escaped before any markdown syntax is recognized. For questions about the underlying data, contact the [strategy office](mailto:strategy@example.com).
