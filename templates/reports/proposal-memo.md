---
title: Vendor recommendation memo
subtitle: Consolidating the workflow tooling evaluation
author: Platform team
date: March 2026
classification: Internal — illustrative
lang: en
---

## Situation

The team evaluated three vendors against the criteria set in January's RFP. This memo recommends one of them and lays out the initiatives that should follow regardless of which vendor is chosen.

## The comparison

Vendor B is the only option that clears both the cost and integration bars; Vendor A wins on price alone, and Vendor C wins on security alone.

![Vendor scoring against RFP criteria](spec:specs/benchmark-table.json)

## What we recommend doing next

Two initiatives justify starting immediately, independent of the vendor decision; a larger platform rewrite should wait for the Q3 roadmap review.

![Initiative prioritization](spec:specs/two-by-two.json)

## Why this order

1. Self-serve onboarding and usage-based pricing both ship inside the current quarter with existing headcount.
2. The platform rewrite requires the vendor decision to be final first, since the two integration paths are not compatible.
3. Sequencing this way means no initiative blocks another.

> "Whichever vendor we pick, the two initiatives above pay for themselves before the contract renews." — Platform lead, illustrative planning note

For the full scoring methodology and interview notes, see the [appendix request form](mailto:platform-team@example.com).
