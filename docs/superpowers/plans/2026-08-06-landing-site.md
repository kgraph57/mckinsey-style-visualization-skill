# Landing Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a single-page GitHub Pages site (chaos→clarity Three.js hero + live embedded demos + spec-paired gallery) that drives installs and stars, with all artifacts committed and CI-drift-checked.

**Architecture:** `docs/` is the Pages root. `scripts/build_site.py` (stdlib) syncs committed repo artifacts into `docs/site/artifacts/` and verifies freshness with `--check` in CI. The page is no-build static HTML/CSS/ES-modules; three.js is vendored. Section markup is produced as disjoint fragments by parallel agents and merged into `docs/index.html` by the integrator (one file owner), so no two agents edit the same file.

**Tech Stack:** Python 3 stdlib (build + tests), static HTML/CSS, ES modules + importmap, vendored three.js.

**Spec:** `docs/superpowers/specs/2026-08-06-landing-site-design.md`

**Branch:** all implementation lands on `site/landing` (created from main after this plan is committed). Best-of-N hero worktrees branch off `site/landing` after Task 3.

**Section CSS namespacing rule:** every section's classes are prefixed with its id (`hd-` hero, `ld-` live-deck, `pl-` pipeline, `gal-` gallery, `cjk-`, `md-` modes, `ro-` roast, `st-` start, `ft-` footer). No element styles outside own namespace; shared primitives live only in `base.css` (owned by Task 4).

---

### Task 1: `scripts/build_site.py` + `tests/test_build_site.py`

**Files:**

- Create: `scripts/build_site.py`
- Test: `tests/test_build_site.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_build_site.py
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def load_module():
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class BuildSiteTests(unittest.TestCase):
    def setUp(self):
        self.mod = load_module()

    def test_build_copies_rendered_svgs(self):
        with tempfile.TemporaryDirectory() as td:
            out = self.mod.build(ROOT, Path(td))
            svgs = sorted((Path(td) / "rendered").glob("*.svg"))
            self.assertEqual(len(svgs), len(list((ROOT / "assets" / "rendered").glob("*.svg"))))

    def test_build_creates_ja_deck(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            html = (Path(td) / "ja-deck.html").read_text(encoding="utf-8")
            self.assertIn("取締役会", html)

    def test_manifest_entries(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            manifest = json.loads((Path(td) / "gallery-manifest.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(manifest), 20)
            for entry in manifest:
                self.assertIn("file", entry)
                self.assertIn("pattern", entry)
                self.assertIn("headline", entry)
            wf = [e for e in manifest if e["file"] == "arr-waterfall.svg"]
            self.assertEqual(wf[0]["pattern"], "waterfall")

    def test_check_passes_on_fresh_build(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            self.assertEqual(self.mod.check(ROOT, Path(td)), [])

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as td:
            self.mod.build(ROOT, Path(td))
            victim = Path(td) / "rendered" / "arr-waterfall.svg"
            victim.write_text(victim.read_text(encoding="utf-8") + " ", encoding="utf-8")
            diffs = self.mod.check(ROOT, Path(td))
            self.assertTrue(any("arr-waterfall.svg" in d for d in diffs))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_build_site -v`
Expected: FAIL — `scripts/build_site.py` does not exist.

- [ ] **Step 3: Implement `scripts/build_site.py`**

Requirements (implementation must satisfy the tests and these rules):

- `ROOT = Path(__file__).resolve().parent.parent`
- `ARTIFACT_COPY` mapping: `assets/rendered/*.svg` → `<dest>/rendered/`; `examples/render-specs/*.json` → `<dest>/specs/`; each of `examples/demo-deck.html`, `examples/demo-report.html`, `examples/demo-article.html`, `examples/demo-script.html` → `<dest>/`.
- JA deck: read `templates/decks/board-update-ja/deck.json` (`{title, slides}`), resolve slide paths relative to the manifest dir, then render via `build_deck` imported from `scripts/build_html_deck.py` with `importlib.util.spec_from_file_location` (same pattern as `load_renderer()` in that file). Write `<dest>/ja-deck.html`.
- Manifest: for each `<dest>/specs/*.json` (sorted by filename), entry `{"file": "<svg name>", "pattern": spec["pattern"], "headline": spec.get("headline") or spec.get("title") or stem}`. SVG name = spec stem + `.svg`. Only include entries whose SVG exists in `<dest>/rendered/`. Write `<dest>/gallery-manifest.json` (UTF-8, `ensure_ascii=False`, indent 2).
- `build(root, dest) -> Path`: performs all of the above, returns dest.
- `check(root, dest) -> list[str]`: rebuilds into a `tempfile.TemporaryDirectory`, walks both trees, returns sorted list of human-readable drift strings (missing file, extra file, byte mismatch). Empty list = fresh.
- CLI: `python3 scripts/build_site.py` builds into `docs/site/artifacts/` (default); `--check` runs check against `docs/site/artifacts/`, prints `OK: site artifacts fresh` and exits 0, or prints each drift line and exits 1.
- Stdlib only. `if __name__ == "__main__": main()` guard.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_build_site -v`
Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/build_site.py tests/test_build_site.py
git commit -m "site: add build_site.py artifact sync with --check"
```

