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


def _write_manifest(
    root: Path,
    slides: list[dict],
    title: str = "Test Deck",
    description: str = "",
    series: str = "",
    lead: str = "",
) -> tuple[list[Path], dict]:
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
    if series:
        manifest["series"] = series
    if lead:
        manifest["lead"] = lead
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


def _build(spec_paths, title="Test Deck", lead="", lang="en", series=""):
    return builder.build_article(spec_paths, title, lead, lang, series=series)


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


class NormalizeRefsTests(unittest.TestCase):
    def test_well_formed_refs_pass_through(self) -> None:
        refs = [{"label": "Example", "url": "https://example.com"}]
        self.assertEqual(
            builder._normalize_refs(refs),
            [{"label": "Example", "url": "https://example.com"}],
        )

    def test_missing_label_falls_back_to_url(self) -> None:
        refs = [{"url": "https://example.com"}]
        self.assertEqual(builder._normalize_refs(refs)[0]["label"], "https://example.com")

    def test_non_list_returns_empty(self) -> None:
        self.assertEqual(builder._normalize_refs("not a list"), [])
        self.assertEqual(builder._normalize_refs(None), [])

    def test_non_dict_items_are_skipped(self) -> None:
        refs = ["not a dict", {"label": "Real", "url": "https://example.com"}]
        self.assertEqual(len(builder._normalize_refs(refs)), 1)

    def test_items_missing_url_are_skipped(self) -> None:
        refs = [{"label": "No URL"}, {"label": "Has URL", "url": "https://example.com"}]
        self.assertEqual(len(builder._normalize_refs(refs)), 1)

    def test_blank_url_is_skipped(self) -> None:
        refs = [{"label": "Blank", "url": "   "}]
        self.assertEqual(builder._normalize_refs(refs), [])


class SharedContractTests(unittest.TestCase):
    """The shared notes/label/refs contract: the SVG renderer must ignore
    all three entirely, for every shipped board-update spec (not just a
    synthetic one)."""

    def test_notes_do_not_change_rendered_svg_for_every_board_update_spec(self) -> None:
        specs_dir = ROOT / "templates" / "decks" / "board-update" / "specs"
        spec_paths = sorted(specs_dir.glob("*.json"))
        self.assertTrue(spec_paths, "expected board-update specs to exist")
        for path in spec_paths:
            with_notes = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("notes", with_notes, f"{path.name} is missing its demo notes field")
            without_extras = copy.deepcopy(with_notes)
            without_extras.pop("notes", None)
            without_extras.pop("label", None)
            without_extras.pop("refs", None)
            self.assertEqual(
                renderer.render(with_notes),
                renderer.render(without_extras),
                f"notes/label/refs changed the rendered SVG for {path.name}",
            )

    def test_notes_label_refs_do_not_change_rendered_svg_for_a_synthetic_spec(self) -> None:
        spec = _gap_spec("Capacity trails demand")
        without_extras = renderer.render(spec)
        spec["notes"] = ["A paragraph.", "Another one."]
        spec["label"] = "A Label"
        spec["refs"] = [{"label": "Ref", "url": "https://example.com"}]
        with_extras = renderer.render(spec)
        self.assertEqual(with_extras, without_extras)


class ManifestAndOrderingTests(unittest.TestCase):
    def test_slides_render_in_manifest_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(
                root,
                [_gap_spec("First finding"), _gap_spec("Second finding"), _gap_spec("Third finding")],
            )
            html = _build(spec_paths)
            first = html.index("First finding")
            second = html.index("Second finding")
            third = html.index("Third finding")
            self.assertTrue(first < second < third)

    def test_deck_shows_one_article_per_slide_including_chromeless(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro"},
                _gap_spec("Content slide"),
                {"pattern": "end_cover", "title": "Thank you"},
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertEqual(html.count('<article class="slide-block"'), 3)
            self.assertEqual(html.count("<svg"), 3)

    def test_slide_anchor_ids_are_sequential_and_zero_padded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("First"), _gap_spec("Second")])
            html = _build(spec_paths)
            self.assertIn('id="slide-01"', html)
            self.assertIn('id="slide-02"', html)


