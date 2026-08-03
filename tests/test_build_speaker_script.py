from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str):
    module_path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = load_module("build_speaker_script")


def _gap_spec(headline: str, notes=None) -> dict:
    spec = {
        "pattern": "gap",
        "headline": headline,
        "items": [
            {"label": "Demand", "value": 100, "emphasis": True},
            {"label": "Capacity", "value": 60},
        ],
    }
    if notes is not None:
        spec["notes"] = notes
    return spec


def _write_specs(tmp_dir: Path, specs: list[dict]) -> list[Path]:
    paths = []
    for i, spec in enumerate(specs, start=1):
        path = tmp_dir / f"spec-{i}.json"
        path.write_text(json.dumps(spec), encoding="utf-8")
        paths.append(path)
    return paths


class NotesParagraphsTests(unittest.TestCase):
    def test_list_of_strings_each_becomes_one_paragraph(self) -> None:
        self.assertEqual(
            builder.notes_paragraphs(["First paragraph.", "Second paragraph."]),
            ["First paragraph.", "Second paragraph."],
        )

    def test_string_splits_into_paragraphs_on_blank_lines(self) -> None:
        self.assertEqual(
            builder.notes_paragraphs("First paragraph.\n\nSecond paragraph."),
            ["First paragraph.", "Second paragraph."],
        )

    def test_string_splits_on_multiple_blank_lines(self) -> None:
        self.assertEqual(
            builder.notes_paragraphs("One.\n\n\n\nTwo."),
            ["One.", "Two."],
        )

    def test_single_paragraph_string_has_internal_newlines_collapsed(self) -> None:
        # A soft-wrapped single paragraph reads as one sentence, not a break.
        self.assertEqual(
            builder.notes_paragraphs("This line\nwraps softly\nacross three lines."),
            ["This line wraps softly across three lines."],
        )

    def test_list_item_internal_newlines_also_collapse(self) -> None:
        self.assertEqual(
            builder.notes_paragraphs(["Soft\nwrapped\nitem."]),
            ["Soft wrapped item."],
        )

    def test_none_normalizes_to_empty(self) -> None:
        self.assertEqual(builder.notes_paragraphs(None), [])

    def test_empty_string_normalizes_to_empty(self) -> None:
        self.assertEqual(builder.notes_paragraphs(""), [])

    def test_empty_list_normalizes_to_empty(self) -> None:
        self.assertEqual(builder.notes_paragraphs([]), [])

    def test_whitespace_only_paragraphs_are_dropped(self) -> None:
        self.assertEqual(builder.notes_paragraphs("   \n\n   \n\nReal paragraph."), ["Real paragraph."])

    def test_unsupported_type_normalizes_to_empty_without_raising(self) -> None:
        self.assertEqual(builder.notes_paragraphs(42), [])
        self.assertEqual(builder.notes_paragraphs({"not": "a string or list"}), [])


class ManifestOrderTests(unittest.TestCase):
    def test_slides_render_in_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            specs = [_gap_spec("Alpha slide"), _gap_spec("Beta slide"), _gap_spec("Gamma slide")]
            paths = _write_specs(tmp_dir, specs)
            html = builder.build_script(paths, "Order test deck")
            positions = [html.index(label) for label in ("Alpha slide", "Beta slide", "Gamma slide")]
            self.assertEqual(positions, sorted(positions))

    def test_page_numbers_count_up_from_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("One"), _gap_spec("Two"), _gap_spec("Three")])
            html = builder.build_script(paths, "Counter deck")
            self.assertIn("1 / 3", html)
            self.assertIn("2 / 3", html)
            self.assertIn("3 / 3", html)

    def test_cli_resolves_slide_paths_relative_to_manifest_not_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            specs_dir = tmp_dir / "nested" / "specs"
            specs_dir.mkdir(parents=True)
            (specs_dir / "one.json").write_text(json.dumps(_gap_spec("Nested slide")), encoding="utf-8")
            manifest_path = tmp_dir / "nested" / "deck.json"
            manifest_path.write_text(
                json.dumps({"title": "Nested deck", "slides": ["specs/one.json"]}), encoding="utf-8"
            )
            output_path = tmp_dir / "out.html"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_speaker_script.py"),
                    "--manifest",
                    str(manifest_path),
                    "-o",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                cwd=str(ROOT),  # deliberately NOT the manifest's own directory
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Nested slide", html)


