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
import re
import shutil
import sys
import tempfile
from html import escape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEST = ROOT / "docs" / "site" / "artifacts"
I18N_DIR = ROOT / "site"


def iter_i18n(root: Path) -> list[Path]:
    return sorted((root / "site").glob("i18n*.json"))

DEMO_HTML = ("demo-deck.html", "demo-report.html", "demo-article.html", "demo-script.html")
JA_MANIFEST = Path("templates/decks/board-update-ja/deck.json")
# Only what /try runs in the browser (copying all scripts/references trips the
# package validator's forbidden-text scan over docs/).
PY_RUNTIME = ("render_slide_spec.py", "build_html_deck.py")
PROMPT_REFS = ("prompt-templates.md", "input-triage.md", "visualization-patterns.md")

VOID_TAGS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)


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


def _parse_compound(part: str) -> dict:
    m = {"tag": None, "id": None, "classes": [], "attrs": [], "nth": None}
    nth_m = re.search(r":nth-of-type\((\d+)\)", part)
    if nth_m:
        m["nth"] = int(nth_m.group(1))
        part = part.replace(nth_m.group(0), "")
    for am in re.finditer(r"\[([\w-]+)(\$?)='([^']*)'\]", part):
        m["attrs"].append((am.group(1), am.group(2), am.group(3)))
    part = re.sub(r"\[[^\]]*\]", "", part)
    if "#" in part:
        part, frag = part.split("#", 1)
        bits = frag.split(".")
        m["id"] = bits[0]
        m["classes"] += [b for b in bits[1:] if b]
    classes = part.split(".")
    if classes[0]:
        m["tag"] = classes[0]
    m["classes"] += [c for c in classes[1:] if c]
    return m


def _match_compound(compound: dict, el: tuple) -> bool:
    tag, attrs, nth = el
    if compound["tag"] and compound["tag"] != tag:
        return False
    if compound["id"] and compound["id"] != attrs.get("id"):
        return False
    el_classes = (attrs.get("class") or "").split()
    if any(c not in el_classes for c in compound["classes"]):
        return False
    for name, op, value in compound["attrs"]:
        actual = attrs.get(name)
        if actual is None:
            return False
        if op == "$" and not actual.endswith(value):
            return False
        if not op and actual != value:
            return False
    if compound["nth"] is not None and compound["nth"] != nth:
        return False
    return True


def _match_selector(selector: list, stack: list) -> bool:
    if not _match_compound(selector[-1], stack[-1]):
        return False
    si = len(stack) - 2
    for compound in reversed(selector[:-1]):
        found = False
        while si >= 0:
            if _match_compound(compound, stack[si]):
                found = True
                si -= 1
                break
            si -= 1
        if not found:
            return False
    return True


def _start_tag(tag: str, attrs: list, selfclose: bool) -> str:
    parts = [tag]
    for k, v in attrs:
        if v is None:
            parts.append(k)
        else:
            parts.append(f'{k}="{escape(v, quote=True)}"')
    return "<" + " ".join(parts) + (" />" if selfclose else ">")


class _JaRewriter(HTMLParser):
    def __init__(self, rules: dict):
        super().__init__(convert_charrefs=False)
        self.attr_rules = []
        self.content_rules = []
        for selector, value in rules.items():
            if "@" in selector:
                sel, attr = selector.rsplit("@", 1)
                self.attr_rules.append((selector, [_parse_compound(p) for p in sel.split()], attr, value))
            else:
                self.content_rules.append((selector, [_parse_compound(p) for p in selector.split()], value))
        self.out = []
        self.stack = []
        self.sibling_frames = [{}]
        self.skip_depth = None
        self.used = set()

    def _apply_rules(self, tag, attrs, nth):
        attrs = [list(a) for a in attrs]
        el = (tag, {k: v for k, v in attrs}, nth)
        for sel_key, parts, attr, value in self.attr_rules:
            if _match_selector(parts, self.stack + [el]):
                for a in attrs:
                    if a[0] == attr:
                        a[1] = value
                        self.used.add(sel_key)
                        break
        content = None
        if self.skip_depth is None:
            for sel_key, parts, value in self.content_rules:
                if _match_selector(parts, self.stack + [el]):
                    content = (sel_key, value)
                    break
        return attrs, content

    def handle_starttag(self, tag, attrs):
        if self.skip_depth is not None:
            if tag not in VOID_TAGS:
                self.skip_depth += 1
            return
        nth = self.sibling_frames[-1].get(tag, 0) + 1
        self.sibling_frames[-1][tag] = nth
        attrs, content = self._apply_rules(tag, attrs, nth)
        self.out.append(_start_tag(tag, attrs, tag in VOID_TAGS))
        if tag not in VOID_TAGS:
            el = (tag, {k: v for k, v in attrs}, nth)
            self.stack.append(el)
            self.sibling_frames.append({})
            if content is not None:
                sel_key, value = content
                self.used.add(sel_key)
                self.out.append(value)
                self.skip_depth = 0

    def handle_startendtag(self, tag, attrs):
        if self.skip_depth is not None:
            return
        nth = self.sibling_frames[-1].get(tag, 0) + 1
        self.sibling_frames[-1][tag] = nth
        attrs, _ = self._apply_rules(tag, attrs, nth)
        self.out.append(_start_tag(tag, attrs, True))

    def handle_endtag(self, tag):
        if self.skip_depth is not None:
            if self.skip_depth == 0:
                self.skip_depth = None
                self.out.append(f"</{tag}>")
                if self.stack and self.stack[-1][0] == tag:
                    self.stack.pop()
                    self.sibling_frames.pop()
            else:
                if tag not in VOID_TAGS:
                    self.skip_depth -= 1
            return
        self.out.append(f"</{tag}>")
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
            self.sibling_frames.pop()

    def handle_data(self, data):
        if self.skip_depth is None:
            self.out.append(data)

    def handle_entityref(self, name):
        if self.skip_depth is None:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if self.skip_depth is None:
            self.out.append(f"&#{name};")

    def handle_comment(self, data):
        if self.skip_depth is None:
            self.out.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.out.append(f"<!{decl}>")

    def unused_rules(self):
        all_keys = {k for k, *_ in self.attr_rules} | {k for k, *_ in self.content_rules}
        return all_keys - self.used


