#!/usr/bin/env python3
"""Validate the skill package structure for marketplace readiness."""

from __future__ import annotations

import json
import re
import sys
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
    "references/style-system.md",
    "references/visualization-patterns.md",
    "references/prompt-templates.md",
    "references/quality-rubric.md",
    "references/public-reference-corpus.md",
    "references/iterative-review-loop.md",
    "references/input-triage.md",
    "references/document-type-profiles.md",
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
    "assets/rendered/arr-waterfall.svg",
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

    if fields.get("name") != "strategy-consulting-visualization":
        fail("SKILL.md frontmatter name must be strategy-consulting-visualization")

    description = fields.get("description", "")
    if not description.startswith("Use when "):
        fail("SKILL.md description must start with 'Use when '")
    if len(description) > 500:
        fail("SKILL.md description must be 500 characters or fewer")

    if fields.get("license") != "MIT":
        fail("SKILL.md license must be MIT")

    for reference in [
        "references/visualization-patterns.md",
        "references/style-system.md",
        "references/prompt-templates.md",
        "references/quality-rubric.md",
        "references/public-reference-corpus.md",
        "references/iterative-review-loop.md",
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
        "version": "1.7.0",
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


def main() -> None:
    validate_required_files()
    validate_skill_frontmatter()
    validate_manifest()
    validate_no_stale_or_risky_text()
    print("OK: skill package passed validation")


if __name__ == "__main__":
    main()
