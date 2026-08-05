"""Static validation for the GitHub Pages site (docs/).

Parses docs/index.html and asserts the guarantees the repo brand makes:
every local reference resolves, runtime makes no external requests,
required sections exist, and OGP meta is present.
"""

import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
INDEX = DOCS / "index.html"

REQUIRED_IDS = {"hero", "live-deck", "pipeline", "gallery", "cjk", "modes", "roast", "start", "footer"}
REFERENCE_ATTRS = {"img": "src", "script": "src", "link": "href", "iframe": "src"}


class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.refs = []  # (tag, value)
        self.metas = {}
        self.importmap_srcs = []

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


@unittest.skipUnless(INDEX.exists(), "site not built yet")
class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = IndexParser()
        cls.parser.feed(INDEX.read_text(encoding="utf-8"))

    def test_required_sections_present(self):
        self.assertEqual(REQUIRED_IDS - self.parser.ids, set())

    def test_local_references_resolve(self):
        missing = []
        for tag, ref in self.parser.refs:
            if ref.startswith(("http://", "https://", "#", "data:")):
                continue
            if not (DOCS / ref).resolve().exists():
                missing.append(f"{tag}: {ref}")
        self.assertEqual(missing, [])

    def test_no_external_runtime_requests(self):
        # <a> links may go anywhere; src/href of assets must be local
        # (the only exception: the og:image meta is a path, and <link> stylesheets are local).
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
        self.assertTrue((DOCS / og_path).resolve().exists(), f"og:image missing: {og_path}")

    def test_three_vendored(self):
        self.assertTrue((DOCS / "site" / "vendor" / "three.module.js").exists())

    def test_iframe_targets_exist(self):
        for tag, ref in self.parser.refs:
            if tag == "iframe":
                self.assertTrue((DOCS / ref).resolve().exists(), f"iframe missing: {ref}")


if __name__ == "__main__":
    unittest.main()
