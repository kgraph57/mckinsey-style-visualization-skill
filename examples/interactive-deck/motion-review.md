# Motion story: whole-deck rebuild, 17 October 2026

The user rejected the earlier interaction experience. The reference for this
round is the user-supplied public article about click-through presentations,
not merely the appearance of a consulting slide. The resulting original
six-page Japanese presentation is `deck.motion.html`, authored from
`motion.json`; `deck.motion.static.html` is its reading/print-mode companion.
The earlier eight-page contract-backed example is retained separately.

## What the reader can do

| Page | Claim and operation |
| --- | --- |
| 1 | Read the bounded pilot recommendation and enter its supporting decisions from the overview cards. |
| 2 | Press a real cause bar or the main number; inspect the cause split and its source/assumptions in the right drawer. |
| 3 | Switch the staffing condition; rows sort by their real values while baseline extents and exact differences remain. |
| 4 | Move adoption; the point, annual value, equation and threshold margin update together. |
| 5 | Turn manager capacity or integration off; the contributions, score and remaining shortage update on the same scale. |
| 6 | Advance the timeline through W1/W6/W7/W12. Conditional East work and its principal explanation follow the live upstream conditions. |

O opens the whole-deck overview. D runs the visible cursor demonstration and
finishes in that overview. A real pointer action or D stops an active demo,
including while an evidence dialog is open. Native dialog controls provide
focus containment, Escape and return to the original trigger.

## Fresh-eye review and dispositions

The independent reviewer received the artifact and actual screenshots, without
the intended conclusions or prior acceptance claims.

| Finding | Disposition and correction |
| --- | --- |
| W7's main panel said to add East even when conditions failed. | Adopted. Conditional steps now declare explicit hold labels and explanations; both the main panel and mobile sequence show the hold state. A new regression check first failed, then passed. |
| The page-2 overview preview was blank. | Adopted. The card-entry transform origin had survived cloning; resetting that origin to zero fixes the preview. A geometric heading-in-preview check first failed, then passed. |
| The phone timeline hid W6/W7 beyond a horizontal crop. | Adopted. The phone layout is a vertical sequence showing all four decision times. |
| The 72-point headline omitted its dependency on integration. | Adopted. The headline now names both manager capacity and integration. |
| An overview card ended with an orphan character. | Adopted. The description was shortened without changing its meaning. |

The reviewer re-read the updated code and images and closed the four substantive
findings. This is independent code/image review, not an independent physical
device test or a claim of exact fidelity to a named designer.

## Verification evidence

- The browser suite checks every page at 1440×900 and 1280×720; phone layout at
  390×844; card entry; directly operated evidence; native focus return; ranking;
  model and readiness propagation into the plan; static deep links; the full
  scripted sequence and cancellation. Final screenshots are under
  `output/playwright/motion-final/`.
- A cancellation test initially awaited the async demo to completion. It was
  corrected to start the demo without awaiting it, so cancellation is actually
  exercised during playback. This exposed the D-key modal guard, which was
  fixed and verified with a failing-then-passing regression.
- The normal-speed demo was also run through D in a real served browser and
  ended with all six previews visible. Its console had no errors or warnings.
  See `output/playwright/motion-full-speed-final.png`.
- Four builder checks cover invalid input domains, missing condition references,
  HTML/JSON escaping and generated-file freshness. The related site/package
  suite passed 24 checks, including those four builder checks.
- Skill validation, generated-site freshness, Python/JavaScript syntax and
  whitespace checks passed. The generated files are self-contained and make
  no automatic external requests.

Values remain the original illustrative Project Relay data. The annual model
uses ten-thousand US dollars: −150 + 6 × adoption; 55% gives 180, equivalent to
$1.8m/year. Readiness is 24 + 20 + 18 + 10 = 72; removing manager capacity gives
54, leaving 16 points to the 70-point gate. All pages disclose the illustrative
basis and provide their source and assumptions.

Only independently authored code and assets are distributed. No purchased
engine, source file or reference image is included in the presentation. No
commit, push, PR, publication or deployment was performed. Physical devices and
projector/assistive-technology checks were outside this local revision.
