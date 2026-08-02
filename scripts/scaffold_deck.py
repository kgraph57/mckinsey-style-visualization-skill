#!/usr/bin/env python3
"""Scaffold a ready-made deck archetype into a new project directory.

Copies one of the bundled deck templates — a build_html_deck-compatible
deck.json manifest plus its numbered slide specs — from
templates/decks/<archetype>/ into an output directory, so the path from
"pick a template" to "animated HTML deck" is:

    python3 scripts/scaffold_deck.py --list
    python3 scripts/scaffold_deck.py board-update -o my-deck --title "Q1 Board Update"
    cd my-deck
    # edit specs/*.json with your own numbers, then:
    python3 <repo>/scripts/build_html_deck.py --manifest deck.json -o deck.html

Every archetype's specs already render successfully as shipped (illustrative
placeholder data) — scaffolding never requires editing before the first
build; editing the specs is how you replace the placeholder story with your
own.

Usage:
    python3 scripts/scaffold_deck.py --list
    python3 scripts/scaffold_deck.py <archetype> -o <dir> [--title "New Title"] [--force]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = ROOT / "templates" / "decks"


def discover_archetypes() -> list[str]:
    """Archetypes are auto-discovered from templates/decks/ (any subdirectory
    with a deck.json) rather than hardcoded, so a new template directory is
    picked up without touching this script."""
    if not TEMPLATES_ROOT.is_dir():
        return []
    return sorted(
        entry.name
        for entry in TEMPLATES_ROOT.iterdir()
        if entry.is_dir() and (entry / "deck.json").exists()
    )


def load_manifest(archetype: str) -> dict:
    manifest_path = TEMPLATES_ROOT / archetype / "deck.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def list_archetypes() -> None:
    archetypes = discover_archetypes()
    if not archetypes:
        print(f"ERROR: no deck archetypes found under {TEMPLATES_ROOT}", file=sys.stderr)
        raise SystemExit(1)

    print("Available deck archetypes:\n")
    name_width = max(len(name) for name in archetypes)
    for name in archetypes:
        manifest = load_manifest(name)
        slide_count = len(manifest.get("slides", []))
        count_label = f"({slide_count} slide{'s' if slide_count != 1 else ''})"
        description = str(manifest.get("description", "")).strip()
        print(f"  {name.ljust(name_width)}  {count_label:<11} {description}")
    print('\nUsage: python3 scripts/scaffold_deck.py <archetype> -o <dir> [--title "..."] [--force]')


def _rewrite_title(output: Path, slides: list[str], title: str) -> None:
    """Rewrite the manifest title and the cover slide's title so a scaffolded
    deck and its first slide agree without hand-editing the copy. The first
    spec with pattern "cover" is used, not a hardcoded filename, so this
    works regardless of an archetype's numbering scheme."""
    manifest_path = output / "deck.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["title"] = title
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for relative in slides:
        spec_path = output / relative
        if not spec_path.exists():
            continue
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if spec.get("pattern") == "cover":
            spec["title"] = title
            spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return


def scaffold(archetype: str, output: Path, title: str | None, force: bool) -> None:
    archetypes = discover_archetypes()
    if archetype not in archetypes:
        known = ", ".join(archetypes) if archetypes else "(none found)"
        print(f"ERROR: unknown archetype {archetype!r}. Available: {known}", file=sys.stderr)
        raise SystemExit(1)

    source_dir = TEMPLATES_ROOT / archetype
    source_specs = source_dir / "specs"
    if not source_specs.is_dir():
        print(f"ERROR: archetype {archetype!r} is missing its specs/ directory", file=sys.stderr)
        raise SystemExit(1)

    if output.exists():
        if not output.is_dir():
            print(f"ERROR: output path exists and is not a directory: {output}", file=sys.stderr)
            raise SystemExit(1)
        if any(output.iterdir()) and not force:
            print(
                f"ERROR: output directory is not empty: {output} (use --force to overwrite)",
                file=sys.stderr,
            )
            raise SystemExit(1)
    output.mkdir(parents=True, exist_ok=True)

    dest_specs = output / "specs"
    if dest_specs.exists():
        shutil.rmtree(dest_specs)
    shutil.copytree(source_specs, dest_specs)
    shutil.copy2(source_dir / "deck.json", output / "deck.json")

    manifest = json.loads((output / "deck.json").read_text(encoding="utf-8"))
    slides = manifest.get("slides", [])

    if title:
        _rewrite_title(output, slides, title)

    render_script = ROOT / "scripts" / "render_slide_spec.py"
    build_script = ROOT / "scripts" / "build_html_deck.py"
    resolved = output.resolve()
    print(f"OK: scaffolded '{archetype}' ({len(slides)} slides) to {resolved}")
    print("\nNext steps:")
    print(
        f'  1) Render check every slide: for f in "{resolved}"/specs/*.json; '
        f'do python3 "{render_script}" "$f" -o /dev/null || break; done'
    )
    print(f'  2) Build the HTML deck:      python3 "{build_script}" --manifest "{resolved}/deck.json" -o "{resolved}/deck.html"')


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scaffold a ready-made deck archetype (manifest + specs) into a new directory."
    )
    parser.add_argument("archetype", nargs="?", help="Archetype name (see --list)")
    parser.add_argument("--list", action="store_true", help="List available archetypes and exit")
    parser.add_argument("-o", "--output", help="Output directory for the scaffolded deck")
    parser.add_argument("--title", help="Rewrite the deck title and cover slide title")
    parser.add_argument("--force", action="store_true", help="Overwrite a non-empty output directory")
    args = parser.parse_args()

    if args.list:
        list_archetypes()
        return

    if not args.archetype:
        print("ERROR: an archetype is required (or pass --list to see available archetypes)", file=sys.stderr)
        raise SystemExit(1)
    if not args.output:
        print("ERROR: -o/--output is required", file=sys.stderr)
        raise SystemExit(1)

    scaffold(args.archetype, Path(args.output), args.title, args.force)


if __name__ == "__main__":
    main()
