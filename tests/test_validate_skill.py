from __future__ import annotations

import importlib.util
import io
import tempfile
import textwrap
import unittest
from contextlib import redirect_stderr
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_validator():
    module_path = ROOT / "scripts" / "validate_skill.py"
    spec = importlib.util.spec_from_file_location("validate_skill", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


validator = load_validator()


class ValidateSkillTests(unittest.TestCase):
    def test_validate_skill_frontmatter_rejects_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: strategy-consulting-visualization
                    description: Use when turning notes into executive visualization specs.
                    license: MIT
                    ---

                    references/visualization-patterns.md
                    references/style-system.md
                    references/prompt-templates.md
                    references/quality-rubric.md
                    references/public-reference-corpus.md
                    references/iterative-review-loop.md
                    references/expert-review-loop.md
                    references/input-triage.md
                    references/document-type-profiles.md

                    This skill is not affiliated with, endorsed by, or sponsored by any consulting firm.
                    """
                ),
                encoding="utf-8",
            )

            original_root = validator.ROOT
            validator.ROOT = root
            try:
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        validator.validate_skill_frontmatter()
            finally:
                validator.ROOT = original_root

    def test_validate_skill_frontmatter_accepts_name_and_description_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SKILL.md").write_text(
                textwrap.dedent(
                    """\
                    ---
                    name: strategy-consulting-visualization
                    description: Use when turning notes into executive visualization specs.
                    ---

                    references/visualization-patterns.md
                    references/style-system.md
                    references/prompt-templates.md
                    references/quality-rubric.md
                    references/public-reference-corpus.md
                    references/iterative-review-loop.md
                    references/expert-review-loop.md
                    references/input-triage.md
                    references/document-type-profiles.md

                    This skill is not affiliated with, endorsed by, or sponsored by any consulting firm.
                    """
                ),
                encoding="utf-8",
            )

            original_root = validator.ROOT
            validator.ROOT = root
            try:
                validator.validate_skill_frontmatter()
            finally:
                validator.ROOT = original_root

    def test_validate_renderer_fails_when_committed_svg_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            specs = root / "examples" / "render-specs"
            rendered = root / "assets" / "rendered"
            scripts.mkdir()
            specs.mkdir(parents=True)
            rendered.mkdir(parents=True)

            (scripts / "render_slide_spec.py").write_text(
                textwrap.dedent(
                    """
                    def render(spec):
                        return "<svg>fresh render</svg>\\n"
                    """
                ),
                encoding="utf-8",
            )
            (specs / "demo.json").write_text('{"pattern": "summary_strip"}', encoding="utf-8")
            (rendered / "demo.svg").write_text("<svg>stale render</svg>\n", encoding="utf-8")

            original_root = validator.ROOT
            validator.ROOT = root
            try:
                with redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        validator.validate_renderer()
            finally:
                validator.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
