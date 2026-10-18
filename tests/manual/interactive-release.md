# Interactive deck release evidence

This record separates reproducible automated evidence from checks that require
a person, a physical device, assistive technology, or the eventual hosting
boundary. An unchecked row is not a release claim.

## Automated evidence

Prerelease preparation, 2026-10-18: the final core suite passed 664 tests
(`python3 -m unittest discover -s tests`, 229.995 s). Package validation, site
freshness, landing-render freshness and whitespace checks passed. The motion
edition's 27 builder/browser/site checks and 18 English page/viewport captures
are recorded separately in `references/decision-design.md`.

Initial Linux comparison fixtures were seeded with explicit opt-in using
`mcr.microsoft.com/playwright/python:v1.58.0-noble` (linux/amd64), Playwright
1.58.0 and the test's pinned Chromium version. The 13-image baseline-generation
test passed (362.590 s). This establishes reproducible fixtures, not human
acceptance or physical-device verification. Human baseline sign-off is still
open for stable v3; see `examples/interactive-deck/review.md`.

| Evidence | Command | Result | Notes |
| --- | --- | --- | --- |
| Project Relay source and artifact contract | `python3 -m unittest tests.test_interactive_reference` | Pass (11/11) | Fresh local run on 2026-10-17. |
| Chromium and Firefox functional acceptance | `python3 -m unittest discover -s tests/e2e -p 'test_interactive_reference.py'` | Pass (9/9) | Browser emulation is not physical-device evidence. Fresh local run on 2026-10-17. |
| Chromium visual and PDF acceptance | `python3 -m unittest discover -s tests/e2e -p 'test_interactive_visual_pdf.py'` | Pass (5/5; Linux baseline update skipped) | Fresh macOS run on 2026-10-17; macOS creates review candidates only and never updates Linux baselines. |
| Project Relay author audit | `python3 scripts/audit_interactive_deck.py --manifest examples/interactive-deck/deck.json --audit-out test-results/interactive/project-relay-audit` | Pass (62 screenshots; two-run byte match) | Fresh reproducibility test on 2026-10-17. Output stays under ignored `test-results/`. |

Visual comparisons use the deterministic thresholds declared in
`tests/e2e/test_interactive_visual_pdf.py`. Reviewed Linux screenshots live
only in `tests/e2e/baselines/chromium-linux/`. Updating those files requires an
explicit opt-in on the pinned Linux/Chromium environment and a recorded human
disposition in `examples/interactive-deck/review.md`.

## Manual-only release gates

The following checks are intentionally not satisfied by Playwright, responsive
desktop mode, a simulator, or a meta CSP. Record the named operator and actual
environment after the run. Until then, leave the checkbox empty and the result
as `Not run`.

| Done | Environment / device | OS / browser | Connection / display | Operator | Date | Result | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [ ] | Linux comparison fixtures | Pinned Chromium | 13 generated comparison images | — | — | Not run | Human baseline sign-off for stable v3; automated seed creation is not acceptance. |
| [ ] | Mac with Safari 17+; local file | macOS / Safari 17+ | Local file | — | — | Not run | Confirm boot, navigation, interaction, evidence, presenter controls, and print. |
| [ ] | Mac with Safari 17+; loopback HTTP | macOS / Safari 17+ | Local HTTP | — | — | Not run | Confirm the same flow over HTTP. |
| [ ] | Physical iPhone; portrait | iOS 17+ / Safari | Handheld touch | — | — | Not run | Confirm readable compact view and complete operation without rotation. |
| [ ] | Physical iPhone; landscape | iOS 17+ / Safari | Handheld touch | — | — | Not run | Confirm no clipped required content. |
| [ ] | Physical touch and swipe | iOS 17+ / Safari | Touch, swipe, vertical scroll | — | — | Not run | Confirm gestures do not cause accidental page or control changes. |
| [ ] | Physical device with browser toolbar at 200% | Real browser / real OS | Browser zoom 200% | — | — | Not run | Desktop emulation and device scale factor do not satisfy this row. |
| [ ] | Presentation over AirPlay | Presenter device / receiving display | AirPlay | — | — | Not run | Confirm stage legibility, input response, and fullscreen fallback. |
| [ ] | Presentation over HDMI or projector | Presenter device / external display | HDMI / projector | — | — | Not run | Confirm 16:9 fit, contrast, and presenter operation. |
| [ ] | VoiceOver with Safari | macOS / Safari | VoiceOver | — | — | Not run | Confirm reading order, labels, evidence focus trap, status announcements, and return focus. |
| [ ] | NVDA with Firefox or Chrome | Windows / Firefox or Chrome | NVDA | — | — | Not run | Confirm reading order, controls, state, and announcements. |
| [ ] | Real high-contrast mode | Supported OS / browser | OS high contrast | — | — | Not run | Confirm visible focus and usable evidence controls. |
| [ ] | Hosted deployment | Eventual production browser | HTTP response headers | — | — | Not run | Verify server-delivered `frame-ancestors`; a meta CSP does not satisfy this row. |

## Recording rules

- Allowed results are `Pass`, `Fail`, `Blocked`, and `Not run`.
- A failed or blocked row keeps its checkbox empty.
- Do not infer a physical-device result from an automated viewport.
- Record defects and any adopted response in
  `examples/interactive-deck/review.md` before release.
