from __future__ import annotations

import importlib.util
import json
import tempfile
import textwrap
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


builder = load_module("build_html_report")


class FrontMatterTests(unittest.TestCase):
    def test_parses_recognized_keys(self) -> None:
        text = textwrap.dedent(
            """\
            ---
            title: FY26 growth review
            subtitle: Pre-read for the March board meeting
            author: Strategy Office
            date: March 2026
            classification: Confidential — illustrative
            lang: ja
            ---

            Body text.
            """
        )
        front, body = builder.parse_front_matter(text)
        self.assertEqual(front["title"], "FY26 growth review")
        self.assertEqual(front["subtitle"], "Pre-read for the March board meeting")
        self.assertEqual(front["author"], "Strategy Office")
        self.assertEqual(front["date"], "March 2026")
        self.assertEqual(front["classification"], "Confidential — illustrative")
        self.assertEqual(front["lang"], "ja")
        self.assertEqual(body.strip(), "Body text.")

    def test_missing_front_matter_returns_whole_text_as_body(self) -> None:
        text = "## Just a heading\n\nSome text.\n"
        front, body = builder.parse_front_matter(text)
        self.assertEqual(front, {})
        self.assertEqual(body, text)

    def test_unterminated_fence_never_crashes_falls_back_to_body(self) -> None:
        # A first line of "---" with no closing fence is not front matter --
        # the whole document (including that line) becomes the body instead
        # of raising, so a stray leading hr never breaks the build.
        text = "---\ntitle: Oops\n\nNo closing fence anywhere in this file.\n"
        front, body = builder.parse_front_matter(text)
        self.assertEqual(front, {})
        self.assertEqual(body, text)

    def test_quoted_values_are_unwrapped(self) -> None:
        text = '---\ntitle: "Quoted title"\n---\nBody\n'
        front, _ = builder.parse_front_matter(text)
        self.assertEqual(front["title"], "Quoted title")

    def test_unrecognized_keys_are_kept_but_ignored_by_the_builder(self) -> None:
        text = "---\ntitle: Doc\nrandom_key: whatever\n---\nBody.\n"
        front, _ = builder.parse_front_matter(text)
        self.assertEqual(front["random_key"], "whatever")
        html = builder.build_report(text, ROOT)
        self.assertNotIn("random_key", html)
        self.assertNotIn("whatever", html)

    def test_missing_title_falls_back_without_crashing(self) -> None:
        html = builder.build_report("Body only, no front matter at all.\n", ROOT)
        self.assertIn("<h1>Untitled</h1>", html)


