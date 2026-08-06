import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_module():
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BuildSiteTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_build_copies_rendered_svgs(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            svgs = sorted((Path(td) / "rendered").glob("*.svg"))
            self.assertEqual(len(svgs), len(list((ROOT / "assets" / "rendered").glob("*.svg"))))

    def test_build_creates_ja_deck(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            html = (Path(td) / "ja-deck.html").read_text(encoding="utf-8")
            self.assertIn("取締役会", html)

    def test_manifest_entries(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            manifest = json.loads((Path(td) / "gallery-manifest.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(manifest), 20)
            for entry in manifest:
                self.assertIn("file", entry)
                self.assertIn("pattern", entry)
                self.assertIn("headline", entry)
            wf = [e for e in manifest if e["file"] == "arr-waterfall.svg"]
            self.assertEqual(wf[0]["pattern"], "waterfall")

    def test_ja_page_generation(self):
        html = self.mod.build_ja_html(ROOT)
        self.assertIn('lang="ja"', html)
        self.assertIn("メモがそのまま", html)
        self.assertNotIn('"./site/', html)
        self.assertIn('"../site/artifacts/demo-deck.html"', html)
        self.assertIn('href="../"', html)

    def test_ja_try_page_generation(self):
        html = self.mod.build_ja_html(ROOT, ROOT / "site" / "i18n-try.json")
        self.assertIn('lang="ja"', html)
        self.assertIn("メモを入れる", html)
        self.assertNotIn('"./site/', html)
        self.assertNotIn('"../site/', html)
        self.assertIn('"../../site/css/try.css"', html)
        self.assertIn('href="../../try/"', html)

    def test_try_runtime_assets_copied(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            self.assertTrue((Path(td) / "py" / "render_slide_spec.py").exists())
            self.assertTrue((Path(td) / "py" / "build_html_deck.py").exists())
            self.assertTrue((Path(td) / "prompt" / "visualization-patterns.md").exists())

    def test_check_passes_on_fresh_build(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            self.assertEqual(self.mod.check(ROOT, Path(td)), [])

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            victim = Path(td) / "rendered" / "arr-waterfall.svg"
            victim.write_text(victim.read_text(encoding="utf-8") + " ", encoding="utf-8")
            diffs = self.mod.check(ROOT, Path(td))
            self.assertTrue(any("arr-waterfall.svg" in d for d in diffs))


if __name__ == "__main__":
    unittest.main()
