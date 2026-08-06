/* Pyodide harness: runs this repo's actual render_slide_spec.py / build_html_deck.py
   in the browser via WebAssembly. One renderer, everywhere — no JS port, no drift.
   Pyodide is pinned and lazy-loaded from jsDelivr on first Generate. */

const PYODIDE_VERSION = "v0.29.3";
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/${PYODIDE_VERSION}/full/`;

const ARTIFACTS = new URL("../../artifacts/", import.meta.url);

let pyodidePromise = null;

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`failed to load ${src}`));
    document.head.appendChild(script);
  });
}

async function fetchText(path) {
  const res = await fetch(new URL(path, ARTIFACTS));
  if (!res.ok) throw new Error(`failed to fetch ${path}: ${res.status}`);
  return res.text();
}

export function ensurePyodide() {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      await loadScript(`${PYODIDE_BASE}pyodide.js`);
      const pyodide = await globalThis.loadPyodide({ indexURL: PYODIDE_BASE });
      const [renderer, deckBuilder] = await Promise.all([
        fetchText("py/render_slide_spec.py"),
        fetchText("py/build_html_deck.py"),
      ]);
      pyodide.FS.mkdirTree("/py");
      pyodide.FS.writeFile("/py/render_slide_spec.py", renderer);
      pyodide.FS.writeFile("/py/build_html_deck.py", deckBuilder);
      pyodide.runPython("import sys\nsys.path.insert(0, '/py')");
      return pyodide;
    })();
    pyodidePromise.catch(() => {
      pyodidePromise = null; // allow retry after a transient failure
    });
  }
  return pyodidePromise;
}

export function renderSlides(pyodide, slides) {
  pyodide.globals.set("__slide_specs_json", JSON.stringify(slides));
  const resultsJson = pyodide.runPython(
    `
import json
from render_slide_spec import render

__specs = json.loads(__slide_specs_json)
__out = []
for __s in __specs:
    try:
        __out.append({"ok": True, "svg": render(__s)})
    except Exception as __e:
        __out.append({"ok": False, "error": str(__e)})
json.dumps(__out, ensure_ascii=False)
`,
  );
  return JSON.parse(resultsJson).map((r, i) => ({ ...r, spec: slides[i] }));
}

export function buildDeckHtml(pyodide, slides, title) {
  pyodide.globals.set("__deck_slides_json", JSON.stringify(slides));
  pyodide.globals.set("__deck_title", title || "Slide Deck");
  return pyodide.runPython(
    `
import json
from pathlib import Path
from build_html_deck import build_deck

__specs = json.loads(__deck_slides_json)
__paths = []
for __i, __s in enumerate(__specs):
    __p = Path(f"/py/spec-{__i}.json")
    __p.write_text(json.dumps(__s, ensure_ascii=False), encoding="utf-8")
    __paths.append(__p)
build_deck(__paths, __deck_title)
`,
  );
}