class NoNotesTests(unittest.TestCase):
    def test_slide_without_notes_still_renders_frame_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("No narration here")]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertIn("No narration here", html)  # the slide itself still renders
            self.assertNotIn('<div class="notes">', html)

    def test_chromeless_slide_without_notes_still_gets_a_section(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [{"pattern": "end_cover", "title": "Thank you"}]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertEqual(html.count('<article class="slide-block"'), 1)
            self.assertNotIn('<div class="notes">', html)

    def test_mixed_deck_only_notes_bearing_slides_get_a_notes_div(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                _gap_spec("Has no notes"),
                _gap_spec("Has notes", notes="A single paragraph of narration."),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertEqual(html.count('<div class="notes">'), 1)
            self.assertIn("A single paragraph of narration.", html)


class NotesRenderingTests(unittest.TestCase):
    def test_notes_list_renders_one_p_per_paragraph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Findings", notes=["Paragraph one.", "Paragraph two."])]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            notes_div = re.search(r'<div class="notes">(.*?)</div>', html, re.S).group(1)
            self.assertEqual(notes_div.count("<p>"), 2)
            self.assertIn("<p>Paragraph one.</p>", notes_div)
            self.assertIn("<p>Paragraph two.</p>", notes_div)

    def test_notes_string_splits_into_paragraphs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Findings", notes="First para.\n\nSecond para.")]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertIn('class="notes"', html)
            self.assertIn("<p>First para.</p>", html)
            self.assertIn("<p>Second para.</p>", html)


class LabelAndHeadingTests(unittest.TestCase):
    def test_label_renders_next_to_the_slide_number_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content", label="Growth Bridge")])
            html = _build(spec_paths)
            self.assertIn('<span class="lbl">Growth Bridge</span>', html)

    def test_no_label_span_when_field_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn('<span class="lbl">', html)

    def test_content_slide_always_gets_an_h2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("A distinct message")])
            html = _build(spec_paths)
            self.assertIn("<h2>A distinct message</h2>", html)

    def test_chromeless_slide_with_a_title_gets_an_h2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [{"pattern": "end_cover", "title": "Thank you"}]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertIn("<h2>Thank you</h2>", html)

    def test_chromeless_slide_with_no_headline_or_title_omits_the_h2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [{"pattern": "end_cover"}]  # renderer defaults its own SVG title, article does not
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            article = re.search(r'<article class="slide-block".*?</article>', html, re.S).group(0)
            self.assertNotIn("<h2>", article)


class RefsTests(unittest.TestCase):
    def test_safe_scheme_ref_renders_as_a_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", refs=[{"label": "Docs", "url": "https://example.com/docs"}])]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertIn(
                '<a href="https://example.com/docs" target="_blank" rel="noopener">Docs</a>', html
            )

    def test_unsafe_scheme_ref_drops_to_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                _gap_spec(
                    "Content",
                    refs=[{"label": "Malicious", "url": "javascript:alert(1)"}],
                )
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("javascript:alert(1)", html)
            self.assertIn("<li>Malicious</li>", html)

    def test_mailto_scheme_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", refs=[{"label": "Contact", "url": "mailto:ir@example.com"}])]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertIn('<a href="mailto:ir@example.com"', html)

    def test_no_refs_aside_when_field_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn('<aside class="slide-refs">', html)

    def test_refs_label_is_localized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", refs=[{"label": "Docs", "url": "https://example.com"}])]
            spec_paths, _ = _write_manifest(root, slides)
            html_en = _build(spec_paths, lang="en")
            html_ja = _build(spec_paths, lang="ja")
            self.assertIn('<p class="slide-refs-label">Links</p>', html_en)
            self.assertIn('<p class="slide-refs-label">関連リンク</p>', html_ja)

    def test_aggregated_links_section_lists_every_ref_once_deduped_by_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                _gap_spec(
                    "First",
                    refs=[
                        {"label": "Shared", "url": "https://example.com/shared"},
                        {"label": "Only on first", "url": "https://example.com/first"},
                    ],
                ),
                _gap_spec(
                    "Second",
                    refs=[{"label": "Shared again", "url": "https://example.com/shared"}],
                ),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            bibliography = re.search(r'<section class="bibliography".*?</section>', html, re.S).group(0)
            self.assertEqual(bibliography.count("https://example.com/shared"), 1)
            self.assertIn("https://example.com/first", bibliography)
            self.assertIn(">All links<", html)

    def test_no_bibliography_section_when_no_slide_has_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn('<section class="bibliography"', html)

    def test_bibliography_title_is_localized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", refs=[{"label": "Docs", "url": "https://example.com"}])]
            spec_paths, _ = _write_manifest(root, slides)
            html_ja = _build(spec_paths, lang="ja")
            self.assertIn(">参考リンク一覧<", html_ja)


class NoTocTests(unittest.TestCase):
    """v2.4 removes the sticky "Contents" TOC entirely -- the article is a
    single linear scroll (see the v2.4.0 addendum)."""

    def test_no_toc_nav_in_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro"},
                _gap_spec("First finding"),
                _gap_spec("Second finding"),
                {"pattern": "end_cover", "title": "Thank you"},
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn('<nav', html)
            self.assertNotIn('class="toc"', html)
            self.assertNotIn(">Contents<", html)

    def test_no_toc_script_ever_emitted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn("<script", html)


