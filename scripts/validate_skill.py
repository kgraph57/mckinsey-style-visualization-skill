#!/usr/bin/env python3
"""Validate the skill package structure for marketplace readiness."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "README.ja.md",
    "MARKETPLACE.md",
    "MARKETPLACE_TARGETS.md",
    "SUBMISSION.md",
    "DISTRIBUTION.md",
    "COMMERCIALIZATION.md",
    "LAUNCH.md",
    "BUYER_BRIEF.md",
    "TRACTION.md",
    "GROWTH.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "ROADMAP.md",
    "marketplace/manifest.json",
    ".github/workflows/ci.yml",
    "references/style-system.md",
    "references/visualization-patterns.md",
    "references/prompt-templates.md",
    "references/quality-rubric.md",
    "references/public-reference-corpus.md",
    "references/iterative-review-loop.md",
    "references/expert-review-loop.md",
    "references/input-triage.md",
    "references/document-type-profiles.md",
    "references/persona-playbook.md",
    "examples/board-update-input.md",
    "examples/board-update-slide-spec.md",
    "examples/evaluation-report.md",
    "examples/review-loop/market-entry-draft-v1.md",
    "examples/review-loop/market-entry-review-v1.md",
    "examples/review-loop/market-entry-draft-v2.md",
    "examples/review-loop/market-entry-review-v2.md",
    "examples/review-loop/board-update-draft-v1.md",
    "examples/review-loop/board-update-review-v1.md",
    "examples/review-loop/board-update-draft-v2.md",
    "examples/review-loop/board-update-review-v2.md",
    "examples/review-loop/vendor-selection-draft-v1.md",
    "examples/review-loop/vendor-selection-review-v1.md",
    "examples/review-loop/vendor-selection-draft-v2.md",
    "examples/review-loop/vendor-selection-review-v2.md",
    "examples/review-loop/investment-memo-draft-v1.md",
    "examples/review-loop/investment-memo-review-v1.md",
    "examples/review-loop/investment-memo-draft-v2.md",
    "examples/review-loop/investment-memo-review-v2.md",
    "scripts/review_slide_spec.py",
    "scripts/render_slide_spec.py",
    "examples/render-specs/arr-waterfall.json",
    "examples/render-specs/capacity-gap.json",
    "examples/render-specs/adoption-before-after.json",
    "examples/render-specs/adoption-trend.json",
    "examples/render-specs/vendor-benchmark.json",
    "examples/render-specs/executive-summary.json",
    "examples/render-specs/onboarding-flow.json",
    "examples/render-specs/sales-pipeline-funnel.json",
    "examples/render-specs/marketing-channel-heatmap.json",
    "examples/render-specs/product-priority-two-by-two.json",
    "examples/render-specs/pmo-rollout-gantt.json",
    "examples/render-specs/hr-talent-scorecard.json",
    "examples/render-specs/eng-incident-flow.json",
    "examples/render-specs/research-outcomes-before-after.json",
    "examples/render-specs/pricing-retention-scatter.json",
    "examples/render-specs/deal-size-distribution.json",
    "examples/render-specs/segment-adoption-multiples.json",
    "examples/render-specs/board-deck-cover.json",
    "examples/render-specs/jp-board-summary.json",
    "assets/rendered/sales-pipeline-funnel.svg",
    "assets/rendered/marketing-channel-heatmap.svg",
    "assets/rendered/product-priority-two-by-two.svg",
    "assets/rendered/pmo-rollout-gantt.svg",
    "assets/rendered/hr-talent-scorecard.svg",
    "assets/rendered/eng-incident-flow.svg",
    "assets/rendered/research-outcomes-before-after.svg",
    "assets/rendered/arr-waterfall.svg",
    "assets/rendered/pricing-retention-scatter.svg",
    "assets/rendered/deal-size-distribution.svg",
    "assets/rendered/segment-adoption-multiples.svg",
    "assets/rendered/board-deck-cover.svg",
    "assets/rendered/jp-board-summary.svg",
    "assets/readme/demo.gif",
    "scripts/build_html_deck.py",
    "examples/demo-deck.json",
    "examples/demo-deck.html",
    "scripts/scaffold_deck.py",
    "scripts/build_html_report.py",
    "examples/render-specs/strategy-agenda.json",
    "examples/render-specs/phase-divider.json",
    "examples/render-specs/rollout-constraints.json",
    "examples/render-specs/board-closing.json",
    "examples/render-specs/customer-quote.json",
    "examples/render-specs/deck-end-cover.json",
    "assets/rendered/strategy-agenda.svg",
    "assets/rendered/phase-divider.svg",
    "assets/rendered/rollout-constraints.svg",
    "assets/rendered/board-closing.svg",
    "assets/rendered/customer-quote.svg",
    "assets/rendered/deck-end-cover.svg",
    "scripts/render_landing_decks.py",
    "assets/rendered/decks-manifest.json",
    "assets/rendered/en/01-board-deck-cover.svg",
    "assets/rendered/en/09-deck-end-cover.svg",
    "assets/rendered/ja/01-cover.svg",
    "assets/rendered/ja/09-end-cover.svg",
    "templates/decks/board-update/deck.json",
    "templates/decks/strategy-recommendation/deck.json",
    "templates/decks/project-status/deck.json",
    "templates/decks/market-entry/deck.json",
    "templates/decks/sales-proposal/deck.json",
    "templates/decks/board-update-ja/deck.json",
    "templates/reports/board-pre-read.md",
    "templates/reports/one-pager.md",
    "templates/reports/proposal-memo.md",
    "examples/demo-report.md",
    "examples/demo-report.html",
    "scripts/build_speaker_script.py",
    "scripts/build_html_article.py",
    "examples/demo-script.html",
    "examples/demo-article.html",
    "assets/readme/hero-before-after.svg",
    "assets/social/launch-card.svg",
    ".github/ISSUE_TEMPLATE/marketplace-listing.md",
    ".github/ISSUE_TEMPLATE/example-request.md",
    ".github/ISSUE_TEMPLATE/buyer-inquiry.md",
    ".github/ISSUE_TEMPLATE/bug-report.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
]

FORBIDDEN_PATTERNS = [
    "github.com/kgraph57/Helix",
    "raw.githubusercontent.com/kgraph57/Helix",
    "official McKinsey",
    "official BCG",
    "official Bain",
    "McKinsey-approved",
    "BCG-approved",
    "Bain-approved",
    "McKinsey-certified",
    "BCG-certified",
    "Bain-certified",
    "in partnership with McKinsey",
    "in partnership with BCG",
    "in partnership with Bain",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path: str) -> str:
    full_path = ROOT / path
    if not full_path.exists():
        fail(f"missing required file: {path}")
    return full_path.read_text(encoding="utf-8")


def parse_frontmatter(skill_text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", skill_text, re.DOTALL)
    if not match:
        fail("SKILL.md must start with YAML frontmatter")

    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            fail(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def validate_required_files() -> None:
    for path in REQUIRED_FILES:
        if not (ROOT / path).exists():
            fail(f"missing required file: {path}")


def validate_skill_frontmatter() -> None:
    text = read_text("SKILL.md")
    fields = parse_frontmatter(text)
    allowed_fields = {"name", "description"}
    extra_fields = sorted(set(fields) - allowed_fields)
    if extra_fields:
        fail(f"SKILL.md frontmatter has unsupported fields: {', '.join(extra_fields)}")

    if fields.get("name") != "strategy-consulting-visualization":
        fail("SKILL.md frontmatter name must be strategy-consulting-visualization")

    description = fields.get("description", "")
    if not description.startswith("Use when "):
        fail("SKILL.md description must start with 'Use when '")
    if len(description) > 500:
        fail("SKILL.md description must be 500 characters or fewer")

    for reference in [
        "references/visualization-patterns.md",
        "references/style-system.md",
        "references/prompt-templates.md",
        "references/quality-rubric.md",
        "references/public-reference-corpus.md",
        "references/iterative-review-loop.md",
        "references/expert-review-loop.md",
        "references/input-triage.md",
        "references/document-type-profiles.md",
    ]:
        if reference not in text:
            fail(f"SKILL.md must reference {reference}")

    disclaimer = "not affiliated with, endorsed by, or sponsored by"
    if disclaimer not in text:
        fail("SKILL.md must include a non-affiliation disclaimer")


def validate_manifest() -> None:
    manifest_path = ROOT / "marketplace/manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"marketplace/manifest.json is invalid JSON: {exc}")

    expected = {
        "name": "strategy-consulting-visualization",
        "display_name": "Strategy Consulting Visualization Skill",
        "version": "2.4.0",
        "license": "MIT",
        "entrypoint": "SKILL.md",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            fail(f"manifest field {key!r} must be {value!r}")

    permissions = manifest.get("permissions", {})
    for key in ["network", "filesystem_write", "external_tools"]:
        if permissions.get(key) is not False:
            fail(f"manifest permissions.{key} must be false")

    proof = manifest.get("proof", {})
    for proof_path in proof.values():
        if not (ROOT / proof_path).exists():
            fail(f"manifest proof path does not exist: {proof_path}")

    launch = manifest.get("launch", {})
    for launch_path in launch.values():
        if not (ROOT / launch_path).exists():
            fail(f"manifest launch path does not exist: {launch_path}")

    operations = manifest.get("operations", {})
    for operations_path in operations.values():
        if not (ROOT / operations_path).exists():
            fail(f"manifest operations path does not exist: {operations_path}")


def validate_no_stale_or_risky_text() -> None:
    scanned_extensions = {".md", ".json", ".py", ".txt"}
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file() or path.suffix not in scanned_extensions:
            continue
        if path.relative_to(ROOT).parts[:2] == ("docs", "superpowers"):
            continue
        if path.relative_to(ROOT) in {Path("scripts/validate_skill.py"), Path("scripts/review_slide_spec.py")}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.lower() in text.lower():
                fail(f"forbidden text {pattern!r} found in {path.relative_to(ROOT)}")


def validate_renderer() -> None:
    import importlib.util

    module_path = ROOT / "scripts" / "render_slide_spec.py"
    spec_loader = importlib.util.spec_from_file_location("render_slide_spec", module_path)
    module = importlib.util.module_from_spec(spec_loader)
    spec_loader.loader.exec_module(module)

    for spec_path in sorted((ROOT / "examples" / "render-specs").glob("*.json")):
        try:
            slide_spec = json.loads(spec_path.read_text(encoding="utf-8"))
            svg = module.render(slide_spec)
        except Exception as exc:  # noqa: BLE001 - any render failure should fail validation
            fail(f"renderer failed on {spec_path.relative_to(ROOT)}: {exc}")
        if "<svg" not in svg:
            fail(f"renderer produced invalid output for {spec_path.relative_to(ROOT)}")
        rendered_path = ROOT / "assets" / "rendered" / f"{spec_path.stem}.svg"
        if not rendered_path.exists():
            fail(f"missing committed render for {spec_path.relative_to(ROOT)}: {rendered_path.relative_to(ROOT)}")
        committed_svg = rendered_path.read_text(encoding="utf-8")
        if svg != committed_svg:
            fail(
                "stale committed render for "
                f"{spec_path.relative_to(ROOT)}: regenerate {rendered_path.relative_to(ROOT)}"
            )

    # Deck-template specs are illustrative starting points meant to be edited by
    # scaffold_deck.py users, not frozen proof assets — render must succeed, but
    # no committed SVG is required or compared.
    for spec_path in sorted((ROOT / "templates" / "decks").glob("*/specs/*.json")):
        try:
            slide_spec = json.loads(spec_path.read_text(encoding="utf-8"))
            svg = module.render(slide_spec)
        except Exception as exc:  # noqa: BLE001 - any render failure should fail validation
            fail(f"renderer failed on {spec_path.relative_to(ROOT)}: {exc}")
        if "<svg" not in svg:
            fail(f"renderer produced invalid output for {spec_path.relative_to(ROOT)}")


def validate_demo_deck() -> None:
    """The committed HTML deck must match a fresh build from its manifest."""
    module_path = ROOT / "scripts" / "build_html_deck.py"
    spec_loader = importlib.util.spec_from_file_location("build_html_deck", module_path)
    module = importlib.util.module_from_spec(spec_loader)
    spec_loader.loader.exec_module(module)
    manifest = json.loads((ROOT / "examples" / "demo-deck.json").read_text(encoding="utf-8"))
    spec_paths = [ROOT / "examples" / p for p in manifest["slides"]]
    fresh = module.build_deck(spec_paths, manifest.get("title", "Slide Deck"))
    committed = (ROOT / "examples" / "demo-deck.html").read_text(encoding="utf-8")
    if fresh != committed:
        fail("stale demo deck: regenerate examples/demo-deck.html with scripts/build_html_deck.py")


def validate_demo_report() -> None:
    """The committed HTML report must match a fresh build from its Markdown source.

    Unlike ``validate_demo_deck`` (which imports ``build_html_deck`` and calls its
    ``build_deck`` function directly), this shells out to the documented CLI
    (``python3 scripts/build_html_report.py input.md -o report.html``). That
    keeps the freshness check pinned to the one public contract for the report
    builder rather than to an internal function name/signature.
    """
    script_path = ROOT / "scripts" / "build_html_report.py"
    source_path = ROOT / "examples" / "demo-report.md"
    committed_path = ROOT / "examples" / "demo-report.html"
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = Path(tmp_dir) / "demo-report.html"
        result = subprocess.run(
            [sys.executable, str(script_path), str(source_path), "-o", str(output_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            fail(
                "build_html_report.py failed on examples/demo-report.md: "
                f"{result.stderr.strip()}"
            )
        fresh = output_path.read_text(encoding="utf-8")
    committed = committed_path.read_text(encoding="utf-8")
    if fresh != committed:
        fail("stale demo report: regenerate examples/demo-report.html with scripts/build_html_report.py")


def validate_demo_script() -> None:
    """The committed speaker script must match a fresh build from the
    board-update-ja deck template -- the same deck-manifest shape
    ``validate_demo_deck`` checks (imports the builder module directly and
    calls its public build function), not the report builder's Markdown
    source flow ``validate_demo_report`` shells out to.
    """
    module_path = ROOT / "scripts" / "build_speaker_script.py"
    spec_loader = importlib.util.spec_from_file_location("build_speaker_script", module_path)
    module = importlib.util.module_from_spec(spec_loader)
    spec_loader.loader.exec_module(module)

    manifest_path = ROOT / "templates" / "decks" / "board-update-ja" / "deck.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec_paths = [manifest_path.parent / p for p in manifest["slides"]]
    fresh = module.build_script(spec_paths, manifest.get("title", "Slide Deck"), "ja")
    committed = (ROOT / "examples" / "demo-script.html").read_text(encoding="utf-8")
    if fresh != committed:
        fail(
            "stale demo script: regenerate examples/demo-script.html with "
            "scripts/build_speaker_script.py --manifest templates/decks/board-update-ja/deck.json "
            "-o examples/demo-script.html --lang ja"
        )


def validate_demo_article() -> None:
    """The committed slide article must match a fresh build from the
    board-update deck template, mirroring ``validate_demo_deck``'s
    import-and-call-directly approach."""
    module_path = ROOT / "scripts" / "build_html_article.py"
    spec_loader = importlib.util.spec_from_file_location("build_html_article", module_path)
    module = importlib.util.module_from_spec(spec_loader)
    spec_loader.loader.exec_module(module)

    manifest_path = ROOT / "templates" / "decks" / "board-update" / "deck.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spec_paths = [manifest_path.parent / p for p in manifest["slides"]]
    lead = manifest.get("lead") or manifest.get("description", "")
    series = manifest.get("series", "")
    fresh = module.build_article(
        spec_paths, manifest.get("title", "Untitled"), lead, "en", series=series
    )
    committed = (ROOT / "examples" / "demo-article.html").read_text(encoding="utf-8")
    if fresh != committed:
        fail(
            "stale demo article: regenerate examples/demo-article.html with "
            "scripts/build_html_article.py --manifest templates/decks/board-update/deck.json "
            "-o examples/demo-article.html"
        )


def main() -> None:
    validate_required_files()
    validate_skill_frontmatter()
    validate_manifest()
    validate_no_stale_or_risky_text()
    validate_demo_deck()
    validate_demo_report()
    validate_demo_script()
    validate_demo_article()
    validate_renderer()
    print("OK: skill package passed validation")


if __name__ == "__main__":
    main()
