# Installation Guide

This guide installs Strategy Consulting Visualization Skill for agent tools that support the `SKILL.md` convention.

## Prerequisites

- An agent tool that can load local skills.
- Git for clone-based installation, or a browser and ZIP extractor.
- Python 3 to run the bundled renderer, builders, and package validator.

## Personal Installation

Use this when you want the skill available across projects.

```bash
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git ~/.claude/skills/strategy-consulting-visualization
```

## Project Installation

Use this when the skill should live inside one repository.

```bash
mkdir -p .claude/skills
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git .claude/skills/strategy-consulting-visualization
```

## Download Without Git

1. Open the [repository](https://github.com/kgraph57/mckinsey-style-visualization-skill)
   and choose **Code → Download ZIP**.
2. Extract the archive and rename the extracted folder to
   `strategy-consulting-visualization`.
3. Place the complete folder in your agent's skill directory (for Claude Code,
   `~/.claude/skills/`). Keep `SKILL.md`, `references/`, `scripts/`, `templates/`,
   and the other package files together.

Do not download only `SKILL.md`: it calls scripts and references files from the
rest of the package. A single-file download cannot render the examples or
scaffold a deck.

## Verify

After either installation method:

```bash
cd ~/.claude/skills/strategy-consulting-visualization
python3 scripts/validate_skill.py
```

Expected:

```text
OK: skill package passed validation
```

## Update

For a Git clone:

```bash
cd ~/.claude/skills/strategy-consulting-visualization
git pull
python3 scripts/validate_skill.py
```

For a ZIP installation, download and extract the latest archive into a new
folder, validate it, then replace the installed skill folder. Keep any decks
or reports you created separately so an update does not overwrite your work.

## Troubleshooting

### Skill Does Not Appear

1. Confirm the folder contains `SKILL.md`.
2. Confirm the skill folder path matches your agent tool's expected skill directory.
3. Restart the agent tool so it reloads skill metadata.
4. Check that `SKILL.md` starts with YAML frontmatter.

### References Are Missing

If only `SKILL.md` was downloaded, clone the full repository so the `references/` files are available.

### Validation Fails

Run:

```bash
python3 scripts/validate_skill.py
```

Fix the first reported error, then run the command again.

## Uninstall

```bash
rm -rf ~/.claude/skills/strategy-consulting-visualization
```
