/* /try page controller: key management, notes -> Claude -> Pyodide render -> downloads. */

import { generateDeck } from "./llm.js";
import { ensurePyodide, renderSlides, buildDeckHtml } from "./py-render.js";
import { getKey, initKeyField } from "./keymgr.js";
import { fetchRefs } from "./refs.js";
import { STR } from "./strings.js";

const els = {
  keyInput: document.getElementById("try-key-input"),
  keySave: document.getElementById("try-key-save"),
  keyState: document.getElementById("try-key-state"),
  notes: document.getElementById("try-notes-input"),
  sample: document.getElementById("try-sample"),
  generate: document.getElementById("try-generate"),
  status: document.getElementById("try-status"),
  error: document.getElementById("try-error"),
  output: document.getElementById("try-output"),
  outputTitle: document.getElementById("try-output-title"),
  carousel: document.getElementById("try-carousel"),
  dlDeck: document.getElementById("try-dl-deck"),
  dlSvg: document.getElementById("try-dl-svg"),
  copySpec: document.getElementById("try-copy-spec"),
  specWrap: document.getElementById("try-spec-wrap"),
  specJson: document.getElementById("try-spec-json"),
  reset: document.getElementById("try-reset"),
};

function setStatus(text) {
  els.status.hidden = !text;
  els.status.textContent = text || "";
}

function setError(text) {
  els.error.hidden = !text;
  els.error.textContent = text || "";
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

const state = { deck: null, results: [], deckHtml: "" };

function currentSlideIndex() {
  const slides = [...els.carousel.querySelectorAll(".try-slide")];
  if (slides.length < 2) return 0;
  const step = slides[1].offsetLeft - slides[0].offsetLeft;
  return Math.min(
    slides.length - 1,
    Math.max(0, Math.round(els.carousel.scrollLeft / step)),
  );
}

function showResults() {
  els.carousel.textContent = "";
  state.results.forEach((result, i) => {
    const card = document.createElement("div");
    card.className = "try-slide";
    if (result.ok) {
      const holder = document.createElement("div");
      holder.innerHTML = result.svg; // renderer-escaped output (text fields are esc()'d)
      card.appendChild(holder);
    } else {
      const pre = document.createElement("pre");
      pre.className = "try-slide-error";
      pre.textContent = `slide ${i + 1}: ${result.error}`;
      card.appendChild(pre);
    }
    els.carousel.appendChild(card);
  });
  els.outputTitle.textContent = state.deck.title || "Your deck";
  els.specJson.textContent = JSON.stringify(state.deck, null, 2);
  els.output.hidden = false;
  els.output.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function onGenerate() {
  setError("");
  if (!getKey()) return setError(STR.needKey);
  if (!els.notes.value.trim()) return setError(STR.needNotes);

  els.generate.disabled = true;
  try {
    setStatus(STR.stRefs);
    const refsPromise = fetchRefs();
    const pyPromise = ensurePyodide(); // overlap the WASM download with the LLM call
    const refs = await refsPromise;

    setStatus(STR.stClaude);
    const deck = await generateDeck(getKey(), els.notes.value.trim(), refs);
    state.deck = deck;

    setStatus(STR.stRenderer);
    const pyodide = await pyPromise;

    setStatus(STR.stDraw);
    state.results = renderSlides(pyodide, deck.slides);
    state.deckHtml = buildDeckHtml(
      pyodide,
      deck.slides,
      deck.title || "Slide Deck",
    );

    showResults();
    setStatus(STR.stDone);
  } catch (error) {
    setError(String(error && error.message ? error.message : error));
    setStatus("");
  } finally {
    els.generate.disabled = false;
  }
}

els.sample.addEventListener("click", () => {
  els.notes.value = STR.sampleNotes;
  els.notes.focus();
});
els.generate.addEventListener("click", onGenerate);
els.dlDeck.addEventListener("click", () => {
  download("deck.html", state.deckHtml, "text/html");
});
els.dlSvg.addEventListener("click", () => {
  const i = currentSlideIndex();
  const result = state.results[i];
  if (result && result.ok)
    download(`slide-${i + 1}.svg`, result.svg, "image/svg+xml");
});
els.copySpec.addEventListener("click", async () => {
  els.specWrap.hidden = !els.specWrap.hidden;
  const text = els.specJson.textContent;
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    /* clipboard blocked — the <pre> is visible for manual copy */
  }
  const label = els.copySpec.textContent;
  els.copySpec.textContent = STR.copied;
  setTimeout(() => {
    els.copySpec.textContent = label;
  }, 1600);
});
els.reset.addEventListener("click", () => {
  state.deck = null;
  state.results = [];
  state.deckHtml = "";
  els.output.hidden = true;
  els.notes.value = "";
  setStatus("");
  setError("");
  els.notes.focus();
});

initKeyField({ input: els.keyInput, save: els.keySave, state: els.keyState });
