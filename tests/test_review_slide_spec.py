from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_reviewer():
    module_path = ROOT / "scripts" / "review_slide_spec.py"
    spec = importlib.util.spec_from_file_location("review_slide_spec", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


reviewer = load_reviewer()


class ReviewSlideSpecTests(unittest.TestCase):
    def test_review_accepts_bold_label_section_format(self) -> None:
        text = """\
# Board Update Slide Spec

## Slide 1

**Strategic question:** Should the board approve implementation capacity investment?

**Insight headline:** Growth is constrained by delivery capacity.

**Recommended visualization:** Executive summary strip.

**Slide spec:**
- Canvas: 16:9 landscape.
- Layout: three insight blocks.
- Source note: User-provided data; assumptions noted below.

**Data and assumptions:**
- $15.0M Q4 ARR from user-provided internal metrics.
- Assumption: implementation forecast is directional.

**Quality check:** Board reader, clear decision, color-independent labels, not affiliated, original user-provided data.
"""

        total, issues, _scores = reviewer.score_spec(text)

        self.assertGreaterEqual(total, 18)
        self.assertFalse(any("Missing sections" in issue for issue in issues))

    def test_review_flags_overconfident_universal_claims(self) -> None:
        text = """\
## Strategic question
Should we launch globally?

## Insight headline
This is guaranteed to be the best option for all users.

## Recommended visualization
Benchmark table.

## Slide spec
- Canvas: 16:9
- Layout: table
- Source note: User-provided data; assumptions noted below.

## Data and assumptions
- 42% adoption from user-provided pilot data.
- Assumption: pilot users represent the market.

## Quality check
- Not affiliated; original, user-provided data.
"""

        _total, issues, _scores = reviewer.score_spec(text)

        self.assertTrue(any("Overconfident universal claim" in issue for issue in issues))

    def test_review_flags_missing_reader_or_accessibility_notes(self) -> None:
        text = """\
## Strategic question
Should we approve the rollout?

## Insight headline
Approve the rollout after sequencing capacity.

## Recommended visualization
Waterfall with implication box.

## Slide spec
- Canvas: 16:9
- Layout: waterfall
- Source note: User-provided data; assumptions noted below.

## Data and assumptions
- $10M baseline, +$3M expansion, -$1M churn.
- Assumption: values are unaudited user-provided estimates.

## Quality check
- Not affiliated; original, user-provided data.
"""

        _total, issues, _scores = reviewer.score_spec(text)

        self.assertTrue(any("Reader fit" in issue for issue in issues))
        self.assertTrue(any("Accessibility" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
