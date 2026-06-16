#!/usr/bin/env python3
"""Heuristic review for strategy consulting slide spec markdown files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = [
    "Strategic question",
    "Insight headline",
    "Recommended visualization",
    "Slide spec",
    "Data and assumptions",
    "Quality check",
]

VISUAL_PATTERNS = [
    "waterfall",
    "timeline",
    "gap",
    "benchmark",
    "2x2",
    "matrix",
    "contrast",
    "market",
    "before",
    "after",
    "executive summary",
    "cover",
]

SAFETY_RISKS = [
    "official mckinsey",
    "official bcg",
    "official bain",
    "mckinsey-approved",
    "bcg-approved",
    "bain-approved",
    "mckinsey-certified",
    "bcg-certified",
    "bain-certified",
    "in partnership with mckinsey",
    "in partnership with bcg",
    "in partnership with bain",
]

OVERCONFIDENT_CLAIMS = [
    "always",
    "guaranteed",
    "best option",
    "all users",
    "everyone",
    "no risk",
    "will definitely",
]

READER_FIT_TERMS = [
    "reader",
    "audience",
    "stakeholder",
    "leader",
    "executive",
    "board",
    "operator",
]

ACCESSIBILITY_TERMS = [
    "accessibility",
    "contrast",
    "color",
    "colour",
    "reading order",
    "alt text",
    "plain language",
    "jargon",
    "localization",
    "localisation",
]


def section_present(text: str, section: str) -> bool:
    heading_pattern = rf"^##\s+{re.escape(section)}\s*$"
    bold_label_pattern = rf"^\*\*{re.escape(section)}:\*\*"
    return bool(re.search(heading_pattern, text, re.IGNORECASE | re.MULTILINE)) or bool(
        re.search(bold_label_pattern, text, re.IGNORECASE | re.MULTILINE)
    )


def contains_number(text: str) -> bool:
    return bool(re.search(r"(\$?\d+(?:\.\d+)?\s?(?:%|M|B|T|x|pts|points)?)", text))


def score_spec(text: str) -> tuple[int, list[str], dict[str, int]]:
    lower = text.lower()
    issues: list[str] = []
    scores = {
        "strategy": 0,
        "data_integrity": 0,
        "visual_hierarchy": 0,
        "portability": 0,
        "marketplace_safety": 0,
    }

    missing_sections = [section for section in REQUIRED_SECTIONS if not section_present(text, section)]
    if missing_sections:
        issues.append(f"Missing sections: {', '.join(missing_sections)}")

    if section_present(text, "Strategic question") and section_present(text, "Insight headline"):
        scores["strategy"] += 3
    if any(phrase in lower for phrase in ["recommend", "approve", "sequence", "should be", "decision:"]):
        scores["strategy"] += 2
    if scores["strategy"] < 5:
        issues.append("Strategy could be sharper: make the decision implication explicit.")

    if contains_number(text):
        scores["data_integrity"] += 2
    if any(word in lower for word in ["assumption", "source", "provided", "missing", "not provided"]):
        scores["data_integrity"] += 3
    if scores["data_integrity"] < 5:
        issues.append("Data integrity needs visible values, units, source notes, or assumptions.")

    if any(pattern in lower for pattern in VISUAL_PATTERNS):
        scores["visual_hierarchy"] += 2
    if any(word in lower for word in ["annotation", "primary number", "direct label", "implication box"]):
        scores["visual_hierarchy"] += 2
    if scores["visual_hierarchy"] < 4:
        issues.append("Visual hierarchy needs clearer labels, annotations, or primary numbers.")

    if section_present(text, "Slide spec") and all(word in lower for word in ["canvas", "layout", "source note"]):
        scores["portability"] += 3
    elif section_present(text, "Slide spec"):
        scores["portability"] += 2
        issues.append("Portability is partial: add canvas, layout, and source note details.")
    else:
        issues.append("Portability is weak: add a renderable slide spec.")

    if not any(risk in lower for risk in SAFETY_RISKS):
        scores["marketplace_safety"] += 2
    else:
        issues.append("Marketplace safety risk: remove affiliation, certification, or partnership claims.")
    if any(word in lower for word in ["not affiliated", "original", "no copied", "source-aware", "user-provided"]):
        scores["marketplace_safety"] += 1
    else:
        issues.append("Marketplace safety could improve: add originality or source-awareness language.")

    if any(claim in lower for claim in OVERCONFIDENT_CLAIMS):
        issues.append("Overconfident universal claim: scope the wording to the evidence or show what would change the conclusion.")

    if not any(term in lower for term in READER_FIT_TERMS):
        issues.append("Reader fit is unclear: name the primary audience and the decision, task, or misunderstanding to resolve.")

    if not any(term in lower for term in ACCESSIBILITY_TERMS):
        issues.append("Accessibility is underspecified: check contrast, color independence, reading order, and jargon/localization risk.")

    total = sum(scores.values())
    return total, issues, scores


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a strategy consulting slide spec markdown file.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--min-score", type=int, default=18)
    args = parser.parse_args()

    if not args.path.exists():
        print(f"ERROR: file not found: {args.path}", file=sys.stderr)
        return 2

    text = args.path.read_text(encoding="utf-8")
    total, issues, scores = score_spec(text)

    print(f"Score: {total}/20")
    for name, score in scores.items():
        print(f"- {name.replace('_', ' ').title()}: {score}")

    if issues:
        print("\nIssues:")
        for issue in issues:
            print(f"- {issue}")

    if total < args.min_score:
        print(f"\nDecision: revise; score is below {args.min_score}.")
        return 1

    print(f"\nDecision: pass; score meets {args.min_score}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
