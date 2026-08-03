from __future__ import annotations

import copy
import importlib.util
import json
import re
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


builder = load_module("build_html_article")
renderer = load_module("render_slide_spec")


def _write_manifest(root: Path, slides: list[dict], title: str = "Test Deck", description: str = "") -> tuple[list[Path], dict]:
    """Write each slide dict to its own JSON file plus a manifest referencing
    them in order; return (spec_paths, manifest_dict) ready for build_article."""
    spec_paths: list[Path] = []
    slide_names: list[str] = []
    for i, slide in enumerate(slides, start=1):
        name = f"{i:02d}.json"
        (root / name).write_text(json.dumps(slide), encoding="utf-8")
        spec_paths.append(root / name)
        slide_names.append(name)
    manifest = {"title": title, "description": description, "slides": slide_names}
    (root / "deck.json").write_text(json.dumps(manifest), encoding="utf-8")
    return spec_paths, manifest


# A minimal non-chromeless pattern (matches the "gap" fixtures used across
# the repo's own test suites, e.g. tests/test_build_html_report.py).
def _gap_spec(headline: str, **extra) -> dict:
    spec = {
        "pattern": "gap",
        "headline": headline,
        "items": [
            {"label": "Demand", "value": 100, "emphasis": True},
            {"label": "Capacity", "value": 60},
        ],
    }
    spec.update(extra)
    return spec


class NotesParagraphsTests(unittest.TestCase):
    def test_list_is_used_as_is_one_paragraph_per_item(self) -> None:
        self.assertEqual(
            builder.notes_paragraphs(["First paragraph.", "Second paragraph."]),
            ["First paragraph.", "Second paragraph."],
        )

    def test_string_splits_on_blank_lines(self) -> None:
        notes = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        self.assertEqual(
            builder.notes_paragraphs(notes),
            ["First paragraph.", "Second paragraph.", "Third paragraph."],
        )

    def test_string_with_no_blank_line_is_a_single_paragraph(self) -> None:
        self.assertEqual(builder.notes_paragraphs("Just one paragraph."), ["Just one paragraph."])

    def test_internal_newlines_within_a_paragraph_collapse_to_spaces(self) -> None:
        self.assertEqual(
            builder.notes_paragraphs("Line one\nline two continues."),
            ["Line one line two continues."],
        )

    def test_missing_or_none_returns_empty_list(self) -> None:
        self.assertEqual(builder.notes_paragraphs(None), [])

    def test_non_string_non_list_returns_empty_list(self) -> None:
        self.assertEqual(builder.notes_paragraphs(42), [])

    def test_blank_or_whitespace_only_items_are_dropped(self) -> None:
        self.assertEqual(builder.notes_paragraphs(["Real one.", "   ", ""]), ["Real one."])

    def test_empty_string_returns_empty_list(self) -> None:
        self.assertEqual(builder.notes_paragraphs("   "), [])


class SharedContractTests(unittest.TestCase):
    """The shared notes contract: the SVG renderer must ignore `notes`
    entirely, for every shipped board-update spec (not just a synthetic one)."""

    def test_notes_do_not_change_rendered_svg_for_every_board_update_spec(self) -> None:
        specs_dir = ROOT / "templates" / "decks" / "board-update" / "specs"
        spec_paths = sorted(specs_dir.glob("*.json"))
        self.assertTrue(spec_paths, "expected board-update specs to exist")
        for path in spec_paths:
            with_notes = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("notes", with_notes, f"{path.name} is missing its demo notes field")
            without_notes = copy.deepcopy(with_notes)
            del without_notes["notes"]
            self.assertEqual(
                renderer.render(with_notes),
                renderer.render(without_notes),
                f"notes changed the rendered SVG for {path.name}",
            )

    def test_notes_do_not_change_rendered_svg_for_a_synthetic_spec(self) -> None:
        spec = _gap_spec("Capacity trails demand")
        without_notes = renderer.render(spec)
        spec["notes"] = ["A paragraph.", "Another one."]
        with_notes = renderer.render(spec)
        self.assertEqual(with_notes, without_notes)