class MarkdownSubsetTests(unittest.TestCase):
    def build(self, body: str) -> str:
        return builder.build_report(body, ROOT)

    def test_headings_are_numbered_and_listed_in_toc(self) -> None:
        html = self.build("## First section\n\nBody one.\n\n## Second section\n\nBody two.\n")
        self.assertIn('<h2 id="first-section">1. First section</h2>', html)
        self.assertIn('<h2 id="second-section">2. Second section</h2>', html)
        self.assertIn('<nav class="toc"', html)
        self.assertIn('<a href="#first-section">1. First section</a>', html)
        self.assertIn('<a href="#second-section">2. Second section</a>', html)

    def test_h3_is_unnumbered_and_toc_omitted_without_any_h2(self) -> None:
        html = self.build("### A subheading\n\nBody.\n")
        self.assertIn("<h3>A subheading</h3>", html)
        self.assertNotIn('<nav class="toc"', html)

    def test_duplicate_headings_get_unique_slugs(self) -> None:
        html = self.build("## Repeat\n\nOne.\n\n## Repeat\n\nTwo.\n")
        self.assertIn('id="repeat"', html)
        self.assertIn('id="repeat-2"', html)

    def test_unordered_list_with_one_nested_level(self) -> None:
        html = self.build("- top\n  - nested\n- top two\n")
        self.assertIn(
            "<ul><li>top<ul><li>nested</li></ul></li><li>top two</li></ul>", html
        )

    def test_ordered_list_uses_first_number_as_start(self) -> None:
        html = self.build("5. fifth\n6. sixth\n")
        self.assertIn('<ol start="5">', html)
        self.assertIn("<li>fifth</li><li>sixth</li>", html)

    def test_ordered_list_starting_at_one_has_no_start_attribute(self) -> None:
        html = self.build("1. first\n2. second\n")
        self.assertIn("<ol><li>first</li>", html)
        self.assertNotIn("start=", html)

    def test_inline_bold_italic_code_link(self) -> None:
        html = self.build(
            "A **bold** word, an *italic* word, `some code`, and a [link](https://example.com/x).\n"
        )
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)
        self.assertIn("<code>some code</code>", html)
        self.assertIn('<a href="https://example.com/x">link</a>', html)

    def test_code_span_content_is_immune_to_bold_italic_processing(self) -> None:
        html = self.build("Some `a * b * c` code with asterisks inside.\n")
        self.assertIn("<code>a * b * c</code>", html)
        self.assertNotIn("<em>", html)

    def test_blockquote_joins_lines(self) -> None:
        html = self.build("> A quoted line\n> continues here\n")
        self.assertIn("<blockquote><p>A quoted line continues here</p></blockquote>", html)

    def test_horizontal_rule(self) -> None:
        html = self.build("Para one.\n\n---\n\nPara two.\n")
        self.assertIn("<hr>", html)

    def test_gfm_table_with_alignment(self) -> None:
        html = self.build("| Name | Score |\n| --- | ---: |\n| Alpha | 4.2 |\n| Beta | 3.9 |\n")
        self.assertIn("<th>Name</th>", html)
        self.assertIn('<th style="text-align:right">Score</th>', html)
        self.assertIn('<td style="text-align:right">4.2</td>', html)
        self.assertIn("<td>Alpha</td>", html)

    def test_unrecognized_syntax_passes_through_as_escaped_text_never_crashes(self) -> None:
        html = self.build(
            "#### Not a real heading (4 hashes is outside the subset)\n\n"
            "Some ~~strikethrough~~ that is not in the subset either.\n"
        )
        self.assertIn("#### Not a real heading", html)
        self.assertIn("~~strikethrough~~", html)

    def test_image_syntax_with_an_unrecognized_scheme_is_not_an_exhibit(self) -> None:
        # Only spec: and svg: are recognized exhibit schemes. Anything else
        # is outside the subset, so it must never raise -- here it falls
        # through to plain link handling with a literal leading "!".
        html = self.build("![Not an exhibit](http://example.com/x.png)\n")
        self.assertIn('<p>!<a href="http://example.com/x.png">Not an exhibit</a></p>', html)


class EscapingTests(unittest.TestCase):
    def test_script_tag_in_paragraph_stays_escaped(self) -> None:
        html = builder.build_report("A line with <script>alert(1)</script> inside.\n", ROOT)
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_script_tag_in_heading_stays_escaped(self) -> None:
        html = builder.build_report("## <script>alert(2)</script>\n\nBody.\n", ROOT)
        self.assertNotIn("<script>alert(2)</script>", html)
        self.assertIn("&lt;script&gt;alert(2)&lt;/script&gt;", html)

    def test_script_tag_in_table_cell_stays_escaped(self) -> None:
        html = builder.build_report("| A |\n| --- |\n| <script>alert(3)</script> |\n", ROOT)
        self.assertNotIn("<script>alert(3)</script>", html)
        self.assertIn("&lt;script&gt;alert(3)&lt;/script&gt;", html)

    def test_script_tag_in_list_item_stays_escaped(self) -> None:
        html = builder.build_report("- <script>alert(5)</script>\n", ROOT)
        self.assertNotIn("<script>alert(5)</script>", html)
        self.assertIn("&lt;script&gt;alert(5)&lt;/script&gt;", html)

    def test_front_matter_title_is_escaped(self) -> None:
        text = "---\ntitle: <script>alert(4)</script>\n---\nBody.\n"
        html = builder.build_report(text, ROOT)
        self.assertNotIn("<script>alert(4)</script>", html)
        self.assertIn("&lt;script&gt;alert(4)&lt;/script&gt;", html)

    def test_javascript_uri_link_is_dropped(self) -> None:
        html = builder.build_report("Click [here](javascript:alert(6)) now.\n", ROOT)
        self.assertNotIn("javascript:", html)
        self.assertNotIn('<a href="javascript', html)
        self.assertIn("here", html)  # label survives as plain text

    def test_javascript_uri_link_is_dropped_case_insensitively(self) -> None:
        html = builder.build_report("Click [here](JaVaScRiPt:alert(7)) now.\n", ROOT)
        self.assertNotIn("avascript:", html)
        self.assertIn("here", html)

    def test_data_and_vbscript_uri_links_are_dropped(self) -> None:
        text = "[a](data:text/html;base64,PHM+) and [b](vbscript:msgbox(1))\n"
        html = builder.build_report(text, ROOT)
        self.assertNotIn('href="data:', html)
        self.assertNotIn('href="vbscript:', html)

    def test_control_character_scheme_smuggling_is_dropped(self) -> None:
        html = builder.build_report("[x](java\x01script:alert(8))\n", ROOT)
        self.assertNotIn("script:alert", html)

    def test_safe_link_schemes_are_kept(self) -> None:
        text = (
            "[h](https://example.com/a) [m](mailto:a@example.com) "
            "[f](#section-1) [r](../other/page.html)\n"
        )
        html = builder.build_report(text, ROOT)
        self.assertIn('<a href="https://example.com/a">h</a>', html)
        self.assertIn('<a href="mailto:a@example.com">m</a>', html)
        self.assertIn('<a href="#section-1">f</a>', html)
        self.assertIn('<a href="../other/page.html">r</a>', html)

    def test_colon_before_first_slash_is_dropped(self) -> None:
        # A colon in the first segment is how a browser would discover a
        # scheme the allowlist did not match — whether or not it parses as
        # a syntactically valid scheme on our side.
        html = builder.build_report("[y](foo.bar:baz/qux)\n", ROOT)
        self.assertNotIn('href="foo.bar:baz/qux"', html)
        html2 = builder.build_report("[z](1:2/path)\n", ROOT)
        self.assertNotIn('href="1:2/path"', html2)
        # ...but a colon later in the path is inert and stays.
        html3 = builder.build_report("[k](/docs/a:b)\n", ROOT)
        self.assertIn('<a href="/docs/a:b">k</a>', html3)


