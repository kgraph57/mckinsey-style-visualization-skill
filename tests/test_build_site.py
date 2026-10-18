import importlib.util
import json
import shutil
import subprocess
import sys
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
            en = sorted((Path(td) / "rendered" / "en").glob("*.svg"))
            ja = sorted((Path(td) / "rendered" / "ja").glob("*.svg"))
            self.assertEqual(len(en), 9)
            self.assertEqual(len(ja), 9)
            man = json.loads((Path(td) / "decks-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(man["en"]["slides"]), 9)
            self.assertEqual(len(man["ja"]["slides"]), 9)
            self.assertTrue(man["en"]["slides"][0]["file"].startswith("rendered/en/"))
            self.assertTrue(man["ja"]["slides"][0]["file"].startswith("rendered/ja/"))

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
        self.assertIn("触って、判断を深めるスライド", html)
        self.assertNotIn('"./site/', html)
        self.assertIn('"../site/artifacts/ja-deck.html?embed=1"', html)
        self.assertIn("考える時間を、", html)
        self.assertIn('href="../"', html)
        self.assertIn("リポジトリ", html)
        self.assertIn("MITライセンス", html)

    def test_ja_try_page_generation(self):
        html = self.mod.build_ja_html(ROOT, ROOT / "site" / "i18n-try.json")
        self.assertIn('lang="ja"', html)
        self.assertIn("メモを入れる", html)
        self.assertNotIn('"./site/', html)
        self.assertNotIn('"../site/', html)
        self.assertRegex(html, r'"\.\./\.\./site/css/try\.css(?:\?[^"]+)?"')
        self.assertIn('href="../../try/"', html)

    def test_try_runtime_assets_copied(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            self.assertTrue((Path(td) / "py" / "render_slide_spec.py").exists())
            self.assertTrue((Path(td) / "py" / "build_html_deck.py").exists())
            self.assertTrue((Path(td) / "prompt" / "visualization-patterns.md").exists())

    def test_try_runtime_builder_imports_from_its_bundled_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            runtime = Path(td) / "py"
            self.assertTrue((runtime / "deck_core.py").is_file())
            result = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); from build_html_deck import build_deck; print(build_deck([], 'Portable'))", str(runtime)], cwd=td, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("<title>Portable</title>", result.stdout)

    @unittest.skipUnless(shutil.which("node"), "Node is optional; required for the Try harness behavior check")
    def test_try_harness_installs_shared_normalizer_before_python_import(self):
        with tempfile.TemporaryDirectory() as td:
            harness = Path(td) / "py-render.mjs"
            harness.write_text((ROOT / "docs/site/js/try/py-render.js").read_text(encoding="utf-8"), encoding="utf-8")
            program = """
import {readFileSync, writeFileSync} from 'node:fs';
import {basename, join} from 'node:path';
globalThis.document = {createElement: () => ({}), head: {appendChild: script => script.onload()}};
globalThis.fetch = async url => ({ok: true, text: async () => readFileSync(join(process.argv[2], basename(new URL(url).pathname)), 'utf8')});
globalThis.loadPyodide = async () => ({FS: {mkdirTree() {}, writeFile(path, data) {writeFileSync(join(process.argv[3], basename(path)), data);}}, runPython() {}});
const {ensurePyodide} = await import(process.argv[1]);
await ensurePyodide();
"""
            runtime = Path(td) / "runtime"
            runtime.mkdir()
            result = subprocess.run([shutil.which("node"), "--input-type=module", "-e", program, harness.as_uri(), str(ROOT / "scripts"), str(runtime)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            imported = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); from build_html_deck import build_deck; print(build_deck([], 'Installed by Try'))", str(runtime)], cwd=td, capture_output=True, text=True)
            self.assertEqual(imported.returncode, 0, imported.stderr)
            self.assertIn("<title>Installed by Try</title>", imported.stdout)

    def test_ja_site_deck_reads_mixed_manifest_and_ignores_missing_scene(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
            manifest_path = root / self.mod.JA_MANIFEST
            manifest_path.parent.mkdir(parents=True)
            original_path = ROOT / self.mod.JA_MANIFEST
            manifest = json.loads(original_path.read_text(encoding="utf-8"))
            manifest["slides"] = [str(original_path.parent / p) if i % 2 == 0 else {"spec": str(original_path.parent / p), "scene": "../absent.json"} for i, p in enumerate(manifest["slides"])]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            dest = root / "output"
            dest.mkdir()
            self.mod._build_ja_deck(root, dest)
            self.assertEqual((dest / "ja-deck.html").read_bytes(), (ROOT / "docs/site/artifacts/ja-deck.html").read_bytes())

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
