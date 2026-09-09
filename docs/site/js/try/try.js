import { createPresenter } from "./presenter.js";
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

  els.generate.disabled = true; els.reset.disabled = true;
  demoButton.disabled = true;
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
    els.copySpec.hidden = false;
    setStatus(STR.stDone);
  } catch (error) {
    setError(String(error && error.message ? error.message : error));
    setStatus("");
  } finally {
    els.generate.disabled = false; els.reset.disabled = false;
    demoButton.disabled = false;
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

const presenter = createPresenter({ getResults: () => state.results, getHtml: () => state.deckHtml, getTitle: () => state.deck?.title || 'Presentation' });
document.getElementById('try-present').addEventListener('click', () => presenter.open());
document.getElementById('try-share').addEventListener('click', async () => {
  try {
    const result = await presenter.share();
    if (result === 'downloaded') setStatus(document.documentElement.lang === 'ja' ? 'HTMLファイルの保存を開始しました。共有非対応の環境では、保存したファイルを共有してください。' : 'HTML download started. Share the saved file if native file sharing is unavailable.');
  } catch (error) { setError(String(error.message || error)); }
});
const demoButton = document.getElementById('try-demo');
demoButton.addEventListener('click', async () => {
  demoButton.disabled = true; els.generate.disabled = true; els.reset.disabled = true; setError('');
  try {
    const response = await fetch(new URL('../../artifacts/demo-deck.html', import.meta.url));
    if (!response.ok) throw new Error('Sample deck unavailable');
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const svgs = [...doc.querySelectorAll('.frame svg')];
    if (!svgs.length) throw new Error('Sample deck has no slides');
    state.deckHtml = html; state.deck = { title: doc.title, slides: [] };
    state.results = svgs.map(svg => ({ ok: true, svg: svg.outerHTML }));
    showResults(); els.copySpec.hidden = true; els.specWrap.hidden = true;
    setStatus(document.documentElement.lang === 'ja' ? '既存の英語サンプルです。APIは呼び出していません。' : 'Existing English sample loaded. No AI API call was made.');
  } catch (error) { setError(String(error.message || error)); }
  finally { demoButton.disabled = false; els.generate.disabled = false; els.reset.disabled = false; }
});