class ExhibitTests(unittest.TestCase):
    def test_spec_exhibits_render_and_number_sequentially(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = {
                "pattern": "gap",
                "headline": "Capacity trails demand",
                "items": [
                    {"label": "Demand", "value": 100, "emphasis": True},
                    {"label": "Capacity", "value": 60},
                ],
            }
            (root / "chart.json").write_text(json.dumps(spec), encoding="utf-8")
            body = (
                "## Section\n\n"
                "![First chart](spec:chart.json)\n\n"
                "Some text in between.\n\n"
                "![Second chart](spec:chart.json)\n"
            )
            html = builder.build_report(body, root)
            self.assertIn("Exhibit 1 — First chart", html)
            self.assertIn("Exhibit 2 — Second chart", html)
            self.assertEqual(html.count('<figure class="exhibit">'), 2)
            self.assertIn("Capacity trails demand", html)  # the rendered slide's own headline

    def test_svg_exhibit_embeds_existing_file_and_strips_xmlns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg_content = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
                "<rect width=\"10\" height=\"10\"/></svg>\n"
            )
            (root / "chart.svg").write_text(svg_content, encoding="utf-8")
            html = builder.build_report("![An existing chart](svg:chart.svg)\n", root)
            self.assertIn("Exhibit 1 — An existing chart", html)
            self.assertNotIn("http://www.w3.org/2000/svg", html)
            self.assertNotIn("<?xml", html)
            self.assertIn("<svg", html)

    def test_exhibit_caption_is_escaped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            svg_content = '<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
            (root / "chart.svg").write_text(svg_content, encoding="utf-8")
            html = builder.build_report("![<script>alert(6)</script>](svg:chart.svg)\n", root)
            self.assertNotIn("<script>alert(6)</script>", html)
            self.assertIn("&lt;script&gt;alert(6)&lt;/script&gt;", html)

    def test_missing_exhibit_reference_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(builder.ReportBuildError) as ctx:
                builder.build_report("![Missing](spec:does-not-exist.json)\n", root)
            self.assertIn("does-not-exist.json", str(ctx.exception))

    def test_invalid_json_exhibit_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "broken.json").write_text("{not valid json", encoding="utf-8")
            with self.assertRaises(builder.ReportBuildError) as ctx:
                builder.build_report("![Broken](spec:broken.json)\n", root)
            self.assertIn("broken.json", str(ctx.exception))

    def test_spec_the_renderer_rejects_raises_naming_the_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad-pattern.json").write_text(
                json.dumps({"pattern": "not_a_real_pattern"}), encoding="utf-8"
            )
            with self.assertRaises(builder.ReportBuildError) as ctx:
                builder.build_report("![Bad](spec:bad-pattern.json)\n", root)
            self.assertIn("bad-pattern.json", str(ctx.exception))

    def test_svg_file_missing_svg_tag_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "not-svg.svg").write_text("just text, not an svg file", encoding="utf-8")
            with self.assertRaises(builder.ReportBuildError):
                builder.build_report("![Not svg](svg:not-svg.svg)\n", root)

    def test_exhibit_path_resolves_relative_to_markdown_file_not_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = root / "nested"
            sub.mkdir()
            svg_content = '<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
            (sub / "chart.svg").write_text(svg_content, encoding="utf-8")
            html = builder.build_report("![Nested chart](svg:chart.svg)\n", sub)
            self.assertIn("Exhibit 1 — Nested chart", html)


