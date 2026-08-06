#!/usr/bin/env python3
"""Pre-render the landing-site EN and JA demo decks as committed SVG sets.

Outputs (committed, CI-checked):
  assets/rendered/en/01-….svg … 09-….svg   ← examples/demo-deck.json
  assets/rendered/ja/01-….svg … 09-….svg   ← templates/decks/board-update-ja/
  assets/rendered/decks-manifest.json      ← labels + paths for the chat demo

Also rebuilds:
  examples/demo-deck.html
  (ja-deck.html is still produced by scripts/build_site.py into docs/)

Usage:
    python3 scripts/render_landing_decks.py
    python3 scripts/render_landing_decks.py --check   # fail if committed assets drift
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _slide_filename(index: int, path: Path) -> str:
    stem = path.stem
    # JA specs are already numbered (01-cover); don't double-prefix.
    if re.match(r"^\d{2}-", stem):
        return f"{stem}.svg"
    return f"{index + 1:02d}-{stem}.svg"


DECKS = {
    "en": {
        "manifest": ROOT / "examples" / "demo-deck.json",
        "base": ROOT / "examples",
        "out": ROOT / "assets" / "rendered" / "en",
        "labels_en": [
            "Cover",
            "Agenda",
            "Divider",
            "Exec summary",
            "ARR bridge",
            "Segments",
            "Priorities",
            "Asks",
            "Close",
        ],
        "labels_ja": [
            "表紙",
            "アジェンダ",
            "区切り",
            "役員要約",
            "ARR橋渡し",
            "セグメント",
            "優先度",
            "決議事項",
            "クローズ",
        ],
        "deck_file": "demo-deck.html",
    },
    "ja": {
        "manifest": ROOT / "templates" / "decks" / "board-update-ja" / "deck.json",
        "base": ROOT / "templates" / "decks" / "board-update-ja",
        "out": ROOT / "assets" / "rendered" / "ja",
        "labels_en": [
            "Cover",
            "Agenda",
            "Exec summary",
            "KPI",
            "ARR bridge",
            "Adoption",
            "Risks",
            "Asks",
            "Close",
        ],
        "labels_ja": [
            "表紙",
            "アジェンダ",
            "役員要約",
            "KPI",
            "ARR橋渡し",
            "導入率",
            "リスク",
            "決議",
            "クローズ",
        ],
        "deck_file": "ja-deck.html",
    },
}


def _slide_paths(cfg: dict) -> list[Path]:
    manifest = json.loads(cfg["manifest"].read_text(encoding="utf-8"))
    return [cfg["base"] / p for p in manifest["slides"]]


def _short_label(spec: dict, fallback: str) -> str:
    return (spec.get("headline") or spec.get("title") or fallback).strip()


def render_lang(lang: str, renderer) -> list[dict]:
    cfg = DECKS[lang]
    paths = _slide_paths(cfg)
    cfg["out"].mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for i, path in enumerate(paths):
        spec = json.loads(path.read_text(encoding="utf-8"))
        svg = renderer.render(spec)
        name = _slide_filename(i, path)
        (cfg["out"] / name).write_text(svg, encoding="utf-8")
        entries.append(
            {
                "file": f"rendered/{lang}/{name}",
                "label_en": cfg["labels_en"][i],
                "label_ja": cfg["labels_ja"][i],
                "headline": _short_label(spec, path.stem),
            }
        )
    # Drop stale numbered SVGs that no longer belong to this deck.
    keep = {Path(e["file"]).name for e in entries}
    for old in cfg["out"].glob("*.svg"):
        if old.name not in keep:
            old.unlink()
    return entries


def write_manifest(by_lang: dict[str, list[dict]]) -> Path:
    payload = {
        "en": {
            "deck": DECKS["en"]["deck_file"],
            "slides": by_lang["en"],
        },
        "ja": {
            "deck": DECKS["ja"]["deck_file"],
            "slides": by_lang["ja"],
        },
    }
    out = ROOT / "assets" / "rendered" / "decks-manifest.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def rebuild_en_deck_html() -> Path:
    builder = _load("build_html_deck")
    manifest = json.loads((ROOT / "examples" / "demo-deck.json").read_text(encoding="utf-8"))
    specs = [ROOT / "examples" / p for p in manifest["slides"]]
    html = builder.build_deck(specs, manifest["title"])
    out = ROOT / "examples" / "demo-deck.html"
    out.write_text(html, encoding="utf-8")
    return out


def render_all() -> dict[str, list[dict]]:
    renderer = _load("render_slide_spec")
    by_lang = {lang: render_lang(lang, renderer) for lang in ("en", "ja")}
    write_manifest(by_lang)
    rebuild_en_deck_html()
    return by_lang


def check() -> list[str]:
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # Render into a temp mirror of assets/rendered/{en,ja,manifest}
        # by temporarily swapping DECKS outs — simpler: compare file bytes
        # after a fresh render into temp, vs committed.
        renderer = _load("render_slide_spec")
        diffs: list[str] = []
        fresh: dict[str, list[dict]] = {}
        for lang, cfg in DECKS.items():
            out = td_path / lang
            out.mkdir(parents=True)
            paths = _slide_paths(cfg)
            entries = []
            for i, path in enumerate(paths):
                spec = json.loads(path.read_text(encoding="utf-8"))
                svg = renderer.render(spec)
                name = _slide_filename(i, path)
                (out / name).write_text(svg, encoding="utf-8")
                committed = cfg["out"] / name
                if not committed.exists():
                    diffs.append(f"missing: assets/rendered/{lang}/{name}")
                elif committed.read_text(encoding="utf-8") != svg:
                    diffs.append(f"stale: assets/rendered/{lang}/{name}")
                entries.append(
                    {
                        "file": f"rendered/{lang}/{name}",
                        "label_en": cfg["labels_en"][i],
                        "label_ja": cfg["labels_ja"][i],
                        "headline": _short_label(spec, path.stem),
                    }
                )
            fresh[lang] = entries
            committed_names = {p.name for p in cfg["out"].glob("*.svg")} if cfg["out"].exists() else set()
            fresh_names = {_slide_filename(i, p) for i, p in enumerate(paths)}
            for extra in sorted(committed_names - fresh_names):
                diffs.append(f"extra: assets/rendered/{lang}/{extra}")

        expected_manifest = {
            "en": {"deck": DECKS["en"]["deck_file"], "slides": fresh["en"]},
            "ja": {"deck": DECKS["ja"]["deck_file"], "slides": fresh["ja"]},
        }
        man_path = ROOT / "assets" / "rendered" / "decks-manifest.json"
        if not man_path.exists():
            diffs.append("missing: assets/rendered/decks-manifest.json")
        else:
            committed = json.loads(man_path.read_text(encoding="utf-8"))
            if committed != expected_manifest:
                diffs.append("stale: assets/rendered/decks-manifest.json")

        builder = _load("build_html_deck")
        manifest = json.loads((ROOT / "examples" / "demo-deck.json").read_text(encoding="utf-8"))
        specs = [ROOT / "examples" / p for p in manifest["slides"]]
        html = builder.build_deck(specs, manifest["title"])
        committed_html = (ROOT / "examples" / "demo-deck.html").read_text(encoding="utf-8")
        if committed_html != html:
            diffs.append("stale: examples/demo-deck.html")
        return diffs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if committed deck SVGs drift")
    args = parser.parse_args()
    if args.check:
        diffs = check()
        if diffs:
            for d in diffs:
                print(f"DRIFT: {d}", file=sys.stderr)
            raise SystemExit(1)
        print("OK: landing deck SVGs fresh (en + ja)")
        return
    by_lang = render_all()
    for lang, entries in by_lang.items():
        print(f"OK: {len(entries)} slides → assets/rendered/{lang}/")
    print("OK: assets/rendered/decks-manifest.json")
    print("OK: examples/demo-deck.html")


if __name__ == "__main__":
    main()
