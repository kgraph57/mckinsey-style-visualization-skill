import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    spec = importlib.util.spec_from_file_location(
        "render_landing_decks", ROOT / "scripts" / "render_landing_decks.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class RenderLandingDecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_committed_en_and_ja_sets_exist(self):
        en = sorted((ROOT / "assets" / "rendered" / "en").glob("*.svg"))
        ja = sorted((ROOT / "assets" / "rendered" / "ja").glob("*.svg"))
        self.assertEqual(len(en), 9)
        self.assertEqual(len(ja), 9)
        # JA content should contain CJK; EN cover should not rely on JA deck.
        ja_cover = (ROOT / "assets" / "rendered" / "ja" / "01-cover.svg").read_text(
            encoding="utf-8"
        )
        en_cover = (
            ROOT / "assets" / "rendered" / "en" / "01-board-deck-cover.svg"
        ).read_text(encoding="utf-8")
        self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in ja_cover))
        self.assertIn("FY26", en_cover)

    def test_manifest_matches_folders(self):
        man = json.loads(
            (ROOT / "assets" / "rendered" / "decks-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        for lang in ("en", "ja"):
            self.assertEqual(len(man[lang]["slides"]), 9)
            for entry in man[lang]["slides"]:
                path = ROOT / "assets" / entry["file"]
                self.assertTrue(path.exists(), msg=entry["file"])
                self.assertIn("label_en", entry)
                self.assertIn("label_ja", entry)

    def test_check_passes_on_committed(self):
        self.assertEqual(self.mod.check(), [])


if __name__ == "__main__":
    unittest.main()