class HeroTests(unittest.TestCase):
    def test_hero_h1_uses_title(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, title="My Custom Title")
            self.assertIn("<title>My Custom Title</title>", html)
            self.assertIn('<header class="hero">', html)
            self.assertIn("<h1>My Custom Title</h1>", html)

    def test_kicker_renders_from_series_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, series="Board Reporting Series")
            self.assertIn('<p class="kicker">Board Reporting Series</p>', html)

    def test_no_kicker_when_series_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn('class="kicker"', html)

    def test_lead_paragraph_renders_from_lead_argument(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, lead="A helpful lead paragraph.")
            self.assertIn('<p class="lead">A helpful lead paragraph.</p>', html)

    def test_empty_lead_renders_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn('class="lead"', html)

    def test_slide_count_chip_reports_total_slides(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(
                root, [_gap_spec("First"), _gap_spec("Second"), _gap_spec("Third")]
            )
            html = _build(spec_paths)
            self.assertIn('<span class="chip">3 slides</span>', html)

    def test_slide_count_chip_is_localized_for_japanese(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, lang="ja")
            self.assertIn('<span class="chip">全 1 スライド</span>', html)

    def test_hero_chips_built_from_cover_presenter_and_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro", "presenter": "Ops Team", "date": "Q3 2026"},
                _gap_spec("Content"),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertIn('<span class="chip">Author: Ops Team</span>', html)
            self.assertIn('<span class="chip">Q3 2026</span>', html)

    def test_no_author_or_date_chip_when_no_cover_slide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn("Author:", html)

    def test_no_author_or_date_chip_when_cover_lacks_them(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [{"pattern": "cover", "title": "Intro"}, _gap_spec("Content")]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("Author:", html)

    def test_no_navy_title_band_in_hero_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertNotIn("title-band", html)

    def test_footer_names_the_title_and_the_skill_with_no_version_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, title="Test Deck")
            footer = re.search(r"<footer>.*?</footer>", html, re.S).group(0)
            self.assertIn("Test Deck", footer)
            self.assertIn("Strategy Consulting Visualization", footer)
            self.assertNotRegex(footer, r"\d+\.\d+\.\d+")


class EscapingTests(unittest.TestCase):
    def test_script_tag_in_notes_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", notes="<script>alert(1)</script>")]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("<script>alert(1)</script>", html)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_script_tag_in_notes_list_item_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", notes=["<script>alert(2)</script>"])]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("<script>alert(2)</script>", html)
            self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;", html)

    def test_script_tag_in_headline_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("<script>alert(3)</script>")]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("<script>alert(3)</script>", html)
            self.assertIn("&lt;script&gt;alert(3)&lt;/script&gt;", html)

    def test_script_tag_in_title_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, title="<script>alert(4)</script>")
            self.assertNotIn("<script>alert(4)</script>", html)
            self.assertIn("&lt;script&gt;alert(4)&lt;/script&gt;", html)

    def test_script_tag_in_lead_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, lead="<script>alert(5)</script>")
            self.assertNotIn("<script>alert(5)</script>", html)
            self.assertIn("&lt;script&gt;alert(5)&lt;/script&gt;", html)

    def test_script_tag_in_series_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, series="<script>alert(6)</script>")
            self.assertNotIn("<script>alert(6)</script>", html)
            self.assertIn("&lt;script&gt;alert(6)&lt;/script&gt;", html)

    def test_script_tag_in_cover_presenter_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro", "presenter": "<script>alert(7)</script>"},
                _gap_spec("Content"),
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("<script>alert(7)</script>", html)
            self.assertIn("&lt;script&gt;alert(7)&lt;/script&gt;", html)

    def test_script_tag_in_label_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", label="<script>alert(8)</script>")]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("<script>alert(8)</script>", html)
            self.assertIn("&lt;script&gt;alert(8)&lt;/script&gt;", html)

    def test_script_tag_in_ref_label_stays_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                _gap_spec(
                    "Content",
                    refs=[{"label": "<script>alert(9)</script>", "url": "https://example.com"}],
                )
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn("<script>alert(9)</script>", html)
            self.assertIn("&lt;script&gt;alert(9)&lt;/script&gt;", html)

    def test_quote_in_ref_url_stays_escaped_in_href_attribute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                _gap_spec(
                    "Content",
                    refs=[{"label": "Odd URL", "url": 'https://example.com/?q="x"'}],
                )
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            self.assertNotIn('href="https://example.com/?q="x""', html)
            self.assertIn("&quot;x&quot;", html)