class MissingNotesMarkerTests(unittest.TestCase):
    def test_slide_without_notes_still_renders_with_a_muted_marker_en(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("No script here")])
            html = builder.build_script(paths, "Deck", lang="en")
            self.assertIn("(no script)", html)
            self.assertIn("No script here", html)  # the slide itself still renders

    def test_slide_without_notes_still_renders_with_a_muted_marker_ja(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("No script here")])
            html = builder.build_script(paths, "Deck", lang="ja")
            self.assertIn("（原稿なし）", html)

    def test_notes_present_suppresses_the_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("Has a script", notes="Some spoken narration.")])
            html = builder.build_script(paths, "Deck", lang="en")
            self.assertNotIn("(no script)", html)
            self.assertIn("Some spoken narration.", html)


class EscapingTests(unittest.TestCase):
    def test_script_tag_in_notes_stays_inert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(
                tmp_dir, [_gap_spec("Safe headline", notes="<script>alert(1)</script>")]
            )
            html = builder.build_script(paths, "Deck")
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_script_tag_in_headline_stays_inert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("<script>alert(2)</script>")])
            html = builder.build_script(paths, "Deck")
            self.assertNotIn("<script>alert(2)</script>", html)
            self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;", html)

    def test_script_tag_in_deck_title_stays_inert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("Headline")])
            html = builder.build_script(paths, "<script>alert(3)</script>")
            self.assertNotIn("<script>alert(3)</script>", html)
            self.assertIn("&lt;script&gt;alert(3)&lt;/script&gt;", html)

    def test_script_tag_in_cover_date_stays_inert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            cover = {
                "pattern": "cover",
                "title": "Cover",
                "date": "<script>alert(4)</script>",
            }
            paths = _write_specs(tmp_dir, [cover])
            html = builder.build_script(paths, "Deck")
            self.assertNotIn("<script>alert(4)</script>", html)
            self.assertIn("&lt;script&gt;alert(4)&lt;/script&gt;", html)


class LanguageModeTests(unittest.TestCase):
    def test_default_lang_is_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("Headline", notes="Notes.")])
            html = builder.build_script(paths, "Deck")
            self.assertIn('<html lang="en">', html)
            self.assertNotIn('class="lang-ja"', html)
            self.assertIn("Speaker script", html)

    def test_ja_lang_sets_body_class_and_kicker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("Headline", notes="Notes.")])
            html = builder.build_script(paths, "Deck", lang="ja")
            self.assertIn('<html lang="ja">', html)
            self.assertIn('<body class="lang-ja">', html)
            self.assertIn("発表原稿", html)

    def test_ja_narration_gets_the_1_9_line_height_rule(self) -> None:
        html = builder.STYLE
        self.assertIn("body.lang-ja .notes p { line-height: 1.9; font-feature-settings: 'palt'; }", html)
        self.assertIn(".notes p { font-size: 20px; line-height: 1.7;", html)

    def test_unrecognized_lang_falls_back_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("Headline")])
            html = builder.build_script(paths, "Deck", lang="fr")
            self.assertIn('<html lang="en">', html)
            self.assertNotIn('class="lang-ja"', html)


class PageStructureTests(unittest.TestCase):
    def test_one_page_section_per_slide_plus_one_cover_page(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("A"), _gap_spec("B"), _gap_spec("C"), _gap_spec("D")])
            html = builder.build_script(paths, "Deck")
            self.assertEqual(html.count('class="page slide-page"'), 4)
            self.assertEqual(html.count('class="page cover-page"'), 1)

    def test_print_layout_is_a4_one_slide_per_page(self) -> None:
        html = builder.STYLE
        self.assertIn("@page { size: A4 landscape; margin: 12mm; }", html)
        # Slide left / script right: the side-by-side grid exists on screen
        # and stays two-column in print.
        self.assertIn(".duo { display: grid;", html)
        self.assertIn("break-after: page; page-break-after: always;", html)
        # The last page must not force a further break.
        self.assertIn(".page:last-child { break-after: auto; page-break-after: auto; }", html)

    def test_missing_notes_marker_never_silently_skips_the_slide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("Only slide")])
            html = builder.build_script(paths, "Deck")
            self.assertEqual(html.count('class="page slide-page"'), 1)
            self.assertIn("(no script)", html)


