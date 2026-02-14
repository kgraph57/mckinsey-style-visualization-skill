# Contributing to McKinsey/BCG Style Visualization Skill

Thank you for your interest in contributing to this Claude Code Skill! This document provides guidelines for contributing to the project.

## How to Contribute

### Reporting Issues

If you encounter bugs, have feature requests, or find areas for improvement:

1. Check the [existing issues](https://github.com/kgraph57/mckinsey-style-visualization-skill/issues) to avoid duplicates
2. Open a new issue with a clear title and description
3. For bugs, include:
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Claude Code version
   - Operating system

### Suggesting Enhancements

We welcome suggestions for new visualization types, design improvements, or additional features:

1. Open an issue with the "enhancement" label
2. Clearly describe the proposed feature
3. Explain the use case and benefits
4. Provide examples if possible

### Submitting Pull Requests

1. **Fork the repository** to your GitHub account
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mckinsey-style-visualization-skill.git
   cd mckinsey-style-visualization-skill
   ```
3. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes** following the guidelines below
5. **Test your changes** thoroughly with Claude Code
6. **Commit your changes** with clear, descriptive messages:
   ```bash
   git commit -m "Add new visualization type: [name]"
   ```
7. **Push to your fork**:
   ```bash
   git push origin feature/your-feature-name
   ```
8. **Open a Pull Request** from your fork to the main repository

## Contribution Guidelines

### For SKILL.md Changes

When modifying `SKILL.md`:

1. **Maintain the YAML frontmatter structure:**
   - Keep the `name` and `description` fields intact
   - Only modify frontmatter if absolutely necessary

2. **Follow the existing format:**
   - Use consistent heading levels
   - Maintain the current section structure
   - Keep examples clear and concise

3. **Add new visualization types:**
   - Follow the existing template for Types 1-11
   - Include: Use case, Elements, Example
   - Add corresponding prompt engineering template

4. **Update version history:**
   - Add a new entry at the top of the Version History section
   - Use the format: `- **vX.X** (YYYY-MM-DD): Description of changes`

5. **Test with Claude Code:**
   - Ensure Claude can parse the updated SKILL.md
   - Test that new instructions work as expected
   - Verify automatic skill invocation still works

### For README.md Changes

When updating the README:

1. Keep the structure consistent with the current format
2. Update examples if you add new features
3. Ensure all links work correctly
4. Update the version history if applicable

### For Documentation

1. Write in clear, professional English
2. Use markdown formatting consistently
3. Include code examples where appropriate
4. Keep explanations concise but comprehensive

### Code of Conduct

- Be respectful and constructive in all interactions
- Focus on the content, not the person
- Accept feedback gracefully
- Help create a welcoming environment for all contributors

## What We're Looking For

### High Priority

- New visualization types with clear use cases
- Improved prompt engineering templates
- Better examples and use cases
- Documentation improvements
- Bug fixes

### Medium Priority

- Additional design guidelines
- Integration examples with other skills
- Accessibility improvements
- Internationalization (with careful consideration of rendering issues)

### Low Priority

- Minor formatting changes
- Typo fixes (though still appreciated!)

## Testing Your Changes

Before submitting a pull request:

1. **Install the modified skill** in Claude Code:
   ```bash
   # Copy your modified version to the skills directory
   cp -r /path/to/your/fork ~/.claude/skills/mckinsey-style-visualization-test
   ```

2. **Test automatic invocation:**
   - Ask Claude to create visualizations matching the skill description
   - Verify Claude loads the skill automatically

3. **Test manual invocation:**
   - Use `/mckinsey-style-visualization` command
   - Test with various requests

4. **Test new features:**
   - If you added new visualization types, test them thoroughly
   - Verify prompt templates produce expected results
   - Check that examples work correctly

5. **Verify quality:**
   - Run through the quality checklist in SKILL.md
   - Ensure output matches McKinsey/BCG style guidelines

## Review Process

1. A maintainer will review your pull request
2. They may request changes or ask questions
3. Once approved, your changes will be merged
4. Your contribution will be acknowledged in the commit history

## Recognition

All contributors will be recognized in the project. Significant contributions may be highlighted in release notes.

## Questions?

If you have questions about contributing:

1. Check this document first
2. Review existing issues and pull requests
3. Open a new issue with the "question" label
4. Be patient - we'll respond as soon as possible

## License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

Thank you for helping improve this Claude Code Skill! Your contributions make it better for everyone.
