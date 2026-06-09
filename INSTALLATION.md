# Installation Guide

This guide installs Strategy Consulting Visualization Skill for agent tools that support the `SKILL.md` convention.

## Prerequisites

- An agent tool that can load local skills.
- Git for clone-based installation, or `curl` for direct download.

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

## Direct Download

Use this when you only need the entrypoint and not the full reference package.

```bash
mkdir -p ~/.claude/skills/strategy-consulting-visualization
curl -o ~/.claude/skills/strategy-consulting-visualization/SKILL.md https://raw.githubusercontent.com/kgraph57/mckinsey-style-visualization-skill/main/SKILL.md
```

For marketplace-quality behavior, clone the full repository instead of downloading only `SKILL.md`, because the skill references files in `references/`.

## Verify

After clone-based installation:

```bash
cd ~/.claude/skills/strategy-consulting-visualization
python3 scripts/validate_skill.py
```

Expected:

```text
OK: skill package passed validation
```

## Update

```bash
cd ~/.claude/skills/strategy-consulting-visualization
git pull
python3 scripts/validate_skill.py
```

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
