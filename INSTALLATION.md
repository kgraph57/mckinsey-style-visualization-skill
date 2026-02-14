# Installation Guide

This guide provides detailed instructions for installing the McKinsey/BCG Style Visualization skill in Claude Code.

## Prerequisites

- Claude Code installed and configured
- Git installed (for cloning method)
- Basic familiarity with command line (optional)

## Installation Methods

### Method 1: Clone Repository (Recommended)

This method is recommended as it allows you to easily update the skill by pulling changes from the repository.

#### For Personal Skills (Available in All Projects)

```bash
# Clone to your personal skills directory
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git ~/.claude/skills/mckinsey-style-visualization
```

#### For Project-Specific Skills

```bash
# Navigate to your project directory
cd /path/to/your/project

# Clone to project skills directory
git clone https://github.com/kgraph57/mckinsey-style-visualization-skill.git .claude/skills/mckinsey-style-visualization
```

### Method 2: Direct Download

If you prefer not to use Git, you can download the skill file directly.

#### For Personal Skills

```bash
# Create the skills directory
mkdir -p ~/.claude/skills/mckinsey-style-visualization

# Download SKILL.md
curl -o ~/.claude/skills/mckinsey-style-visualization/SKILL.md https://raw.githubusercontent.com/kgraph57/mckinsey-style-visualization-skill/main/SKILL.md
```

#### For Project-Specific Skills

```bash
# Navigate to your project directory
cd /path/to/your/project

# Create the skills directory
mkdir -p .claude/skills/mckinsey-style-visualization

# Download SKILL.md
curl -o .claude/skills/mckinsey-style-visualization/SKILL.md https://raw.githubusercontent.com/kgraph57/mckinsey-style-visualization-skill/main/SKILL.md
```

### Method 3: Manual Download

1. Visit the [GitHub repository](https://github.com/kgraph57/mckinsey-style-visualization-skill)
2. Click on `SKILL.md`
3. Click the "Raw" button
4. Save the file to your computer
5. Create the appropriate directory:
   - Personal: `~/.claude/skills/mckinsey-style-visualization/`
   - Project: `.claude/skills/mckinsey-style-visualization/`
6. Move the downloaded `SKILL.md` file into the directory

## Verification

After installation, verify that the skill is available:

1. Open Claude Code
2. Type `/` to see available commands
3. Look for `/mckinsey-style-visualization` in the list

Alternatively, ask Claude:
```
What skills are available?
```

The skill should appear in the list with its description.

## Updating the Skill

### If Installed via Git Clone

```bash
# Navigate to the skill directory
cd ~/.claude/skills/mckinsey-style-visualization

# Pull the latest changes
git pull
```

### If Installed via Direct Download

Re-download the `SKILL.md` file using the same method as installation.

## Troubleshooting

### Skill Not Appearing

If the skill doesn't appear in Claude Code:

1. **Check the directory structure:**
   ```bash
   # For personal skills
   ls -la ~/.claude/skills/mckinsey-style-visualization/
   
   # For project skills
   ls -la .claude/skills/mckinsey-style-visualization/
   ```
   
   You should see `SKILL.md` in the directory.

2. **Verify the file content:**
   ```bash
   head -n 20 ~/.claude/skills/mckinsey-style-visualization/SKILL.md
   ```
   
   The file should start with YAML frontmatter (between `---` markers).

3. **Restart Claude Code:**
   Close and reopen Claude Code to ensure it picks up the new skill.

4. **Check for character budget issues:**
   If you have many skills, they may exceed the character budget. Run `/context` to check for warnings about excluded skills.

### Skill Not Triggering Automatically

If Claude doesn't use the skill automatically when expected:

1. Try invoking it directly with `/mckinsey-style-visualization`
2. Make your request more specific to match the skill description
3. Check that the skill description includes keywords you're using

### Permission Issues

If you encounter permission errors when creating directories:

```bash
# For personal skills, ensure the .claude directory exists
mkdir -p ~/.claude/skills

# Check permissions
ls -ld ~/.claude
```

## Uninstallation

To remove the skill:

```bash
# For personal skills
rm -rf ~/.claude/skills/mckinsey-style-visualization

# For project skills
rm -rf .claude/skills/mckinsey-style-visualization
```

## Support

If you encounter issues not covered in this guide:

1. Check the [README](README.md) for usage instructions
2. Review the [SKILL.md](SKILL.md) for detailed documentation
3. Open an issue on [GitHub](https://github.com/kgraph57/mckinsey-style-visualization-skill/issues)

## Next Steps

After installation, see the [README](README.md) for:
- Usage examples
- Visualization types
- Design principles
- Quality checklist
