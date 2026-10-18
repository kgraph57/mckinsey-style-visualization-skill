# Project Relay storyboard

All content and values are original and illustrative. This is a presentation,
not a dashboard or an analytical pre-read. Approve a bounded North pilot today;
use adoption, readiness and the staffing scenario at Week 6 to decide on East;
review network scale separately at Week 12.

| Page | Assertion | Evidence | Main interaction | May change | Must not change |
| ---: | --- | --- | --- | --- | --- |
| 1 | Project Relay | A 12-week dispatch pilot: North first, East conditional | None | Nothing | Bounded scope and illustrative label |
| 2 | Approve a $0.6m cap; start with North | Three decision moments: total cap including conditional East today, East at W6, scale review at W12 | None | Nothing | Cap, duration and separate decisions |
| 3 | Dispatch causes 61% of delays; fix it first | Proportional bars: 61% dispatch, 24% technicians, 15% handoff; 1,200 synthetic jobs over 12 weeks | Evidence overlay | Method disclosure | Values, fixed 0–100 scale, sample and source |
| 4 | North leads; staffing sets the second route | Paired rank columns with identity-preserving connections; scores are explicit labels, not encoded by line slope. Left baseline stays fixed | Scenario toggle | Right-side scores, ranks and comparison annotation | Left baseline, route identities, score domain, units and assumptions |
| 5 | 55% adoption clears the $1.8m hurdle | Full model line y = −1.5 + 0.06x, hurdle and 55% crossing | Adoption slider | Point, value and gate status | Formula, axes, hurdle; cap approval is not this gate |
| 6 | Manager capacity keeps readiness above 70 | Contributions 24 + 20 + 18 + 10 = 72; without the 18-point manager contribution: 54 against a 70-point gate | Four-input score | Contributions, total, class, gate status | Scoring method, bands, fixed scale and threshold |
| 7 | The Week 6 review decides whether East starts | North from W1; combined review ends W6; optional East from W7; scale review W12 | None | Nothing | East after the gate; staffing constraint also required; scale is separate |
| 8 | Approve the cap; gate East at Week 6 | $0.6m decision and named owners at W1, W6 and W12 | None | Nothing | Same cap, gates, sequence and conditional East scope |

## Visual and interaction contract

- One assertion and one main exhibit per content page. No automatic subtitle.
- Body 26px, labels 22px on a 1280 × 720 canvas. Cut or split content before reducing type.
- Numerical comparisons use length or position, not equal-width cards with numbers.
- At 1280 × 720 and 1440 × 900, the chart, primary controls and decision fit together. This is not a slide followed by a form.
- At narrow widths or zoom, content reflows vertically; keyboard and evidence access remain available.
- `model_context` is validated against the executable scene. It cannot introduce an unrelated slope, score contribution or scenario.
- Sources, model details and extended explanations belong in evidence, not a second headline or duplicate table.