def build_ja_html(root: Path, i18n_path: Path | None = None) -> str:
    i18n_path = i18n_path or I18N_DIR / "i18n.json"
    i18n = json.loads(i18n_path.read_text(encoding="utf-8"))
    source = (root / i18n["source"]).read_text(encoding="utf-8")
    selectors = dict(i18n["selectors"])
    selectors["html@lang"] = i18n["htmlLang"]
    rewriter = _JaRewriter(selectors)
    rewriter.feed(source)
    rewriter.close()
    html = "".join(rewriter.out)
    for old, new in i18n.get("pathRewrite", []):
        html = html.replace(old, new)
    for en, ja in i18n.get("scriptReplacements", []):
        if en not in html:
            raise RuntimeError(f"script replacement source not found: {en[:60]}")
        html = html.replace(en, ja)
    unused = rewriter.unused_rules()
    if unused:
        raise RuntimeError("i18n selectors matched nothing: " + ", ".join(sorted(unused)))
    return html


def write_ja_page(root: Path, i18n_path: Path | None = None) -> Path:
    i18n_path = i18n_path or I18N_DIR / "i18n.json"
    i18n = json.loads(i18n_path.read_text(encoding="utf-8"))
    output = root / i18n["output"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_ja_html(root, i18n_path), encoding="utf-8")
    return output


def build(root: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    _copy_tree_files(root / "assets" / "rendered", dest / "rendered", "*.svg")
    _copy_tree_files(root / "examples" / "render-specs", dest / "specs", "*.json")
    for name in DEMO_HTML:
        shutil.copyfile(root / "examples" / name, dest / name)
    (dest / "py").mkdir(parents=True, exist_ok=True)
    for name in PY_RUNTIME:
        shutil.copyfile(root / "scripts" / name, dest / "py" / name)
    (dest / "prompt").mkdir(parents=True, exist_ok=True)
    for name in PROMPT_REFS:
        shutil.copyfile(root / "references" / name, dest / "prompt" / name)
    _build_ja_deck(root, dest)
    _build_gallery_manifest(dest)
    return dest


def check(root: Path, dest: Path) -> list[str]:
    diffs = []
    with tempfile.TemporaryDirectory() as td:
        fresh = build(root, Path(td))
        fresh_files = {p.relative_to(fresh) for p in fresh.rglob("*") if p.is_file()}
        dest_files = {p.relative_to(dest) for p in dest.rglob("*") if p.is_file()}
        for rel in sorted(fresh_files - dest_files):
            diffs.append(f"missing: {rel}")
        for rel in sorted(dest_files - fresh_files):
            diffs.append(f"extra: {rel}")
        for rel in sorted(fresh_files & dest_files):
            if not filecmp.cmp(fresh / rel, dest / rel, shallow=False):
                diffs.append(f"stale: {rel}")
    for i18n_path in iter_i18n(root):
        i18n = json.loads(i18n_path.read_text(encoding="utf-8"))
        output = root / i18n["output"]
        rel = i18n["output"].replace("docs/", "", 1)
        if output.exists():
            if output.read_text(encoding="utf-8") != build_ja_html(root, i18n_path):
                diffs.append(f"stale: {rel}")
        else:
            diffs.append(f"missing: {rel}")
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
    for i18n_path in iter_i18n(ROOT):
        out = write_ja_page(ROOT, i18n_path)
        print(f"OK: built {out.relative_to(ROOT)} (from {i18n_path.name})")
    print(f"OK: built site artifacts at {DEFAULT_DEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