class ManifestAndOrderingTests(unittest.TestCase):
    def test_slides_render_in_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(
                root,
                [_gap_spec("First finding"), _gap_spec("Second finding"), _gap_spec("Third finding")],
            )
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            first = html.index("First finding")
            second = html.index("Second finding")
            third = html.index("Third finding")
            self.assertTrue(first < second < third)

    def test_deck_shows_one_section_per_slide_including_chromeless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro"},
                _gap_spec("Content slide"),
                {"pattern": "end_cover", "title": "Thank you"},
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertEqual(html.count('<section class="slide-block"'), 3)
            self.assertEqual(html.count("<svg"), 3)


class NoNotesTests(unittest.TestCase):
    def test_slide_without_notes_still_renders_frame_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("No narration here")]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertIn("No narration here", html)  # the slide itself still renders
            self.assertNotIn('<div class="notes">', html)

    def test_chromeless_slide_without_notes_still_gets_a_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [{"pattern": "end_cover", "title": "Thank you"}]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertEqual(html.count('<section class="slide-block"'), 1)
            self.assertNotIn('<div class="notes">', html)

    def test_mixed_deck_only_notes_bearing_slides_get_a_notes_div(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                _gap_spec("Has no notes"),
                _gap_spec("Has notes", notes="A single paragraph of narration."),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertEqual(html.count('<div class="notes">'), 1)
            self.assertIn("A single paragraph of narration.", html)


class NotesRenderingTests(unittest.TestCase):
    def test_notes_list_renders_one_p_per_paragraph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Findings", notes=["Paragraph one.", "Paragraph two."])]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            notes_div = re.search(r'<div class="notes">(.*?)</div>', html, re.S).group(1)
            self.assertEqual(notes_div.count("<p>"), 2)
            self.assertIn("<p>Paragraph one.</p>", notes_div)
            self.assertIn("<p>Paragraph two.</p>", notes_div)

    def test_notes_string_splits_into_paragraphs_on_measure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Findings", notes="First para.\n\nSecond para.")]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertIn('class="notes"', html)
            self.assertIn("<p>First para.</p>", html)
            self.assertIn("<p>Second para.</p>", html)
            self.assertIn(".notes { max-width: var(--measure)", html)


class TocTests(unittest.TestCase):
    def test_toc_skips_chromeless_patterns_but_they_still_appear_in_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro"},
                _gap_spec("First finding"),
                {"pattern": "section_divider", "title": "Part two", "section_number": 2},
                _gap_spec("Second finding"),
                {"pattern": "end_cover", "title": "Thank you"},
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            toc = re.search(r'<nav class="toc".*?</nav>', html, re.S).group(0)
            self.assertIn("First finding", toc)
            self.assertIn("Second finding", toc)
            self.assertNotIn("Intro", toc)
            self.assertNotIn("Part two", toc)
            self.assertNotIn("Thank you", toc)
            # ...but every slide, chromeless or not, still gets a section.
            self.assertEqual(html.count('<section class="slide-block"'), 5)

    def test_toc_numbers_only_content_slides_sequentially(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro"},
                _gap_spec("First finding"),
                _gap_spec("Second finding"),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertIn(">1. First finding<", html)
            self.assertIn(">2. Second finding<", html)

    def test_toc_entries_link_to_anchors_that_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Anchor target")]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            href = re.search(r'href="#([^"]+)"', html).group(1)
            self.assertIn(f'id="{href}"', html)

    def test_no_toc_when_every_slide_is_chromeless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [{"pattern": "cover", "title": "Intro"}, {"pattern": "end_cover", "title": "Bye"}]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn('<nav class="toc"', html)

    def test_duplicate_headlines_get_unique_slugs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Repeat"), _gap_spec("Repeat")]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertIn('id="repeat"', html)
            self.assertIn('id="repeat-2"', html)


class MetaAndTitleTests(unittest.TestCase):
    def test_meta_line_uses_cover_presenter_and_date_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro", "presenter": "Ops Team", "date": "Q3 2026"},
                _gap_spec("Content"),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertIn('<p class="meta">Ops Team &middot; Q3 2026</p>', html)

    def test_no_meta_line_when_no_cover_slide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn('<p class="meta">', html)

    def test_no_meta_line_when_cover_lacks_presenter_and_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [{"pattern": "cover", "title": "Intro"}, _gap_spec("Content")]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn('<p class="meta">', html)

    def test_title_is_used_in_band_and_document_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "My Custom Title", "", "en")
            self.assertIn("<title>My Custom Title</title>", html)
            self.assertIn("<h1>My Custom Title</h1>", html)

    def test_subtitle_renders_from_manifest_description(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "A helpful subtitle.", "en")
            self.assertIn('<p class="subtitle">A helpful subtitle.</p>', html)

    def test_empty_subtitle_renders_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn('<p class="subtitle">', html)


class EscapingTests(unittest.TestCase):
    def test_script_tag_in_notes_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", notes="<script>alert(1)</script>")]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_script_tag_in_notes_list_item_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", notes=["<script>alert(2)</script>"])]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn("<script>alert(2)</script>", html)
            self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;", html)

    def test_script_tag_in_headline_toc_entry_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("<script>alert(3)</script>")]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn("<script>alert(3)</script>", html)
            self.assertIn("&lt;script&gt;alert(3)&lt;/script&gt;", html)

    def test_script_tag_in_title_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "<script>alert(4)</script>", "", "en")
            self.assertNotIn("<script>alert(4)</script>", html)
            self.assertIn("&lt;script&gt;alert(4)&lt;/script&gt;", html)

    def test_script_tag_in_subtitle_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "<script>alert(5)</script>", "en")
            self.assertNotIn("<script>alert(5)</script>", html)
            self.assertIn("&lt;script&gt;alert(5)&lt;/script&gt;", html)

    def test_script_tag_in_cover_presenter_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro", "presenter": "<script>alert(6)</script>"},
                _gap_spec("Content"),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertNotIn("<script>alert(6)</script>", html)
            self.assertIn("&lt;script&gt;alert(6)&lt;/script&gt;", html)


