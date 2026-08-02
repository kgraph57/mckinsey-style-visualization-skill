from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

KNOWN_ARCHETYPES = {
    "board-update",
    "strategy-recommendation",
    "project-status",
    "market-entry",
    "sales-proposal",
    "board-update-ja",
}


def load_module(name: str):
    module_path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


scaffolder = load_module("scaffold_deck")
renderer = load_module("render_slide_spec")
builder = load_module("build_html_deck")


class DiscoverArchetypesTests(unittest.TestCase):
    def test_discovers_all_six_shipped_archetypes(self) -> None:
        self.assertEqual(set(scaffolder.discover_archetypes()), KNOWN_ARCHETYPES)

    def test_returns_empty_list_for_missing_templates_root(self) -> None:
        original = scaffolder.TEMPLATES_ROOT
        try:
            scaffolder.TEMPLATES_ROOT = ROOT / "templates" / "does-not-exist"
            self.assertEqual(scaffolder.discover_archetypes(), [])
        finally:
            scaffolder.TEMPLATES_ROOT = original


class ListArchetypesTests(unittest.TestCase):
    def test_list_prints_every_archetype_with_a_slide_count_and_description(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            scaffolder.list_archetypes()
        text = out.getvalue()
        for name in KNOWN_ARCHETYPES:
            self.assertIn(name, text)
        manifest = scaffolder.load_manifest("board-update")
        self.assertIn(f"({len(manifest['slides'])} slides)", text)
        self.assertIn(manifest["description"], text)

    def test_list_raises_when_no_archetypes_found(self) -> None:
        original = scaffolder.TEMPLATES_ROOT
        try:
            scaffolder.TEMPLATES_ROOT = ROOT / "templates" / "does-not-exist"
            err = io.StringIO()
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stderr(err):
                    scaffolder.list_archetypes()
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("ERROR", err.getvalue())
        finally:
            scaffolder.TEMPLATES_ROOT = original


class ScaffoldCopyTests(unittest.TestCase):
    def test_unknown_archetype_exits_with_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stderr(err):
                    scaffolder.scaffold("not-a-real-archetype", Path(tmp) / "out", None, False)
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("unknown archetype", err.getvalue())
            for name in KNOWN_ARCHETYPES:
                self.assertIn(name, err.getvalue())

    def test_scaffold_copies_manifest_and_every_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            out = io.StringIO()
            with redirect_stdout(out):
                scaffolder.scaffold("board-update", output, None, False)

            source = ROOT / "templates" / "decks" / "board-update"
            source_manifest = json.loads((source / "deck.json").read_text(encoding="utf-8"))
            copied_manifest = json.loads((output / "deck.json").read_text(encoding="utf-8"))
            self.assertEqual(copied_manifest, source_manifest)

            source_specs = sorted(p.name for p in (source / "specs").glob("*.json"))
            copied_specs = sorted(p.name for p in (output / "specs").glob("*.json"))
            self.assertEqual(source_specs, copied_specs)
            for name in source_specs:
                self.assertEqual(
                    (source / "specs" / name).read_text(encoding="utf-8"),
                    (output / "specs" / name).read_text(encoding="utf-8"),
                )
            self.assertIn("OK: scaffolded 'board-update'", out.getvalue())
            self.assertIn("Next steps", out.getvalue())

    def test_scaffold_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "nested" / "deeper" / "out"
            with redirect_stdout(io.StringIO()):
                scaffolder.scaffold("project-status", output, None, False)
            self.assertTrue((output / "deck.json").exists())


class ScaffoldTitleRewriteTests(unittest.TestCase):
    def test_title_rewrites_manifest_and_cover_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            with redirect_stdout(io.StringIO()):
                scaffolder.scaffold("board-update", output, "My Custom Deck Title", False)

            manifest = json.loads((output / "deck.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["title"], "My Custom Deck Title")

            cover_spec = json.loads((output / "specs" / "01-cover.json").read_text(encoding="utf-8"))
            self.assertEqual(cover_spec["title"], "My Custom Deck Title")

    def test_no_title_leaves_manifest_and_cover_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            with redirect_stdout(io.StringIO()):
                scaffolder.scaffold("board-update", output, None, False)

            source_cover = json.loads(
                (ROOT / "templates" / "decks" / "board-update" / "specs" / "01-cover.json").read_text(encoding="utf-8")
            )
            copied_cover = json.loads((output / "specs" / "01-cover.json").read_text(encoding="utf-8"))
            self.assertEqual(copied_cover["title"], source_cover["title"])

    def test_title_rewrite_preserves_japanese_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            with redirect_stdout(io.StringIO()):
                scaffolder.scaffold("board-update-ja", output, "第1四半期アップデート", False)

            manifest_text = (output / "deck.json").read_text(encoding="utf-8")
            self.assertIn("第1四半期アップデート", manifest_text)
            self.assertNotIn("\\u", manifest_text)  # written literally, not \uXXXX-escaped

            cover_spec = json.loads((output / "specs" / "01-cover.json").read_text(encoding="utf-8"))
            self.assertEqual(cover_spec["title"], "第1四半期アップデート")


class ScaffoldOverwriteGuardTests(unittest.TestCase):
    def test_refuses_nonempty_directory_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            output.mkdir()
            (output / "existing-file.txt").write_text("do not touch", encoding="utf-8")

            err = io.StringIO()
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stderr(err):
                    scaffolder.scaffold("board-update", output, None, False)
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("not empty", err.getvalue())
            self.assertIn("--force", err.getvalue())
            # Nothing was written on the refused path.
            self.assertFalse((output / "deck.json").exists())

    def test_force_overwrites_nonempty_directory_without_touching_unrelated_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            output.mkdir()
            sentinel = output / "unrelated-notes.txt"
            sentinel.write_text("keep me", encoding="utf-8")

            with redirect_stdout(io.StringIO()):
                scaffolder.scaffold("board-update", output, None, True)

            self.assertTrue((output / "deck.json").exists())
            self.assertTrue((output / "specs").is_dir())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep me")

    def test_empty_existing_directory_does_not_require_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            output.mkdir()
            with redirect_stdout(io.StringIO()):
                scaffolder.scaffold("board-update", output, None, False)
            self.assertTrue((output / "deck.json").exists())

    def test_output_path_that_is_a_file_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            output.write_text("i am a file", encoding="utf-8")

            err = io.StringIO()
            with self.assertRaises(SystemExit) as ctx:
                with redirect_stderr(err):
                    scaffolder.scaffold("board-update", output, None, False)
            self.assertEqual(ctx.exception.code, 1)
            self.assertIn("not a directory", err.getvalue())


class EveryArchetypeScaffoldsAndBuildsTests(unittest.TestCase):
    """Mirrors the contract's acceptance command: scaffold into a temp dir,
    then build an HTML deck from the copy, for every shipped archetype."""

    def test_every_archetype_scaffolds_and_builds_a_deck(self) -> None:
        for archetype in scaffolder.discover_archetypes():
            with self.subTest(archetype=archetype):
                with tempfile.TemporaryDirectory() as tmp:
                    output = Path(tmp) / "out"
                    with redirect_stdout(io.StringIO()):
                        scaffolder.scaffold(archetype, output, None, False)

                    manifest = json.loads((output / "deck.json").read_text(encoding="utf-8"))
                    spec_paths = [output / p for p in manifest["slides"]]
                    for spec_path in spec_paths:
                        self.assertTrue(spec_path.exists(), f"missing {spec_path}")
                        spec = json.loads(spec_path.read_text(encoding="utf-8"))
                        svg = renderer.render(spec)
                        self.assertIn("<svg", svg)

                    html = builder.build_deck(spec_paths, manifest["title"])
                    self.assertEqual(html.count('<section class="slide"'), len(spec_paths))
                    for marker in ("http://", "https://", "@import"):
                        self.assertNotIn(marker, html.replace("http://www.w3.org/2000/svg", ""))


class ScaffoldCliTests(unittest.TestCase):
    """A few true subprocess-level checks of the documented CLI contract."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "scaffold_deck.py"), *args],
            capture_output=True,
            text=True,
        )

    def test_cli_list_exits_zero_and_lists_archetypes(self) -> None:
        result = self._run("--list")
        self.assertEqual(result.returncode, 0)
        for name in KNOWN_ARCHETYPES:
            self.assertIn(name, result.stdout)

    def test_cli_missing_output_errors(self) -> None:
        result = self._run("board-update")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR", result.stderr)
        self.assertIn("-o/--output", result.stderr)

    def test_cli_missing_archetype_errors(self) -> None:
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR", result.stderr)
        self.assertIn("archetype is required", result.stderr)

    def test_cli_end_to_end_scaffold_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "out"
            result = self._run("sales-proposal", "-o", str(output), "--title", "CLI Smoke Test")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((output / "deck.json").exists())

            build = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_html_deck.py"),
                    "--manifest",
                    str(output / "deck.json"),
                    "-o",
                    str(output / "deck.html"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            self.assertTrue((output / "deck.html").exists())


if __name__ == "__main__":
    unittest.main()
