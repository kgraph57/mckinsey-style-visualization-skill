# Quick Start

Get started with Strategy Consulting Visualization Skill in five minutes.

## Install

### Recommended

```bash
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git ~/.claude/skills/strategy-consulting-visualization
```

### Direct Download

```bash
mkdir -p ~/.claude/skills/strategy-consulting-visualization
curl -o ~/.claude/skills/strategy-consulting-visualization/SKILL.md https://raw.githubusercontent.com/kgraph57/mckinsey-style-visualization-skill/main/SKILL.md
```

## Validate the Package

From a cloned copy of the repository:

```bash
python3 -m unittest discover -s tests
python3 scripts/validate_skill.py
```

Expected:

```text
OK: skill package passed validation
```

## Fastest Path to a Complete Deck

Skip writing specs from scratch — scaffold a ready-made archetype and fill in real data:

```bash
python3 scripts/scaffold_deck.py --list
python3 scripts/scaffold_deck.py board-update -o my-deck
# edit my-deck/specs/*.json with real data
python3 scripts/build_html_deck.py --manifest my-deck/deck.json -o my-deck/deck.html
```

Six archetypes ship: `board-update`, `strategy-recommendation`, `project-status`, `market-entry`, `sales-proposal`, and `board-update-ja` (Japanese). See the [README template gallery](README.md#template-gallery) for what each one contains.

## Fastest Path to a Report Document

For a document instead of a deck, write Markdown and build it straight to a self-contained, print-to-A4 HTML report:

```bash
python3 scripts/build_html_report.py my-report.md -o my-report.html --lang en
```

Start from a template in `templates/reports/` (`board-pre-read.md`, `one-pager.md`, `proposal-memo.md`), or see the committed [examples/demo-report.html](examples/demo-report.html).

## Fastest Path to a Speaker Script

Add a top-level `"notes"` field (a string, or a list of paragraphs) to any slide spec — the renderer ignores it — then build the same deck manifest into a print-first, one-slide-per-page podium script:

```bash
python3 scripts/build_speaker_script.py --manifest my-deck/deck.json -o my-deck/script.html --lang en
```

See the committed [examples/demo-script.html](examples/demo-script.html).

## Fastest Path to a Deck-as-an-Article Page

Same `notes` field, read top-to-bottom instead: every slide followed by its narration as prose, like an M3-series web article.

```bash
python3 scripts/build_html_article.py --manifest my-deck/deck.json -o my-deck/article.html --lang en
```

See the committed [examples/demo-article.html](examples/demo-article.html).

## First Prompt

```text
Use the strategy consulting visualization skill to create a waterfall slide spec showing ARR growth from $10M in Q1 to $15M in Q4, with +$3M from enterprise customers, +$2.5M from expansion, and -$0.5M from churn.
```

If the input is vague, use this safer prompt:

```text
Use the strategy consulting visualization skill. First identify the reader and decision, then choose the simplest useful visual. Challenge assumptions, avoid overclaiming, and include expert review notes.
Here is the raw material:
[paste notes, metrics, prose, or process]
```

## Common Requests

```text
Create a board-ready 2x2 market map positioning competitors by technical capability and enterprise adoption.
```

```text
Turn these operating metrics into a five-slide executive summary with data assumptions and a quality check.
```

```text
Create a competitive benchmarking table for five AI vendors across accuracy, cost, integration maturity, and risk.
```

## Next Steps

- Read [README.md](README.md) for the product overview.
- Review [EXAMPLES.md](EXAMPLES.md) for usage scenarios.
- Use [references/expert-review-loop.md](references/expert-review-loop.md) before publishing public or high-stakes visuals.
- Open [MARKETPLACE.md](MARKETPLACE.md) for listing copy.
- Inspect [references/quality-rubric.md](references/quality-rubric.md) before publishing proof assets.