class LanguageModeTests(unittest.TestCase):
    def test_default_is_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertIn('<html lang="en">', html)
            self.assertNotIn('class="lang-ja"', html)

    def test_ja_sets_lang_attribute_and_body_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "ja")
            self.assertIn('<html lang="ja">', html)
            self.assertIn('<body class="lang-ja">', html)

    def test_unrecognized_lang_falls_back_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "fr")
            self.assertIn('<html lang="en">', html)

    def test_ja_line_height_and_palt_class_is_defined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "ja")
            self.assertIn("body.lang-ja { line-height: 1.9; font-feature-settings: 'palt'; }", html)


class DocumentAssemblyTests(unittest.TestCase):
    def test_output_is_a_single_self_contained_html_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertTrue(html.startswith("<!DOCTYPE html>"))
            self.assertIn("<style>", html)
            self.assertNotIn("@import", html)
            self.assertNotIn('rel="stylesheet"', html)
            self.assertNotIn("<link", html)

    def test_zero_external_requests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro", "presenter": "Ops", "date": "Q3"},
                _gap_spec("Content", notes="Some narration."),
                {"pattern": "end_cover", "title": "Bye"},
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = builder.build_article(spec_paths, "Test Deck", "A subtitle.", "en")
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)
            self.assertNotIn(" src=", html)

    def test_missing_slide_spec_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "does-not-exist.json"
            with self.assertRaises(builder.ArticleBuildError) as ctx:
                builder.build_article([missing], "Test Deck", "", "en")
            self.assertIn("does-not-exist.json", str(ctx.exception))

    def test_invalid_json_spec_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "broken.json"
            bad.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(builder.ArticleBuildError) as ctx:
                builder.build_article([bad], "Test Deck", "", "en")
            self.assertIn("broken.json", str(ctx.exception))

    def test_spec_the_renderer_rejects_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad-pattern.json"
            bad.write_text(json.dumps({"pattern": "not_a_real_pattern"}), encoding="utf-8")
            with self.assertRaises(builder.ArticleBuildError) as ctx:
                builder.build_article([bad], "Test Deck", "", "en")
            self.assertIn("bad-pattern.json", str(ctx.exception))

    def test_print_css_avoids_breaking_a_slide_figure_but_does_not_force_a_page_per_slide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = builder.build_article(spec_paths, "Test Deck", "", "en")
            self.assertIn(".slide-figure { break-inside: avoid; page-break-inside: avoid; }", html)
            # The title band legitimately forces one full navy print page
            # (matching build_html_report.py) -- but nothing forces a page
            # break between slides themselves: a slide-block never gets its
            # own break-after/page-break-after rule.
            self.assertNotIn(".slide-block { break-after", html)
            self.assertNotIn(".slide-block { page-break-after", html)
            self.assertNotIn(".slide-figure { break-after", html)
            self.assertNotIn(".slide-figure { page-break-after", html)