### Task 2: Generate committed artifacts

**Files:**

- Create: `docs/site/artifacts/**` (generated)

- [ ] **Step 1: Run the build**

Run: `python3 scripts/build_site.py`
Expected output ends with: `OK: built site artifacts at docs/site/artifacts`

- [ ] **Step 2: Verify check passes**

Run: `python3 scripts/build_site.py --check`
Expected: `OK: site artifacts fresh`

- [ ] **Step 3: Commit**

```bash
git add docs/site/artifacts/
git commit -m "site: commit generated artifacts (gallery, specs, demo decks)"
```

### Task 3: CI drift check

**Files:**

- Modify: `.github/workflows/ci.yml` (append one step after "Validate package")

- [ ] **Step 1: Add the step**

```yaml
- name: Check site artifacts are fresh
  run: python3 scripts/build_site.py --check
```

- [ ] **Step 2: Verify locally**

Run: `python3 -m unittest discover -s tests && python3 scripts/validate_skill.py && python3 scripts/build_site.py --check`
Expected: all three green.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: assert site artifacts stay fresh"
```

**CHECKPOINT:** create best-of-N hero worktrees from this commit. Hero concepts are standalone `hero.html` + `hero.js` demos at the worktree root, each using `docs/site/artifacts/rendered/arr-waterfall.svg` as the convergence target. (Dispatch details in "Execution" below.)

### Task 4: Page skeleton — `docs/index.html`, `tokens.css`, `base.css`

**Files:**

- Create: `docs/index.html`
- Create: `docs/site/css/tokens.css`
- Create: `docs/site/css/base.css`

- [ ] **Step 1: `tokens.css`** — CSS custom properties mirroring `references/style-system.md`:

```css
:root {
  --navy: #15296b;
  --blue: #2563eb;
  --ink: #000000;
  --grey-700: #374151;
  --grey-500: #6b7280;
  --grey-300: #d1d5db;
  --fill: #f3f4f6;
  --tint: #eff3fb;
  --risk: #b91c1c;
  --paper: #ffffff;
  --serif:
    Georgia, "Times New Roman", "Hiragino Mincho ProN", "Yu Mincho", serif;
  --sans:
    -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial,
    "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
  --u: 8px;
  --measure: 72rem;
}
```

- [ ] **Step 2: `base.css`** — box-sizing reset, `html { scroll-behavior: smooth }` guarded by reduced-motion, body (sans, ink on paper, `line-height: 1.6`), headings (`h1/h2` serif), `.wrap { max-width: var(--measure); margin-inline: auto; padding-inline: calc(var(--u) * 3) }`, `.kicker` (sans, 12px, uppercase, letter-spacing 0.14em, grey-500), focus-visible outlines (2px `--blue`), section vertical rhythm (`padding-block: calc(var(--u) * 12)`), `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important } }`.

- [ ] **Step 3: `docs/index.html` skeleton** — `<!doctype html>`, `<html lang="en">`, head with charset/viewport, title "Strategy Consulting Visualization Skill — Messy notes in. Board-ready slides out.", meta description, OGP tags (`og:title`, `og:description`, `og:image` → `site/og.png`, `twitter: card summary_large_image`), importmap `{"imports": {"three": "./site/vendor/three.module.js"}}`, stylesheet links, `<script type="module" src="./site/js/main.js"></script>` deferred by module semantics. Body: skip link, slim header (wordmark + nav anchors + GitHub star link), then `<section id="...">` shells in spec order (`hero`, `live-deck`, `pipeline`, `gallery`, `cjk`, `modes`, `roast`, `start`) each containing its final `h2` and `.kicker`, and `<footer id="footer">`. Section bodies are filled by Tasks 6–10 via fragment merge.

- [ ] **Step 4: Commit**

```bash
git add docs/index.html docs/site/css/
git commit -m "site: page skeleton, tokens, base styles"
```

### Task 5: `tests/test_site.py` static site validation

**Files:**

- Test: `tests/test_site.py`

- [ ] **Step 1: Write the test** (passes only after Tasks 4–10 complete; keep it skipped until integration, then unskip)

Behavior: parse `docs/index.html` with `html.parser.HTMLParser`. Collect `src`/`href` from `img`, `script`, `link`, `iframe`. Assert: (a) every relative reference resolves to an existing file under `docs/`; (b) no `http://`/`https://` in `src`/`href` except links in `<a>`; (c) required ids present: `hero live-deck pipeline gallery cjk modes roast start footer`; (d) `og:image` meta present; (e) `site/vendor/three.module.js` exists; (f) every `iframe src` file exists. Guard with `@unittest.skipUnless((ROOT / "docs" / "index.html").exists(), "site not built yet")` so it is inert until the page exists — no skip-flag churn needed.

