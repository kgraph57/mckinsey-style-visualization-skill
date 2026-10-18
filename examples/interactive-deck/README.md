# Project Relay

Project Relay is an original, synthetic eight-page executive decision deck.
It asks for a $0.6m cap and a North-first pilot. East remains conditional on the
Week 6 adoption/readiness review and the technician-constraint case. Network
expansion is a separate Week 12 decision. Pages 3–6 are interactive; the other pages are static.
Every analytical value and evidence surface is labelled `Illustrative`.

The content pages use direct evidence: proportional cause bars, paired route
scenarios, the full adoption/value line and hurdle, and readiness contributions.
The interactive companion places primary controls next to the exhibit on desktop,
with vertical reflow on narrow screens. Action titles need no redundant subtitle.

Build from the repository root:

```bash
python3 scripts/build_html_deck.py \
  --manifest examples/interactive-deck/deck.json \
  -o examples/interactive-deck/deck.html

python3 scripts/build_interactive_deck.py \
  --manifest examples/interactive-deck/deck.json \
  -o examples/interactive-deck/deck.interactive.html

python3 scripts/export_pdf.py \
  examples/interactive-deck/deck.interactive.html \
  -o examples/interactive-deck/deck.pdf

python3 scripts/audit_interactive_deck.py \
  --manifest examples/interactive-deck/deck.json \
  --audit-out test-results/interactive/project-relay-audit

python3 -m unittest tests.test_interactive_reference
python3 -m unittest discover -s tests/e2e -p 'test_interactive_reference.py'
python3 -m unittest discover -s tests/e2e -p 'test_interactive_visual_pdf.py'
```

`deck.html`, `deck.interactive.html`, and `deck.pdf` are the audience
artifacts. The audit atlas is author-only output under ignored
`test-results/`; it must never be copied into this example directory.

Presenter shortcuts in the interactive artifact: `Alt+O` overview, `Alt+R`
reset, `Alt+D` curated demo, `Alt+F` fullscreen, and `Alt+H` help.
