"""Source and reproducibility contracts for the original Project Relay example.

The reference data is synthetic.  These tests intentionally exercise only the
public builders; there is no example-specific compiler path.
"""
from __future__ import annotations

import base64
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "interactive-deck"
FIXTURES = ROOT / "examples" / "interactive-fixtures"
BUILD_CLASSIC = ROOT / "scripts" / "build_html_deck.py"
BUILD_INTERACTIVE = ROOT / "scripts" / "build_interactive_deck.py"

SLIDE_IDS = [
    "relay-cover",
    "relay-pilot-thesis",
    "relay-late-job-evidence",
    "relay-route-priority",
    "relay-adoption-value",
    "relay-readiness-score",
    "relay-twelve-week-plan",
    "relay-decision",
]

TITLES = [
    "Project Relay",
    "Approve a $0.6m cap; start with North",
    "Dispatch causes 61% of delays; fix it first",
    "North leads; staffing sets the second route",
    "55% adoption clears the $1.8m hurdle",
    "Manager capacity keeps readiness above 70",
    "The Week 6 review decides whether East starts",
    "Approve the cap; gate East at Week 6",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_builder(script: Path, manifest: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            str(script),
            "--manifest",
            str(manifest),
            "-o",
            str(output),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def decode_envelope(html: str) -> dict:
    match = re.search(
        r'<div id="idrt-deck-data" hidden data-encoding="base64url-json-v1">([A-Za-z0-9_-]+)</div>',
        html,
    )
    if match is None:
        raise AssertionError("interactive envelope not found")
    token = match.group(1)
    token += "=" * ((4 - len(token) % 4) % 4)
    return json.loads(base64.urlsafe_b64decode(token).decode("utf-8"))


def provenance_records(value: object):
    if isinstance(value, dict):
        if "provenance" in value:
            yield value["provenance"]
        for child in value.values():
            yield from provenance_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from provenance_records(child)


class ProjectRelaySourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load(EXAMPLE / "deck.json")
        self.entries = self.manifest["slides"]
        self.specs = [load(EXAMPLE / entry["spec"]) for entry in self.entries]
        self.scenes = {
            index + 1: load(EXAMPLE / entry["scene"])
            for index, entry in enumerate(self.entries)
            if "scene" in entry
        }

    def test_exact_eight_page_story_and_scene_placement(self) -> None:
        self.assertEqual(self.manifest["title"], "Project Relay")
        self.assertEqual(self.manifest["lang"], "en")
        self.assertEqual([entry["id"] for entry in self.entries], SLIDE_IDS)
        self.assertEqual([spec.get("title", spec.get("headline")) for spec in self.specs], TITLES)
        self.assertEqual(set(self.scenes), {3, 4, 5, 6})
        self.assertEqual(
            [self.scenes[page]["type"] for page in (3, 4, 5, 6)],
            ["evidence_only", "state_toggle", "slider_model", "score_model"],
        )
        for page in (1, 2, 7, 8):
            self.assertNotIn("scene", self.entries[page - 1])

    def test_action_titles_stand_alone_without_redundant_header_subtitles(self) -> None:
        self.assertTrue(
            all("subline" not in spec for spec in self.specs[1:]),
            "Project Relay action titles must not be followed by a second, redundant assertion",
        )

    def test_exact_numeric_and_decision_contracts(self) -> None:
        evidence, routes, adoption, readiness = (self.scenes[page] for page in (3, 4, 5, 6))
        self.assertEqual(evidence["initialState"], {"evidence": "closed"})
        self.assertEqual(self.specs[2]["pattern"], "gap")
        self.assertEqual([item["value"] for item in self.specs[2]["items"]], [61, 24, 15])
        self.assertEqual(sum(item["value"] for item in self.specs[2]["items"]), 100)
        self.assertEqual(self.specs[2]["value_domain"], [0, 100])

        self.assertEqual(routes["initialState"], {"route-scenario": "base"})
        route_values = {
            state["id"]: [
                (item["id"], item["rank"], item["metric"]["value"])
                for item in state["view"]["items"]
            ]
            for state in routes["states"]
        }
        self.assertEqual(
            route_values,
            {
                "base": [("north", 1, 86), ("central", 2, 78), ("east", 3, 73)],
                "constrained": [("north", 1, 82), ("east", 2, 76), ("central", 3, 64)],
            },
        )
        for state in routes["states"]:
            self.assertEqual(state["view"]["domain"], [0, 100])
            self.assertEqual(state["view"]["baseline"], 0)

        self.assertEqual(adoption["initialState"], {"adoption": 55})
        self.assertEqual(adoption["printState"], {"adoption": 55})
        control = adoption["controls"][0]
        self.assertEqual((control["min"], control["max"], control["step"]), (30, 80, 5))
        self.assertEqual(adoption["model"]["intercept"]["value"], -1.5)
        self.assertEqual(adoption["model"]["terms"]["adoption"]["coefficient"], 0.06)
        self.assertEqual(adoption["decisionContract"]["threshold"]["value"], 1.8)
        self.assertEqual(adoption["decisionContract"]["operator"], "gte")
        intercept = Decimal(str(adoption["model"]["intercept"]["value"]))
        coefficient = Decimal(str(adoption["model"]["terms"]["adoption"]["coefficient"]))
        self.assertEqual(
            [intercept + coefficient * Decimal(value) for value in (30, 55, 80)],
            [Decimal("0.3"), Decimal("1.8"), Decimal("3.3")],
        )

        self.assertEqual(
            readiness["initialState"],
            {
                "frequency": 24,
                "data-quality": "standard",
                "manager-capacity": "available",
                "integration-depth": "core",
            },
        )
        self.assertEqual(readiness["decisionContract"]["threshold"]["value"], 70)
        self.assertEqual(
            [(band["id"], band["min"], band["max"], band["label"]) for band in readiness["model"]["bands"]],
            [
                ("defer", 16, 50, "Defer"),
                ("prepare", 50, 70, "Prepare"),
                ("pilot-ready", 70, 98, "Pilot-ready"),
            ],
        )
        contributions = {
            item["control"]: {str(row["input"]): row["points"] for row in item["values"]}
            for item in readiness["model"]["contributions"]
        }
        base = readiness["initialState"]
        base_score = sum(contributions[key][str(value)] for key, value in base.items())
        no_manager = {**base, "manager-capacity": "unavailable"}
        no_manager_score = sum(
            contributions[key][str(value)] for key, value in no_manager.items()
        )
        self.assertEqual((base_score, no_manager_score), (72, 54))

    def test_every_source_is_visibly_illustrative_with_complete_assumptions(self) -> None:
        for page, spec in enumerate(self.specs, start=1):
            with self.subTest(page=page):
                self.assertEqual(spec["classification"], "Illustrative")
                if page != 1:
                    self.assertIn("Illustrative", spec["source"])
        for page, scene in self.scenes.items():
            with self.subTest(page=page):
                self.assertIn("Illustrative", json.dumps(scene, ensure_ascii=False))
                assumption_ids = {item["id"] for item in scene.get("assumptions", [])}
                self.assertTrue(assumption_ids)
                records = list(provenance_records(scene))
                if scene["type"] in ("state_toggle", "slider_model", "score_model"):
                    self.assertTrue(records)
                for record in records:
                    self.assertEqual(record["basis"], "illustrative")
                    self.assertTrue(set(record.get("assumptionRefs", [])).issubset(assumption_ids))
                    self.assertTrue(record.get("assumptionRefs"))

    def test_east_begins_only_after_the_combined_week_six_gate(self) -> None:
        plan = self.specs[6]
        self.assertEqual(len(plan['gates']), 1)
        gate = plan['gates'][0]
        self.assertEqual(gate['period'], 2)
        self.assertIn('55%', gate['label'])
        self.assertIn('70', gate['label'])
        east = next(bar for bar in plan['bars'] if 'East' in bar['label'])
        north = next(bar for bar in plan['bars'] if 'North' in bar['label'])
        self.assertGreater(east['start'], gate['period'])
        self.assertEqual(north['start'], 0)
        self.assertIn('technician-constraint', plan['annotation'])
        self.assertIn('separate decision', plan['annotation'])
        self.assertEqual([step['timing'] for step in self.specs[7]['next_steps']],
                         ['Week 1', 'Week 6', 'Week 12'])

    def test_storyboard_ledgers_and_demo_are_complete(self) -> None:
        storyboard = (EXAMPLE / "storyboard.md").read_text(encoding="utf-8")
        ledger = (EXAMPLE / "data-ledger.md").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"^\| [1-8] \|", storyboard, flags=re.MULTILINE)), 8)
        for heading in ("Evidence", "Main interaction", "May change", "Must not change"):
            self.assertIn(heading, storyboard)
        for title in TITLES:
            self.assertIn(title, storyboard)
        for datum in (
            "late-cause-dispatch",
            "route-base-north",
            "adoption-value-formula",
            "readiness-manager",
            "pilot-funding",
        ):
            self.assertIn(datum, ledger)
        ledger_values = {}
        for line in ledger.splitlines():
            if not line.startswith("|") or line.startswith("| ---"):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) == 10 and cells[0] != "Datum ID":
                ledger_values[cells[0]] = cells[1]
        self.assertEqual(
            {key: ledger_values[key] for key in (
                "pilot-funding",
                "late-cause-dispatch",
                "route-base-north",
                "route-constrained-east",
                "adoption-value-formula",
                "adoption-value-gate",
                "readiness-base",
                "readiness-no-manager",
                "readiness-gate",
            )},
            {
                "pilot-funding": "0.6",
                "late-cause-dispatch": "61",
                "route-base-north": "86",
                "route-constrained-east": "76",
                "adoption-value-formula": "−1.5 + 0.06 × adoption",
                "adoption-value-gate": "1.8 at 55",
                "readiness-base": "72",
                "readiness-no-manager": "54",
                "readiness-gate": "70",
            },
        )

        steps = [step for scene in self.scenes.values() for step in scene.get("demo", [])]
        self.assertEqual(len(steps), 6)
        self.assertEqual(len({step["stepKey"] for step in steps}), 6)
        self.assertEqual(
            [(step["action"], step.get("control"), step.get("value")) for step in steps],
            [
                ("openEvidence", None, None),
                ("select", "route-scenario", "constrained"),
                ("set", "adoption", 50),
                ("set", "adoption", 60),
                ("select", "manager-capacity", "unavailable"),
                ("select", "manager-capacity", "available"),
            ],
        )

    def test_authored_public_sources_have_no_private_or_remote_material(self) -> None:
        paths = [
            path
            for path in EXAMPLE.rglob("*")
            if path.is_file() and path.suffix in {".json", ".md"}
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for forbidden in (
            "/Users/",
            "file://",
            "http://",
            "https://",
            "Uchita",
            "McKinsey & Company",
        ):
            self.assertNotIn(forbidden, text)


class ProjectRelayArtifactTests(unittest.TestCase):
    def test_checked_in_html_matches_two_clean_public_builds(self) -> None:
        manifest = EXAMPLE / "deck.json"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            classic_a, classic_b = root / "classic-a.html", root / "classic-b.html"
            live_a, live_b = root / "live-a.interactive.html", root / "live-b.interactive.html"
            for script, outputs in (
                (BUILD_CLASSIC, (classic_a, classic_b)),
                (BUILD_INTERACTIVE, (live_a, live_b)),
            ):
                for output in outputs:
                    completed = run_builder(script, manifest, output)
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            self.assertEqual(classic_a.read_bytes(), (EXAMPLE / "deck.html").read_bytes())
            self.assertEqual(live_a.read_bytes(), (EXAMPLE / "deck.interactive.html").read_bytes())

            classic = classic_a.read_text(encoding="utf-8")
            self.assertNotIn("idrt-deck-data", classic)
            live = live_a.read_text(encoding="utf-8")
            self.assertIn("Content-Security-Policy", live)
            self.assertNotRegex(
                live,
                r'<(?:script|img|iframe|link)[^>]+(?:src|href)=["\']https?://',
            )
            for communication_api in ("fetch(", "XMLHttpRequest", "WebSocket(", "sendBeacon("):
                self.assertNotIn(communication_api, live)
            envelope = decode_envelope(live)
            self.assertEqual([slide["slideId"] for slide in envelope["slides"]], SLIDE_IDS)
            self.assertEqual(sum(slide.get("scene") is not None for slide in envelope["slides"]), 4)

    def test_failed_build_preserves_prior_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "deck.interactive.html"
            destination.write_bytes(b"prior-complete-artifact")
            broken = root / "deck.json"
            broken.write_text(
                json.dumps({"title": "Broken", "lang": "en", "slides": [{"id": "bad", "spec": "missing.json", "scene": "missing-scene.json"}]}),
                encoding="utf-8",
            )
            completed = run_builder(BUILD_INTERACTIVE, broken, destination)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(destination.read_bytes(), b"prior-complete-artifact")


class IndependentFixtureTests(unittest.TestCase):
    EXPECTED = {
        "drilldown": "drilldown",
        "accordion": "accordion",
        "tooltip": "slider_model",
    }

    def test_each_fixture_is_one_scene_and_builds_from_its_own_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_root = Path(directory)
            for name, scene_type in self.EXPECTED.items():
                with self.subTest(name=name):
                    root = FIXTURES / name
                    manifest = load(root / "deck.json")
                    self.assertEqual(len(manifest["slides"]), 1)
                    entry = manifest["slides"][0]
                    self.assertEqual(load(root / entry["scene"])["type"], scene_type)
                    output = output_root / f"{name}.interactive.html"
                    completed = run_builder(BUILD_INTERACTIVE, root / "deck.json", output)
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    envelope = decode_envelope(output.read_text(encoding="utf-8"))
                    self.assertEqual(sum(slide.get("scene") is not None for slide in envelope["slides"]), 1)
                    self.assertIn("Illustrative", output.read_text(encoding="utf-8"))

    def test_fixture_component_contracts_are_minimal_and_exact(self) -> None:
        drilldown = load(FIXTURES / "drilldown" / "scenes" / "scene.json")
        self.assertEqual([panel["id"] for panel in drilldown["panels"]], ["method", "boundary"])
        self.assertEqual(drilldown["initialState"], {"panel": None})

        accordion = load(FIXTURES / "accordion" / "scenes" / "scene.json")
        self.assertTrue(accordion["allowNone"])
        self.assertEqual([item["id"] for item in accordion["items"]], ["handoff", "exception", "owner"])

        tooltip = load(FIXTURES / "tooltip" / "scenes" / "scene.json")
        self.assertEqual((tooltip["controls"][0]["min"], tooltip["controls"][0]["max"], tooltip["controls"][0]["step"]), (1, 3, 1))
        self.assertEqual(
            [(entry["input"], entry["output"]["value"]) for entry in tooltip["model"]["entries"]],
            [(1, 3), (2, 8), (3, 13)],
        )
        self.assertEqual(tooltip["view"]["domain"], [0, 15])

    def test_fixture_scene_path_cannot_escape_its_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            fixture = temp / "fixture"
            shutil.copytree(FIXTURES / "drilldown", fixture)
            outside = temp / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            manifest = load(fixture / "deck.json")
            manifest["slides"][0]["scene"] = "../outside.json"
            (fixture / "deck.json").write_text(
                json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
            )
            output = temp / "escaped.interactive.html"
            completed = run_builder(BUILD_INTERACTIVE, fixture / "deck.json", output)
            self.assertNotEqual(completed.returncode, 0)
            self.assertFalse(output.exists())

    def test_main_reference_remains_exactly_four_scenes(self) -> None:
        manifest = load(EXAMPLE / "deck.json")
        self.assertEqual(sum("scene" in entry for entry in manifest["slides"]), 4)


if __name__ == "__main__":
    unittest.main()