class LanguageModeTests(unittest.TestCase):
    def test_default_is_english(self) -> None:
        html = builder.build_report("Body.\n", ROOT)
        self.assertIn('<html lang="en">', html)
        self.assertNotIn('class="lang-ja"', html)

    def test_front_matter_lang_ja(self) -> None:
        html = builder.build_report("---\nlang: ja\n---\nBody.\n", ROOT)
        self.assertIn('<html lang="ja">', html)
        self.assertIn('<body class="lang-ja">', html)

    def test_cli_lang_override_wins_over_front_matter(self) -> None:
        html = builder.build_report("---\nlang: ja\n---\nBody.\n", ROOT, lang_override="en")
        self.assertIn('<html lang="en">', html)
        self.assertNotIn('class="lang-ja"', html)

    def test_unrecognized_lang_value_falls_back_to_english(self) -> None:
        html = builder.build_report("---\nlang: fr\n---\nBody.\n", ROOT)
        self.assertIn('<html lang="en">', html)


class DocumentAssemblyTests(unittest.TestCase):
    def test_zero_external_requests_when_document_has_no_links(self) -> None:
        html = builder.build_report(
            "## Section\n\nJust text, no links, no exhibits.\n", ROOT
        )
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_classification_and_meta_line_render(self) -> None:
        text = textwrap.dedent(
            """\
            ---
            title: Doc title
            subtitle: Doc subtitle
            author: Someone
            date: March 2026
            classification: Confidential
            ---

            Body.
            """
        )
        html = builder.build_report(text, ROOT)
        self.assertIn('<h1>Doc title</h1>', html)
        self.assertIn('<p class="subtitle">Doc subtitle</p>', html)
        self.assertIn("Someone", html)
        self.assertIn("March 2026", html)
        self.assertIn("CONFIDENTIAL", html)

    def test_output_is_a_single_self_contained_html_document(self) -> None:
        html = builder.build_report("## Section\n\nBody.\n", ROOT)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("<style>", html)
        self.assertNotIn("@import", html)
        self.assertNotIn('rel="stylesheet"', html)
        self.assertNotIn("<link", html)


class TemplateAndDemoTests(unittest.TestCase):
    """Every shipped template and the flagship demo must build without error."""

    def test_all_report_templates_build_without_error(self) -> None:
        templates_dir = ROOT / "templates" / "reports"
        template_paths = sorted(templates_dir.glob("*.md"))
        self.assertTrue(template_paths, "expected at least one report template")
        for path in template_paths:
            html = builder.build_report(path.read_text(encoding="utf-8"), path.parent)
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("<h1>", html)

    def test_demo_report_builds_and_has_zero_external_requests(self) -> None:
        demo_path = ROOT / "examples" / "demo-report.md"
        html = builder.build_report(demo_path.read_text(encoding="utf-8"), demo_path.parent)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn("Exhibit 1", html)
        self.assertIn("Exhibit 2", html)

    def test_committed_demo_report_html_matches_a_fresh_build(self) -> None:
        demo_path = ROOT / "examples" / "demo-report.md"
        fresh = builder.build_report(demo_path.read_text(encoding="utf-8"), demo_path.parent)
        committed = (ROOT / "examples" / "demo-report.html").read_text(encoding="utf-8")
        self.assertEqual(
            fresh,
            committed,
            "stale demo report: regenerate examples/demo-report.html with "
            "scripts/build_html_report.py",
        )


if __name__ == "__main__":
    unittest.main()
