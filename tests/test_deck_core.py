from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_core():
    spec = importlib.util.spec_from_file_location("deck_core", ROOT / "scripts/deck_core.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManifestNormalizationTests(unittest.TestCase):
    def test_strings_objects_and_mixed_entries_preserve_order_and_relative_paths(self):
        core = load_core()
        manifest = {"slides": ["specs/cover.json", {"spec": "specs/answer.json"}, "specs/end.json"], "futureMetadata": True}
        slides = core.normalize_manifest(manifest, Path("project/deck.json"))
        self.assertEqual([s.spec_path for s in slides], [Path("project/specs/cover.json"), Path("project/specs/answer.json"), Path("project/specs/end.json")])
        self.assertEqual([s.slide_id for s in slides], ["slide-001", "slide-002", "slide-003"])
        self.assertEqual([s.scene_path for s in slides], [None, None, None])

    def test_classic_does_not_validate_or_resolve_scene_data(self):
        core = load_core()
        for scene in ("../missing.json", {"invalid": "ignored"}, None):
            with self.subTest(scene=scene):
                slides = core.normalize_manifest({"slides": [{"spec": "../shared.json", "scene": scene}]}, Path("project/deck.json"))
                self.assertEqual(slides[0].spec_path, Path("project/../shared.json"))
                self.assertIsNone(slides[0].scene_path)

    def test_object_requires_nonempty_string_spec(self):
        core = load_core()
        for entry in ({"scene": "scene.json"}, {"spec": ""}, {"spec": 3}, {"spec": None}):
            with self.subTest(entry=entry), self.assertRaisesRegex(ValueError, "spec"):
                core.normalize_manifest({"slides": [entry]}, Path("deck.json"))

    def test_explicit_ids_are_preserved_and_generated_ids_are_deterministic(self):
        core = load_core()
        slides = core.normalize_manifest({"slides": [{"spec": "a.json", "id": "decision"}, "b.json"]}, Path("deck.json"))
        self.assertEqual([s.slide_id for s in slides], ["decision", "slide-002"])

    def test_duplicate_explicit_or_generated_ids_fail(self):
        core = load_core()
        for entries in ([{"spec": "a.json", "id": "same"}, {"spec": "b.json", "id": "same"}], ["a.json", {"spec": "b.json", "id": "slide-001"}]):
            with self.subTest(entries=entries), self.assertRaisesRegex(ValueError, "duplicate.*id"):
                core.normalize_manifest({"slides": entries}, Path("deck.json"))

    def test_invalid_ids_and_slide_entries_fail(self):
        core = load_core()
        for entry in (None, 5, [], "", {"spec": "a.json", "id": " "}, {"spec": "a.json", "id": 3}):
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                core.normalize_manifest({"slides": [entry]}, Path("deck.json"))
        for manifest in ({}, {"slides": "a.json"}, [], None):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                core.normalize_manifest(manifest, Path("deck.json"))

    def test_empty_manifest_can_be_combined_with_positional_specs_by_classic_cli(self):
        self.assertEqual(load_core().normalize_manifest({"slides": []}, Path("deck.json")), [])

    def test_loader_reads_utf8_and_rejects_nonobject_json(self):
        core = load_core()
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "deck.json"
            path.write_text('{"title":"意思決定", "slides":[]}', encoding="utf-8")
            self.assertEqual(core.load_manifest(path), {"title": "意思決定", "slides": []})
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "object"):
                core.load_manifest(path)


class ScenePathTests(unittest.TestCase):
    def test_interactive_resolves_scene_but_preserves_classic_spec_resolution(self):
        core = load_core()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            slides = core.normalize_manifest({"slides": ["a.json", {"spec": "../shared.json", "scene": "scenes/detail.json"}]}, root / "deck.json", interactive=True)
            self.assertIsNone(slides[0].scene_path)
            self.assertEqual(slides[1].spec_path, root / "../shared.json")
            self.assertEqual(slides[1].scene_path, (root / "scenes/detail.json").resolve())

    def test_scene_path_rejects_lexical_escape(self):
        core = load_core()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "deck"
            root.mkdir()
            for scene in ("../outside.json", "scenes/../../outside.json", str(Path(td) / "outside.json")):
                with self.subTest(scene=scene), self.assertRaisesRegex(ValueError, "scene.*(root|relative)"):
                    core.resolve_scene_path(root, scene)

    def test_scene_path_rejects_symlink_escape_including_missing_target(self):
        core = load_core()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "deck"
            root.mkdir()
            outside = Path(td) / "outside"
            outside.mkdir()
            (root / "scenes").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "scene.*root"):
                core.normalize_manifest({"slides": [{"spec": "a.json", "scene": "scenes/missing.json"}]}, root / "deck.json", interactive=True)

    def test_scene_path_allows_internal_symlink_and_rejects_bad_path_values(self):
        core = load_core()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "local").mkdir()
            (root / "scenes").symlink_to(root / "local", target_is_directory=True)
            self.assertEqual(core.resolve_scene_path(root, "scenes/a.json"), (root / "local/a.json").resolve())
            for scene in ("", 5, None, "bad\x00path"):
                with self.subTest(scene=scene), self.assertRaises(ValueError):
                    core.resolve_scene_path(root, scene)


if __name__ == "__main__":
    unittest.main()
