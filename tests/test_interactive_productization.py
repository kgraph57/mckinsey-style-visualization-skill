from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = (
    "interactive-scene-schema.md",
    "interaction-selection.md",
    "interactive-accessibility.md",
    "presenter-operation.md",
)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self.iframes: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "a":
            self.links.append(values)
        elif tag == "iframe":
            self.iframes.append(values)


class InteractiveProductizationTests(unittest.TestCase):
    def test_forward_request_classes_have_an_explicit_route_and_handoff(self) -> None:
        selection = (ROOT / "references/interaction-selection.md").read_text(
            encoding="utf-8"
        )
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        requests = {
            "ordinary deck": ("slide, deck, presentation", "classic builder only"),
            "quiet animation": ("animated deck, quiet reveal", "classic builder only"),
            "Japanese dynamic deck": ("動くスライド、動的スライド", "classic, then interactive builder"),
            "English what-if deck": ("interactive deck, dynamic deck, live scenario, what-if", "classic, then interactive builder"),
        }
        for label, (trigger, route) in requests.items():
            with self.subTest(label=label):
                self.assertIn(trigger, selection)
                self.assertIn(route, selection)
        self.assertIn("build_html_deck.py", skill)
        self.assertIn("build_interactive_deck.py", skill)

    def test_v3_metadata_identifies_prerelease_and_preserves_stable_release(self) -> None:
        manifest = json.loads(
            (ROOT / "marketplace/manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["version"], "3.0.0-rc.1")
        self.assertEqual(
            manifest["permissions"],
            {"network": False, "filesystem_write": True, "external_tools": False},
        )
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(changelog, r"3\.0\.0-rc\.1[^\n]*prerelease")
        for path in (ROOT / "README.md", ROOT / "README.ja.md", ROOT / "DISTRIBUTION.md"):
            text = path.read_text(encoding="utf-8")
            self.assertIn("releases/tag/v3.0.0-rc.1", text)
            self.assertIn("releases/tag/v2.4.0", text)

    def test_four_focused_references_exist_resolve_links_and_are_routed_by_skill(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for name in REFERENCES:
            path = ROOT / "references" / name
            self.assertTrue(path.is_file(), name)
            self.assertIn(f"references/{name}", skill)
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)#]+)(?:#[^)]+)?\)", text):
                if re.match(r"^[a-z]+://", target):
                    continue
                self.assertTrue((path.parent / target).resolve().exists(), f"{name}: {target}")

    def test_documented_project_relay_commands_reproduce_both_html_artifacts(self) -> None:
        manifest = ROOT / "examples" / "interactive-deck" / "deck.json"
        with tempfile.TemporaryDirectory() as tmp:
            classic = Path(tmp) / "deck.html"
            interactive = Path(tmp) / "deck.interactive.html"
            commands = (
                (ROOT / "scripts" / "build_html_deck.py", classic),
                (ROOT / "scripts" / "build_interactive_deck.py", interactive),
            )
            for script, output in commands:
                result = subprocess.run(
                    [sys.executable, "-B", str(script), "--manifest", str(manifest), "-o", str(output)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                classic.read_bytes(),
                (manifest.parent / "deck.html").read_bytes(),
            )
            self.assertEqual(
                interactive.read_bytes(),
                (manifest.parent / "deck.interactive.html").read_bytes(),
            )
            self.assertEqual(sorted(path.name for path in Path(tmp).iterdir()), ["deck.html", "deck.interactive.html"])

    def test_manifest_proof_paths_are_public_and_resolve(self) -> None:
        manifest = json.loads(
            (ROOT / "marketplace/manifest.json").read_text(encoding="utf-8")
        )
        proof = manifest["proof"]
        for key in ("standard_deck", "interactive_deck", "interactive_pdf", "interactive_schema", "interactive_validation"):
            value = proof[key]
            self.assertFalse(Path(value).is_absolute(), value)
            self.assertNotIn("test-results", value)
            self.assertNotIn("audit", value.lower())
            self.assertTrue((ROOT / value).is_file(), value)

    def test_site_build_copies_project_relay_and_never_frames_interactive_artifact(self) -> None:
        import importlib.util

        spec = importlib.util.spec_from_file_location("build_site_product", ROOT / "scripts" / "build_site.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            module.build(ROOT, dest)
            pairs = {
                "project-relay.html": "deck.html",
                "project-relay.interactive.html": "deck.interactive.html",
                "project-relay.pdf": "deck.pdf",
            }
            for target, source in pairs.items():
                self.assertEqual(
                    (dest / target).read_bytes(),
                    (ROOT / "examples" / "interactive-deck" / source).read_bytes(),
                )

        for site_path in (ROOT / "docs" / "examples" / "index.html", ROOT / "docs" / "ja" / "examples" / "index.html"):
            parser = _LinkParser()
            parser.feed(site_path.read_text(encoding="utf-8"))
            matches = [link for link in parser.links if "project-relay.interactive.html" in link.get("href", "")]
            self.assertEqual(len(matches), 1, site_path)
            self.assertEqual(matches[0].get("target"), "_blank")
            self.assertEqual(set(matches[0].get("rel", "").split()), {"noopener", "noreferrer"})
            self.assertFalse(any("project-relay.interactive.html" in item.get("src", "") for item in parser.iframes))

    def test_browser_trial_remains_classic_only(self) -> None:
        build_site = (ROOT / "scripts" / "build_site.py").read_text(encoding="utf-8")
        py_render = (ROOT / "docs" / "site" / "js" / "try" / "py-render.js").read_text(encoding="utf-8")
        for forbidden in ("build_interactive_deck", "interactive_scene", "interactive_contract", "audit_interactive_deck"):
            self.assertNotIn(forbidden, build_site)
            self.assertNotIn(forbidden, py_render)
        self.assertIn("build_html_deck.py", build_site)

    def test_ci_keeps_core_dependency_free_and_uses_a_separate_pinned_browser_job(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements-e2e.txt").read_text(encoding="utf-8")
        self.assertIn("playwright==1.58.0", requirements)
        self.assertRegex(workflow, r"(?m)^  validate:\s*$")
        self.assertRegex(workflow, r"(?m)^  interactive-e2e:\s*$")
        validate_block, browser_block = workflow.split("  interactive-e2e:", 1)
        self.assertNotIn("pip install", validate_block)
        self.assertNotIn("playwright install", validate_block)
        self.assertIn("requirements-e2e.txt", browser_block)
        self.assertIn("chromium", browser_block)
        self.assertIn("firefox", browser_block)
        self.assertIn("poppler-utils", browser_block)
        self.assertIn("tests/e2e", browser_block)
        self.assertIn("test-results/interactive", browser_block)

    def test_public_v3_surfaces_do_not_leak_private_or_audit_paths(self) -> None:
        paths = [
            ROOT / "SKILL.md",
            ROOT / "README.md",
            ROOT / "README.ja.md",
            ROOT / "QUICKSTART.md",
            ROOT / "EXAMPLES.md",
            ROOT / "marketplace" / "manifest.json",
            *(ROOT / "references" / name for name in REFERENCES),
            *(path for path in (ROOT / "examples" / "interactive-deck").rglob("*") if path.is_file() and path.suffix in {".md", ".json", ".html"}),
        ]
        # Author documentation may name the ignored audit-output directory so
        # contributors can reproduce validation. The marketplace proof map is
        # checked separately and may not point at audit output.
        forbidden = ("/Users/", ".codex/attachments", "note.com/uchita")
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in forbidden:
                self.assertNotIn(token, text, f"{path.relative_to(ROOT)}: {token}")


if __name__ == "__main__":
    unittest.main()