- [ ] **Step 2: Run** — `python3 -m unittest tests.test_site -v` → PASS (or SKIP before integration).

- [ ] **Step 3: Commit** `git commit -m "test: static site reference validation"`

### Task 6: Hero (integrates best-of-N winner)

**Files:**

- Create: `docs/site/js/hero.js`
- Modify: `docs/index.html` (hero section body)

Contract every concept must satisfy:

- `export function initHero(container, { reducedMotion })` returns `{ dispose() }`.
- Fallback: if `reducedMotion` or no WebGL, container shows `<img src="./site/artifacts/rendered/arr-waterfall.svg" alt="Rendered ARR waterfall slide">` inside a framed figure — no canvas at all.
- Scroll driver: `main.js` maps the hero section's scroll progress (0..1 across its 200vh pin) to `hero.setProgress(t)`; concept implements `setProgress`.
- Palette only from `tokens.css` custom properties (read via `getComputedStyle`).
- No network requests; import only `three`.

- [ ] **Step 1: Adapt winning concept to the contract in `hero.js`.**
- [ ] **Step 2: Wire `main.js`: init on DOMContentLoaded, scroll listener (passive) + rAF throttle, IntersectionObserver pause when off-screen.**
- [ ] **Step 3: Manual verify: open `docs/index.html` in browser; hero animates on scroll; reduced-motion OS setting shows static poster.**
- [ ] **Step 4: Commit** `git commit -m "site: chaos-to-clarity hero (concept <A|B|C>)"`

### Task 7: Live deck + pipeline sections

**Files:**

- Create: `docs/site/sections/live-deck.html`, `docs/site/sections/pipeline.html` (fragments for merge)
- Create: `docs/site/css/sections/live-deck.css`, `docs/site/css/sections/pipeline.css`

- [ ] **Step 1: live-deck** — `.ld-frame` figure: `<iframe src="./site/artifacts/demo-deck.html" title="Animated demo deck" loading="lazy">`, aspect-ratio 16/9, border `var(--grey-300)`, caption: "A real deck built by this repo. Click it, then drive it with arrow keys — press p to print to PDF."
- [ ] **Step 2: pipeline** — four-step horizontal flow (notes → spec JSON → SVG slides → HTML deck/PDF) as inline SVG or CSS boxes with arrows; monospace for `spec JSON`; on mobile it stacks vertically.
- [ ] **Step 3: Hand to integrator** (merged into `docs/index.html` + `sections.css`).

### Task 8: Gallery + lightbox

**Files:**

- Create: `docs/site/sections/gallery.html` (fragment)
- Create: `docs/site/js/gallery.js`, `docs/site/js/lightbox.js`
- Create: `docs/site/css/sections/gallery.css`

- [ ] **Step 1: gallery.js** — `fetch("./site/artifacts/gallery-manifest.json")`, render responsive grid (`repeat(auto-fill, minmax(260px, 1fr))`) of `<img loading="lazy" src="./site/artifacts/rendered/<file>">` cards with pattern tag + headline caption.
- [ ] **Step 2: lightbox.js** — dialog element; left = SVG at full width, right = fetched spec JSON pretty-printed in `<pre>` (monospace, scrollable); Esc/backdrop close; focus trap; prev/next arrows.
- [ ] **Step 3: gallery.css** — card hover lift (translateY -2px, token shadow), lightbox layout (grid 3:2 on desktop, stacked on mobile).
- [ ] **Step 4: Hand to integrator.**

