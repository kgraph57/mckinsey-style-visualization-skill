/* /try page controller: key management, notes -> Claude -> Pyodide render -> downloads. */

import { generateDeck, MODEL } from "./llm.js";
import { ensurePyodide, renderSlides, buildDeckHtml } from "./py-render.js";

const IS_JA = document.documentElement.lang === "ja";
const STR = {
  keySaved: IS_JA ? "保存済み" : "saved",
  keyChange: IS_JA ? "変更" : "Change",
  keyClear: IS_JA ? "消去" : "Clear",
  needKey: IS_JA
    ? "先にAPIキーを保存してください。"
    : "Save your API key first.",
  needNotes: IS_JA ? "メモを入力してください。" : "Paste some notes first.",
  stRefs: IS_JA
    ? "レンダラーのルールブックを読み込み中…"
    : "Reading the renderer's rulebook…",
  stClaude: IS_JA
    ? `Claude（${MODEL}）にメモを渡しています…`
    : `Handing your notes to Claude (${MODEL})…`,
  stRenderer: IS_JA
    ? "レンダラーを起動しています（初回のみ約12MB）…"
    : "Starting the renderer (first time only, ~12 MB)…",
  stDraw: IS_JA ? "スライドを描画しています…" : "Drawing slides…",
  stDone: IS_JA ? "できました。" : "Done.",
  stRetry: IS_JA ? "specの修復を試みています…" : "Attempting one repair pass…",
  copied: IS_JA ? "コピーしました" : "Copied",
  slideOf: IS_JA ? "枚目" : "",
  sampleNotes: IS_JA
    ? "ARRは$10Mから$15Mに成長した。エンタープライズ新規が+$3M、既存顧客の拡大が+$2.5M、チャーンが-$0.5M。AIワークフローの導入率は18%から64%に上昇。取締役会で実装キャパシティへの投資判断が必要。"
    : "ARR grew from $10M to $15M. Enterprise added $3M, expansion $2.5M, churn -$0.5M. AI workflow adoption grew from 18% to 64%. The board must decide on implementation capacity investment.",
};

const KEY_STORAGE = "scv-anthropic-key";
const ARTIFACTS = new URL("../../artifacts/", import.meta.url);

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

function getKey() {
  return localStorage.getItem(KEY_STORAGE) || "";
}

function maskKey(key) {
  return key.length > 10 ? `${key.slice(0, 7)}…${key.slice(-4)}` : "…";
}

function refreshKeyState() {
  const key = getKey();
  if (!key) {
    els.keyState.hidden = true;
    els.keyInput.value = "";
    return;
  }
  els.keyInput.value = "";
  els.keyInput.placeholder = maskKey(key);
  els.keyState.hidden = false;
  els.keyState.textContent = "";
  const label = document.createElement("span");
  label.textContent = `${STR.keySaved}: ${maskKey(key)}`;
  const change = document.createElement("button");
  change.type = "button";
  change.className = "btn btn-ghost";
  change.textContent = STR.keyChange;
  change.addEventListener("click", () => {
    els.keyState.hidden = true;
    els.keyInput.value = key;
    els.keyInput.focus();
  });
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "btn btn-ghost";
  clear.textContent = STR.keyClear;
  clear.addEventListener("click", () => {
    localStorage.removeItem(KEY_STORAGE);
    refreshKeyState();
  });
  els.keyState.append(label, change, clear);
}

function setStatus(text) {
  if (!text) {
    els.status.hidden = true;
    els.status.textContent = "";
    return;
  }
  els.status.hidden = false;
  els.status.textContent = text;
}

function setError(text) {
  if (!text) {
    els.error.hidden = true;
    els.error.textContent = "";
    return;
  }
  els.error.hidden = false;
  els.error.textContent = text;
}

async function fetchRefs() {
  const files = {
    patterns: "prompt/visualization-patterns.md",
    templates: "prompt/prompt-templates.md",
    triage: "prompt/input-triage.md",
  };
  const entries = await Promise.all(
    Object.entries(files).map(async ([k, p]) => {
      const res = await fetch(new URL(p, ARTIFACTS));
      if (!res.ok) throw new Error(`failed to load ${p}: ${res.status}`);
      return [k, await res.text()];
    }),
  );
  return Object.fromEntries(entries);
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
    let deck;
    try {
      deck = await generateDeck(getKey(), els.notes.value.trim(), refs);
    } catch (firstError) {
      setStatus(STR.stRetry);
      deck = await generateDeck(getKey(), els.notes.value.trim(), refs).catch(
        () => {
          throw firstError;
        },
      );
    }
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

els.keySave.addEventListener("click", () => {
  const value = els.keyInput.value.trim();
  if (value) localStorage.setItem(KEY_STORAGE, value);
  refreshKeyState();
});
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

refreshKeyState();