class TemplateAndDemoTests(unittest.TestCase):
    """Every shipped deck template and the flagship demo must build without error."""

    def test_all_deck_templates_build_without_error(self) -> None:
        decks_dir = ROOT / "templates" / "decks"
        manifest_paths = sorted(decks_dir.glob("*/deck.json"))
        self.assertTrue(manifest_paths, "expected at least one deck template")
        for manifest_path in manifest_paths:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            base = manifest_path.parent
            spec_paths = [base / p for p in manifest["slides"]]
            html = builder.build_article(spec_paths, manifest.get("title", "Untitled"), manifest.get("description", ""), "en")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertEqual(html.count('<section class="slide-block"'), len(manifest["slides"]))

    def test_demo_article_builds_and_has_zero_external_requests_and_seven_toc_entries(self) -> None:
        manifest_path = ROOT / "templates" / "decks" / "board-update" / "deck.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        base = manifest_path.parent
        spec_paths = [base / p for p in manifest["slides"]]
        html = builder.build_article(spec_paths, manifest["title"], manifest.get("description", ""), "en")
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertEqual(html.count('<section class="slide-block"'), 9)
        toc = re.search(r'<nav class="toc".*?</nav>', html, re.S).group(0)
        self.assertEqual(toc.count("<li>"), 7)  # cover + end_cover are chromeless, skipped

    def test_committed_demo_article_html_matches_a_fresh_build(self) -> None:
        manifest_path = ROOT / "templates" / "decks" / "board-update" / "deck.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        base = manifest_path.parent
        spec_paths = [base / p for p in manifest["slides"]]
        fresh = builder.build_article(spec_paths, manifest["title"], manifest.get("description", ""), "en")
        committed = (ROOT / "examples" / "demo-article.html").read_text(encoding="utf-8")
        self.assertEqual(
            fresh,
            committed,
            "stale demo article: regenerate examples/demo-article.html with "
            "scripts/build_html_article.py",
        )


class ArticleCliTests(unittest.TestCase):
    """True subprocess-level checks of the documented CLI contract."""

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_html_article.py"), *args],
            capture_output=True,
            text=True,
        )

    def test_cli_builds_the_board_update_demo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "article.html"
            result = self._run(
                "--manifest",
                str(ROOT / "templates" / "decks" / "board-update" / "deck.json"),
                "-o",
                str(output),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK: built article", result.stdout)
            self.assertTrue(output.exists())
            html = output.read_text(encoding="utf-8")
            self.assertTrue(html.startswith("<!DOCTYPE html>"))

    def test_cli_lang_flag_is_honored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "article.html"
            result = self._run(
                "--manifest",
                str(ROOT / "templates" / "decks" / "board-update" / "deck.json"),
                "-o",
                str(output),
                "--lang",
                "ja",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('<html lang="ja">', output.read_text(encoding="utf-8"))

    def test_cli_title_override_is_honored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "article.html"
            result = self._run(
                "--manifest",
                str(ROOT / "templates" / "decks" / "board-update" / "deck.json"),
                "-o",
                str(output),
                "--title",
                "CLI Smoke Test",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("<title>CLI Smoke Test</title>", output.read_text(encoding="utf-8"))

    def test_cli_missing_manifest_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                "--manifest", str(Path(tmp) / "does-not-exist.json"), "-o", str(Path(tmp) / "out.html")
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR", result.stderr)


if __name__ == "__main__":
    unittest.main()