### Task 9: CJK + output modes + roast + start + footer sections

**Files:**

- Create: `docs/site/sections/{cjk,modes,roast,start,footer}.html` (fragments)
- Create: `docs/site/css/sections/{cjk,modes,roast,start,footer}.css`

- [ ] **Step 1: cjk** — `.cjk-frame` iframe `./site/artifacts/ja-deck.html`; copy: CJK wraps measured per fullwidth character; dedicated profiles for 稟議書, 役員会資料, 週報, 学会抄録.
- [ ] **Step 2: modes** — four cards linking `./site/artifacts/demo-{deck,report,script,article}.html` (open in new tab): Deck / Report / Speaker script / Article, one line each from README sections.
- [ ] **Step 3: roast** — five score cards, exact data: Tufte 5.5 ("Meaningless decorated rectangles baked into the renderer"), Zelazny 6.5 ("The flagship example violates its own headline rule"), Vignelli × Müller-Brockmann 6 ("A corporate template, not a design system"), Alan Smith 5.5 ("The waterfall draws off-canvas on negative bridges"), Modern design engineering 5.5 ("2016 visuals wearing a 2020s spec sheet"); closing line "Then we shipped every fix." linking to CHANGELOG.md on GitHub.
- [ ] **Step 4: start** — terminal-styled `<pre>` with the three README commands (clone to `~/.claude/skills/...`, render one slide, build deck); copy-to-clipboard button (`navigator.clipboard`, fallback `execCommand`).
- [ ] **Step 5: footer** — star CTA linking `https://github.com/kgraph57/mckinsey-style-visualization-skill`, MIT note, disclaimer sentence verbatim from README ("This is an independent skill package. It is not affiliated with, endorsed by, or sponsored by McKinsey & Company, Boston Consulting Group, Bain & Company, or any other consulting firm.").
- [ ] **Step 6: Hand to integrator.**

### Task 10: Vendor three.js + OGP image

**Files:**

- Create: `docs/site/vendor/three.module.js`
- Create: `docs/site/og.png`

- [ ] **Step 1: Vendor three.js** — download the pinned release module build (record exact version + URL + sha256 in `docs/site/vendor/THREE-VERSION.txt`), e.g. `curl -L https://unpkg.com/three@0.170.0/build/three.module.js -o docs/site/vendor/three.module.js`, verify size ~600–700KB.
- [ ] **Step 2: OGP** — headless-Chrome screenshot recipe: open `docs/index.html` with reduced-motion emulated at 1200x630, capture hero poster state, save `docs/site/og.png`. (One-time, manual, recorded here.)
- [ ] **Step 3: Commit** `git commit -m "site: vendor three.js, add og image"`

### Task 11: Integration + full verification

**Files:**

- Modify: `docs/index.html` (merge all fragments)

- [ ] **Step 1: Merge fragments** into `docs/index.html`; concatenate section CSS files into `docs/site/css/sections.css` in section order (delete per-section files after merge; spec layout is the committed state).
- [ ] **Step 2:** `python3 -m unittest discover -s tests` → all green (including `test_site`).
- [ ] **Step 3:** `python3 scripts/validate_skill.py && python3 scripts/build_site.py --check` → green.
- [ ] **Step 4: Browser QA matrix** (IDE browser): Chrome + Safari; widths 1440 / 768 / 390; reduced-motion ON (poster shows, no animation); WebGL blocked (poster shows); `file://` open of `docs/index.html` works; screenshot each pass.
- [ ] **Step 5: Commit** `git commit -m "site: integrate sections"`

## Execution

1. Commit this plan to main. Create branch `site/landing`.
2. Tasks 1–3 inline (foundation; best-of-N worktrees need artifacts committed).
3. Dispatch 3 best-of-N hero agents in background (concepts A/B/C per spec) + in parallel dispatch section agents for Tasks 7/8/9 (fragments, disjoint files, instructed NOT to commit).
4. Human gate: pick hero from screenshots.
5. Tasks 4–6, 10; integrate Task 11.
6. code-reviewer + security-reviewer subagents; fix loop.
7. Final report with screenshots. Owner actions after review: merge to main, push, enable Pages (Settings → Pages → Deploy from branch → main /docs), set repo social preview to `docs/site/og.png`.