class LanguageModeTests(unittest.TestCase):
    def test_default_is_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertIn('<html lang="en">', html)
            self.assertNotIn('class="lang-ja"', html)

    def test_ja_sets_lang_attribute_and_body_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, lang="ja")
            self.assertIn('<html lang="ja">', html)
            self.assertIn('<body class="lang-ja">', html)

    def test_unrecognized_lang_falls_back_to_english(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, lang="fr")
            self.assertIn('<html lang="en">', html)

    def test_ja_line_height_and_palt_class_is_defined(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths, lang="ja")
            self.assertIn("body.lang-ja { line-height: 1.9; font-feature-settings: 'palt'; }", html)


class DocumentAssemblyTests(unittest.TestCase):
    def test_output_is_a_single_self_contained_html_document(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertTrue(html.startswith("<!DOCTYPE html>"))
            self.assertIn("<style>", html)
            self.assertNotIn("@import", html)
            self.assertNotIn('rel="stylesheet"', html)
            self.assertNotIn("<link", html)
            self.assertNotIn("<script", html)

    def test_reading_column_measure_is_680px(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertIn(".wrap { max-width: 680px", html)

    def test_zero_external_requests_when_no_refs_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [
                {"pattern": "cover", "title": "Intro", "presenter": "Ops", "date": "Q3"},
                _gap_spec("Content", notes="Some narration."),
                {"pattern": "end_cover", "title": "Bye"},
            ]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths, lead="A lead.")
            self.assertNotIn("http://", html)
            self.assertNotIn("https://", html)
            self.assertNotIn(" src=", html)
            self.assertNotIn("<script", html)

    def test_ref_href_is_the_only_external_reference_when_refs_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            slides = [_gap_spec("Content", refs=[{"label": "Docs", "url": "https://example.com/docs"}])]
            spec_paths, _ = _write_manifest(root, slides)
            html = _build(spec_paths)
            # The one legitimate exception: a target=_blank ref link's own href.
            self.assertIn('href="https://example.com/docs"', html)
            self.assertNotIn("<link", html)
            self.assertNotIn("<script", html)
            self.assertNotIn(" src=", html)

    def test_missing_slide_spec_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "does-not-exist.json"
            with self.assertRaises(builder.ArticleBuildError) as ctx:
                _build([missing])
            self.assertIn("does-not-exist.json", str(ctx.exception))

    def test_invalid_json_spec_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "broken.json"
            bad.write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(builder.ArticleBuildError) as ctx:
                _build([bad])
            self.assertIn("broken.json", str(ctx.exception))

    def test_spec_the_renderer_rejects_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bad = root / "bad-pattern.json"
            bad.write_text(json.dumps({"pattern": "not_a_real_pattern"}), encoding="utf-8")
            with self.assertRaises(builder.ArticleBuildError) as ctx:
                _build([bad])
            self.assertIn("bad-pattern.json", str(ctx.exception))

    def test_print_css_avoids_breaking_a_slide_block_with_no_forced_page_per_slide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec_paths, _ = _write_manifest(root, [_gap_spec("Content")])
            html = _build(spec_paths)
            self.assertIn(".slide-block { break-inside: avoid; page-break-inside: avoid; }", html)
            self.assertNotIn(".slide-block { break-after", html)
            self.assertNotIn(".slide-block { page-break-after", html)
            self.assertIn("size: A4 portrait", html)


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
            lead = manifest.get("lead") or manifest.get("description", "")
            series = manifest.get("series", "")
            html = builder.build_article(
                spec_paths, manifest.get("title", "Untitled"), lead, "en", series=series
            )
            self.assertIn("<!DOCTYPE html>", html)
            self.assertEqual(html.count('<article class="slide-block"'), len(manifest["slides"]))

    def test_demo_article_builds_with_hero_labels_and_links(self) -> None:
        manifest_path = ROOT / "templates" / "decks" / "board-update" / "deck.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        base = manifest_path.parent
        spec_paths = [base / p for p in manifest["slides"]]
        lead = manifest.get("lead") or manifest.get("description", "")
        html = builder.build_article(
            spec_paths, manifest["title"], lead, "en", series=manifest.get("series", "")
        )
        self.assertEqual(html.count('<article class="slide-block"'), 9)
        self.assertIn('<p class="kicker">Board Reporting Series</p>', html)
        self.assertIn('<span class="lbl">Growth Bridge</span>', html)
        self.assertIn('<section class="bibliography"', html)
        # Refs were added to exactly two slides in the demo content.
        self.assertEqual(html.count('<aside class="slide-refs">'), 2)

    def test_committed_demo_article_html_matches_a_fresh_build(self) -> None:
        manifest_path = ROOT / "templates" / "decks" / "board-update" / "deck.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        base = manifest_path.parent
        spec_paths = [base / p for p in manifest["slides"]]
        lead = manifest.get("lead") or manifest.get("description", "")
        fresh = builder.build_article(
            spec_paths, manifest["title"], lead, "en", series=manifest.get("series", "")
        )
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
            self.assertIn('<p class="kicker">Board Reporting Series</p>', html)

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
