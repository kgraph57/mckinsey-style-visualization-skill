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
