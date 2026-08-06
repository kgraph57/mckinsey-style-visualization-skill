/* Landing-page console: notes -> Claude -> WASM render, embedded after the hero. */

import { generateDeck } from "./llm.js";
import { ensurePyodide, renderSlides, buildDeckHtml } from "./py-render.js";
import { getKey, initKeyField } from "./keymgr.js";
import { fetchRefs } from "./refs.js";
import { STR } from "./strings.js";

const els = {
  keyInput: document.getElementById("con-key-input"),
  keySave: document.getElementById("con-key-save"),
  keyState: document.getElementById("con-key-state"),
  notes: document.getElementById("con-notes"),
  sample: document.getElementById("con-sample"),
  generate: document.getElementById("con-generate"),
  status: document.getElementById("con-status"),
  error: document.getElementById("con-error"),
  results: document.getElementById("con-results"),
  carousel: document.getElementById("con-carousel"),
  dlDeck: document.getElementById("con-dl-deck"),
};

if (els.generate) {
  initKeyField({ input: els.keyInput, save: els.keySave, state: els.keyState });

  const state = { deck: null, results: [], deckHtml: "" };

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

  function showResults() {
    els.carousel.textContent = "";
    state.results.forEach((result, i) => {
      const card = document.createElement("div");
      card.className = "try-slide";
      if (result.ok) {
        const holder = document.createElement("div");
        holder.innerHTML = result.svg; // renderer-escaped output
        card.appendChild(holder);
      } else {
        const pre = document.createElement("pre");
        pre.className = "try-slide-error";
        pre.textContent = `slide ${i + 1}: ${result.error}`;
        card.appendChild(pre);
      }
      els.carousel.appendChild(card);
    });
    els.results.hidden = false;
    els.results.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function onGenerate() {
    setError("");
    if (!getKey()) return setError(STR.needKey);
    if (!els.notes.value.trim()) return setError(STR.needNotes);
    els.generate.disabled = true;
    try {
      setStatus(STR.stRefs);
      const refsPromise = fetchRefs();
      const pyPromise = ensurePyodide();
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
    if (state.deckHtml) download("deck.html", state.deckHtml, "text/html");
  });
}
