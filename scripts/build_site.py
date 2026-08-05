"""Sync committed repo artifacts into docs/site/artifacts/ for the GitHub Pages site.

Sources (all committed, CI-verified elsewhere):
  assets/rendered/*.svg        -> <dest>/rendered/
  examples/render-specs/*.json -> <dest>/specs/
  examples/demo-*.html         -> <dest>/
  templates/decks/board-update-ja/deck.json -> <dest>/ja-deck.html (rendered)
  specs -> <dest>/gallery-manifest.json (derived)

--check regenerates into a temp dir and diffs against the committed artifacts,
so the site cannot silently drift from what the renderer actually produces.
Python 3 stdlib only.
"""

from __future__ import annotations

import argparse
import filecmp
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = ROOT / "docs" / "site" / "artifacts"

DEMO_HTML = ("demo-deck.html", "demo-report.html", "demo-article.html", "demo-script.html")
JA_MANIFEST = Path("templates/decks/board-update-ja/deck.json")


def _load_deck_builder(root: Path):
    spec = importlib.util.spec_from_file_location("build_html_deck", root / "scripts" / "build_html_deck.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_deck


def _copy_tree_files(src_dir: Path, dest_dir: Path, pattern: str) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    for src in sorted(src_dir.glob(pattern)):
        shutil.copyfile(src, dest_dir / src.name)


def _build_ja_deck(root: Path, dest: Path) -> None:
    manifest_path = root / JA_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    base = manifest_path.parent
    spec_paths = [base / p for p in manifest["slides"]]
    build_deck = _load_deck_builder(root)
    html = build_deck(spec_paths, manifest.get("title", "Slide Deck"))
    (dest / "ja-deck.html").write_text(html, encoding="utf-8")


def _build_gallery_manifest(dest: Path) -> None:
    entries = []
    for spec_path in sorted((dest / "specs").glob("*.json")):
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        svg_name = spec_path.stem + ".svg"
        if not (dest / "rendered" / svg_name).exists():
            continue
        entries.append(
            {
                "file": svg_name,
                "pattern": spec["pattern"],
                "headline": spec.get("headline") or spec.get("title") or spec_path.stem,
            }
        )
    (dest / "gallery-manifest.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build(root: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    _copy_tree_files(root / "assets" / "rendered", dest / "rendered", "*.svg")
    _copy_tree_files(root / "examples" / "render-specs", dest / "specs", "*.json")
    for name in DEMO_HTML:
        shutil.copyfile(root / "examples" / name, dest / name)
    _build_ja_deck(root, dest)
    _build_gallery_manifest(dest)
    return dest


def check(root: Path, dest: Path) -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        fresh = build(root, Path(td))
        diffs = []
        fresh_files = {p.relative_to(fresh) for p in fresh.rglob("*") if p.is_file()}
        dest_files = {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()}
        for rel in sorted(fresh_files - dest_files):
            diffs.append(f"missing: {rel}")
        for rel in sorted(dest_files - fresh_files):
            diffs.append(f"extra: {rel}")
        for rel in sorted(fresh_files & dest_files):
            if not filecmp.cmp(fresh / rel, dest / rel, shallow=False):
                diffs.append(f"stale: {rel}")
        return diffs


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync site artifacts into docs/site/artifacts/.")
    parser.add_argument("--check", action="store_true", help="Fail if committed artifacts are stale")
    args = parser.parse_args()
    if args.check:
        diffs = check(ROOT, DEFAULT_DEST)
        if diffs:
            for d in diffs:
                print(f"DRIFT: {d}", file=sys.stderr)
            raise SystemExit(1)
        print("OK: site artifacts fresh")
        return
    build(ROOT, DEFAULT_DEST)
    print(f"OK: built site artifacts at {DEFAULT_DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
