# Decision presentation: design record

Revision: 2026-10-18. Scope: the English Project Relay example.

The user requested a consulting-style refinement with an explainable design
identity. The working promise is that readers can inspect what changes a pilot
decision. The narrative stays conclusion-first: bounded pilot → delay cause →
regional priority → value gate → execution gate → conditional plan.

## Rules implemented in this revision

- White editorial canvas, dark ink and one blue for selected evidence, active
  controls and decision status. Group explanations through space and alignment;
  do not add panel rules, comparison-row rules or takeaway dividers.
- The assertion stays at the same upper baseline. Chart and interpretation
  share a stable grid. Body text is retained at presentation size.
- The right column has a repeated reading order: current decision status,
  quantity, interpretation, comparison arithmetic, evidence link.
- The headline reflects active assumptions. A failing model or readiness
  score cannot retain a successful headline. Overview captions use the same
  current headline as the page.
- Changing adoption preserves a labelled outline at the initial value. The
  reader can reset that input without changing other assumptions.
- The timeline shows how many of its three conditions currently pass. Meeting
  them is still conditional on the Week 6 review; network scale is a separate
  Week 12 decision.
- The overview uses a numbered reading path with open space and no dividers.
  Mobile displays the same argument in vertical reading order.
- Lines are reserved for chart scales, thresholds, comparisons and control state.
  The evidence link uses blue text and an arrow, without a permanent underline.

## Provenance and claims

The earlier motion-deck work was informed by the user's supplied public
article by Uchita about interactive presentations; see `motion-story.md` for
the reference and the existing provenance statement. That history is retained.
This revision adds the editorial rules and state-dependent treatment above
to the repository's existing implementation. It does not import reference
templates, images or purchased source code.

White backgrounds, blue accents, assertion headlines, sliders, evidence drawers
and comparison markers are general design techniques. Their presence is not
claimed as an invention. The defensible description is an independently
implemented combination for inspecting decision thresholds, not a claim of
world-first novelty or exclusive ownership of these techniques. No official
McKinsey affiliation is represented.

## Build

Set `design` to `decision` in an English motion manifest. The builder includes
`runtime/motion-decision.css` and `runtime/motion-decision.js`; the shared
navigation, calculation and evidence state remain the source of truth.
The English example uses illustrative values throughout. This presentation
layer is currently tailored to the Project Relay story, not a general-purpose
decision engine for arbitrary business datasets.

## Fresh-eyes review disposition

Reviewed all six desktop and mobile captures plus the generated artifact.

| Page | Finding | Disposition |
| --- | --- | --- |
| 4 | Gap arithmetic labels the annual flow as $m | Accepted: label changed to $m/year |
| 4 | One decimal might round 1% slider steps | Retracted after inspection: the slider steps by 5%, producing exact 0.3m increments |
| Mobile | Fixed controls overlap content in a full-page screenshot | Expected viewport overlay while scrolling; content has bottom clearance and remains reachable |

No other confirmed high- or medium-severity finding was returned. Browser
checks separately exercise the changed states, reset, conditional timeline,
evidence drawers, overview, static companion and demo cancellation.

Final verification on 2026-10-18: 27 builder, English/Japanese browser and site
tests passed. All six English pages were captured at 1440, 1280 and 390 pixels.
The served localhost deck also completed the normal-speed demo, ending at
Week 12 with the six-page overview open. Package validation, site freshness
and whitespace checks passed. No publication or push was performed.
