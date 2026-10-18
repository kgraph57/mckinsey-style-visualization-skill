"""Shared deck manifest normalization, independent of rendering and scene I/O."""

from __future__ import annotations

import json
from pathlib import Path
from typing import NamedTuple


class NormalizedSlide(NamedTuple):
    spec_path: Path
    scene_path: Path | None
    slide_id: str


def load_manifest(path: Path) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    return manifest


def _path_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"{field} must be a non-empty path string")
    return value


def resolve_scene_path(root: Path, relative: str) -> Path:
    """Confine a scene or scene-reference path to its manifest directory.

    Resolution does not read the target. It checks existing symlink parents
    even when the leaf has not been created yet. Static spec paths deliberately
    do not use this restriction, preserving the classic builder's contract.
    """
    path = Path(_path_string(relative, "scene path"))
    if path.is_absolute():
        raise ValueError("scene path must be relative to the manifest root")
    root = Path(root).resolve()
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("scene path escapes the manifest root")
    return resolved


def normalize_manifest(
    manifest: dict, manifest_path: Path, *, interactive: bool = False
) -> list[NormalizedSlide]:
    """Normalize ordered string/object entries without reading any slide file.

    Classic consumers inspect only ``spec`` and ``id``; ``scene`` is ignored
    entirely. Interactive callers opt into confined scene path resolution and
    remain responsible for loading and validating the scene itself.
    """
    if not isinstance(manifest, dict) or not isinstance(manifest.get("slides"), list):
        raise ValueError("manifest must include a 'slides' list")
    base = Path(manifest_path).parent
    slides = []
    ids = set()
    for index, entry in enumerate(manifest["slides"], start=1):
        scene_path = None
        slide_id = f"slide-{index:03d}"
        if isinstance(entry, str):
            spec = _path_string(entry, f"slide {index} spec")
        elif isinstance(entry, dict):
            spec = _path_string(entry.get("spec"), f"slide {index} spec")
            slide_id = entry.get("id", slide_id)
            if interactive and "scene" in entry:
                scene_path = resolve_scene_path(base, entry["scene"])
        else:
            raise ValueError(f"slide {index} must be a spec path string or object")
        if not isinstance(slide_id, str) or not slide_id.strip():
            raise ValueError(f"slide {index} id must be a non-empty string")
        if slide_id in ids:
            raise ValueError(f"duplicate slide id: {slide_id!r}")
        ids.add(slide_id)
        slides.append(NormalizedSlide(base / spec, scene_path, slide_id))
    return slides
