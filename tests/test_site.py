"""Static validation for the GitHub Pages site (docs/).

Parses docs/index.html (English) and docs/ja/index.html (Japanese) and asserts
the guarantees the repo brand makes: every local reference resolves, runtime
makes no external requests, required sections exist, and OGP meta is present.
"""

import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

REQUIRED_IDS = {"hero", "console", "pipeline", "start", "footer"}
EXAMPLES_IDS = {"live-deck", "patterns", "formats", "footer"}
REFERENCE_ATTRS = {"img": "src", "script": "src", "link": "href", "iframe": "src"}


def _local_path(ref: str) -> str:
    """Strip query/hash so Path.exists() checks the on-disk file."""
    return ref.split("?", 1)[0].split("#", 1)[0]


class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.refs = []  # (tag, value)
        self.metas = {}

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if "id" in attr:
            self.ids.add(attr["id"])
        if tag in REFERENCE_ATTRS and attr.get(REFERENCE_ATTRS[tag]):
            self.refs.append((tag, attr[REFERENCE_ATTRS[tag]]))
        if tag == "meta":
            key = attr.get("property") or attr.get("name")
            if key:
                self.metas[key] = attr.get("content", "")


class SiteChecks:
    INDEX: Path = None
    BASE: Path = None  # directory the page's relative URLs resolve against
    IDS = REQUIRED_IDS

    @classmethod
    def setUpClass(cls):
        cls.parser = IndexParser()
        cls.parser.feed(cls.INDEX.read_text(encoding="utf-8"))

    def test_required_sections_present(self):
        self.assertEqual(self.IDS - self.parser.ids, set())

    def test_local_references_resolve(self):
        missing = []
        for tag, ref in self.parser.refs:
            if ref.startswith(("http://", "https://", "#", "data:")):
                continue
            path = _local_path(ref)
            if not (self.BASE / path).resolve().exists():
                missing.append(f"{tag}: {ref}")
        self.assertEqual(missing, [])

    def test_no_external_runtime_requests(self):
        # <a> links may go anywhere; src/href of assets must be local.
        external = [
            f"{tag}: {ref}"
            for tag, ref in self.parser.refs
            if ref.startswith(("http://", "https://"))
        ]
        self.assertEqual(external, [])

    def test_og_meta_present(self):
        self.assertIn("og:image", self.parser.metas)
        self.assertIn("og:title", self.parser.metas)

    def test_og_image_exists(self):
        og_path = self.parser.metas.get("og:image", "")
        # Social crawlers require an absolute URL; map ours back to the committed asset.
        if og_path.startswith("https://"):
            suffix = "/site/og.png"
            self.assertTrue(
                og_path.endswith(suffix),
                f"og:image absolute URL must end with {suffix}: {og_path}",
            )
            local = DOCS / "site" / "og.png"
        else:
            local = (self.BASE / _local_path(og_path)).resolve()
        self.assertTrue(local.exists(), f"og:image missing: {og_path}")

    def test_og_image_is_absolute(self):
        og_path = self.parser.metas.get("og:image", "")
        self.assertTrue(
            og_path.startswith("https://"),
            f"og:image must be absolute for X/OG previews: {og_path}",
        )

    def test_iframe_targets_exist(self):
        for tag, ref in self.parser.refs:
            if tag == "iframe":
                path = _local_path(ref)
                self.assertTrue(
                    (self.BASE / path).resolve().exists(), f"iframe missing: {ref}"
                )


@unittest.skipUnless((DOCS / "index.html").exists(), "site not built yet")
class SiteTests(SiteChecks, unittest.TestCase):
    INDEX = DOCS / "index.html"
    BASE = DOCS


@unittest.skipUnless((DOCS / "ja" / "index.html").exists(), "ja page not built yet")
class JaSiteTests(SiteChecks, unittest.TestCase):
    INDEX = DOCS / "ja" / "index.html"
    BASE = DOCS / "ja"


TRY_IDS = {"try-intro", "try-key", "try-notes", "try-output", "try-privacy", "footer"}


@unittest.skipUnless((DOCS / "try" / "index.html").exists(), "try page not built yet")
class TrySiteTests(SiteChecks, unittest.TestCase):
    INDEX = DOCS / "try" / "index.html"
    BASE = DOCS / "try"
    IDS = TRY_IDS


@unittest.skipUnless((DOCS / "ja" / "try" / "index.html").exists(), "ja try page not built yet")
class JaTrySiteTests(SiteChecks, unittest.TestCase):
    INDEX = DOCS / "ja" / "try" / "index.html"
    BASE = DOCS / "ja" / "try"
    IDS = TRY_IDS


@unittest.skipUnless((DOCS / "examples" / "index.html").exists(), "examples page not built yet")
class ExamplesSiteTests(SiteChecks, unittest.TestCase):
    INDEX = DOCS / "examples" / "index.html"
    BASE = DOCS / "examples"
    IDS = EXAMPLES_IDS


@unittest.skipUnless(
    (DOCS / "ja" / "examples" / "index.html").exists(), "ja examples page not built yet"
)
class JaExamplesSiteTests(SiteChecks, unittest.TestCase):
    INDEX = DOCS / "ja" / "examples" / "index.html"
    BASE = DOCS / "ja" / "examples"
    IDS = EXAMPLES_IDS


if __name__ == "__main__":
    unittest.main()
