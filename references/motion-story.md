# Story-led motion presentations

Use this route when the requested experience is a presentation that answers
follow-up questions in place: enter from an overview, click the exhibit, inspect
the evidence, change a condition and continue the argument. The original
Japanese Project Relay example is `examples/interactive-deck/motion.json`.
It uses the existing example's illustrative values, not a new business dataset.

The experience principles were informed by the user's supplied public article,
[うちた: クリックで深掘りできる資料](https://note.com/uchita_success/n/nf8711b1dba37).
The renderer, styles, runtime and example are independently authored. No
purchased engine, sample code, image or template is distributed here.

## Author and build

Create a JSON object with `title`, `lang`, `disclosure` and `pages`. Keep the
argument short enough that the reader can enter at the top and inspect the
supporting decisions. The example uses six pages to show the supported
operations; do not add pages simply to exhibit every feature.

```bash
python3 scripts/build_motion_deck.py --manifest motion.json -o deck.motion.html
python3 scripts/build_motion_deck.py --manifest motion.json --static -o deck.motion.static.html
```

Both files are self-contained. The latter shows every page in its conclusion
state and can be printed from the browser. Neither file needs a network request.
Set `lang` to `ja` or `en`. The English example is `motion.en.json` beside the
Japanese manifest. Author narrative, evidence and source text in that language.
The English build localizes the shared UI and runtime through a strict catalog
in `scripts/motion_locale.py`; unknown Japanese UI text fails the build.
English money labels use $m/year, while the calculation and conditional gates
retain exact integer units of $10,000. Keep model quantities in those units.
The English example also enables the `decision` presentation. Its visual rules,
state-dependent headlines and provenance are recorded in [decision-design.md](decision-design.md).

Each page has a stable `id`, `kind`, `section`, complete assertion `title`,
chart `scope`, `source`, and `evidence`. Evidence includes `head`, `headers`,
`rows`, and `assumptions`. Text is plain, not executable HTML. Every analytic
page also has a `panel` containing one large `value`, its `unit`, a one-line
`label`, concise `text`, and two `comparison` rows. State-dependent fields are
derived from the active data, rather than maintained as separate copies.

## Components

| `kind` | Author data | Main operation |
| --- | --- | --- |
| `overview` | `kpis` and `flow` entries with a destination `page` | Enter the corresponding evidence page from a visible card |
| `evidence` | `items` with `id`, `label`, `value`, optional `focus`; zero-based `domain` | Press a real bar or the prominent number to inspect the supporting evidence |
| `ranking` | Two `scenarios`, including `base`; stable `items` containing both scores; `initial` | Switch the condition; stable rows change rank, while the base extent and exact difference remain visible |
| `model` | `input` min/max/step/initial; linear `model` intercept/coefficient/threshold/domain | Change the input; point, number, formula and decision margin recalculate together |
| `gap` | Additive `components`, optional `toggle`/`initial`, `threshold`, `domain` | Turn a declared contribution off or on; show the remaining shortage on the same scale |
| `sequence` | Ordered `steps` with week/label/detail and bounded `tasks` | Advance the current time and expose each decision in order |

A sequence may declare `conditions` pointing at another page's model value,
readiness score, or selected scenario. For example:

```json
{"page":"readiness","threshold":70,"label":"準備度70点以上"}
```

Conditional tasks fill only when all declared conditions pass. Changing the
upstream condition must change the downstream plan; do not show a success
timeline after the reader has selected failing assumptions.

## Presentation behavior

- The desktop composition uses a 1920×1080 canvas: assertion at the fixed upper
  baseline, exhibit on the left, interpretation and one large number on the
  right, near-claim comparison arithmetic, sources at the bottom.
- Keep the panel copy to two short lines when possible. Remove duplicate
  instructions and fit the argument before reducing type. The phone view
  reflows into a reading order instead of shrinking the canvas.
- Both real chart marks and the prominent number open the evidence drawer.
  Its two tabs separate the breakdown from the source and assumptions.
  Native dialog behavior supplies focus containment, Esc and focus return.
- `O` opens the whole-deck overview, `D` runs or stops a visible cursor demo,
  arrows/Space move between pages, and numbers select a page. Input controls
  retain their native keys. Clicking during the demo cancels it.
- `#p3` selects a page. `#p3.static` reveals its conclusion immediately.
  The static export shows all final pages. Reduced motion removes movement.
- The demo follows the same buttons and inputs as the reader and ends in the
  overview. A missing target is an error, not a silently skipped operation.

## Review the whole artifact

Open every page at presentation size and inspect the final static states,
source drawer, switched ranking, low-input model, missing contribution and
conditional timeline. Check the card-to-page path and native focus return.
Play the full-speed demo, including its ending; accelerated tests only verify
the sequence and cancellation. Use `tests/e2e/test_motion_story.py` for the
maintained example's real browser checks. Do not claim reference-level fidelity
from passing checks or a colour preset alone.