class SvgEmbedTests(unittest.TestCase):
    def test_one_svg_embedded_per_slide_with_xmlns_stripped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("A"), _gap_spec("B"), _gap_spec("C")])
            html = builder.build_script(paths, "Deck")
            self.assertEqual(html.count("<svg"), 3)
            self.assertEqual(html.count('class="script-slide"'), 3)
            self.assertNotIn('xmlns="http://www.w3.org/2000/svg"', html)

    def test_zero_http_references(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            paths = _write_specs(tmp_dir, [_gap_spec("A", notes="No links here.")])
            html = builder.build_script(paths, "Deck")
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)


class SharedContractTests(unittest.TestCase):
    """The notes field is a shared, renderer-invisible contract: adding it to
    a spec must never change the rendered SVG (see FEATURES-V23-BRIEF.md's
    "Shared contract: the notes field")."""

    def test_notes_field_is_ignored_by_the_svg_renderer(self) -> None:
        renderer = load_module("render_slide_spec")
        base_spec = _gap_spec("Capacity trails demand")
        with_notes_str = _gap_spec("Capacity trails demand", notes="Some spoken narration.")
        with_notes_list = _gap_spec("Capacity trails demand", notes=["Para one.", "Para two."])
        rendered_base = renderer.render(base_spec)
        self.assertEqual(rendered_base, renderer.render(with_notes_str))
        self.assertEqual(rendered_base, renderer.render(with_notes_list))

    def test_board_update_ja_specs_render_byte_identically_notes_or_not(self) -> None:
        renderer = load_module("render_slide_spec")
        specs_dir = ROOT / "templates" / "decks" / "board-update-ja" / "specs"
        for spec_path in sorted(specs_dir.glob("*.json")):
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            self.assertIn("notes", spec, f"{spec_path.name} should carry demo notes")
            without_notes = {k: v for k, v in spec.items() if k != "notes"}
            self.assertEqual(
                renderer.render(spec),
                renderer.render(without_notes),
                f"{spec_path.name}: adding notes must not change the rendered SVG",
            )


class DemoContentTests(unittest.TestCase):
    def test_all_nine_board_update_ja_specs_carry_japanese_notes(self) -> None:
        specs_dir = ROOT / "templates" / "decks" / "board-update-ja" / "specs"
        spec_paths = sorted(specs_dir.glob("*.json"))
        self.assertEqual(len(spec_paths), 9)
        for spec_path in spec_paths:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            notes = spec.get("notes")
            self.assertIsInstance(notes, str, f"{spec_path.name} notes should be a string")
            self.assertTrue(notes.strip(), f"{spec_path.name} notes should not be blank")
            self.assertTrue(notes.endswith("。"), f"{spec_path.name} notes should be full Japanese sentences")

    def test_committed_demo_script_matches_a_fresh_build(self) -> None:
        manifest_path = ROOT / "templates" / "decks" / "board-update-ja" / "deck.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        spec_paths = [manifest_path.parent / p for p in manifest["slides"]]
        fresh = builder.build_script(spec_paths, manifest["title"], "ja")
        committed = (ROOT / "examples" / "demo-script.html").read_text(encoding="utf-8")
        self.assertEqual(
            fresh,
            committed,
            "stale demo script: regenerate examples/demo-script.html with "
            "scripts/build_speaker_script.py --manifest templates/decks/board-update-ja/deck.json "
            "-o examples/demo-script.html --lang ja",
        )

    def test_demo_script_has_zero_external_requests(self) -> None:
        html = (ROOT / "examples" / "demo-script.html").read_text(encoding="utf-8")
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script", html)


if __name__ == "__main__":
    unittest.main()
