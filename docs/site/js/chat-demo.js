/* Landing chat demo: ask → build many slides → live deck, looping.
   Page language is absolute. Slide thumbs + deck HTML come from the
   pre-rendered assets in decks-manifest.json (en + ja prepared ahead). */

import { initDeckAutopilot, postDeck } from "./deck-autopilot.js";

const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;

const IS_JA = document.documentElement.lang === "ja";
const LANG = IS_JA ? "ja" : "en";
const ARTIFACT = new URL("../artifacts/", import.meta.url);

const HOLD_MS = reducedMotion ? 2800 : 11000;
const LOOP_GAP_MS = reducedMotion ? 500 : 900;
const BUILD_STEP_MS = reducedMotion ? 40 : 320;

const FALLBACK = {
  en: {
    deck: "demo-deck.html",
    slides: [
      {
        file: "rendered/en/01-board-deck-cover.svg",
        label_en: "Cover",
        label_ja: "表紙",
      },
      {
        file: "rendered/en/02-strategy-agenda.svg",
        label_en: "Agenda",
        label_ja: "アジェンダ",
      },
      {
        file: "rendered/en/03-phase-divider.svg",
        label_en: "Divider",
        label_ja: "区切り",
      },
      {
        file: "rendered/en/04-executive-summary.svg",
        label_en: "Exec summary",
        label_ja: "役員要約",
      },
      {
        file: "rendered/en/05-arr-waterfall.svg",
        label_en: "ARR bridge",
        label_ja: "ARR橋渡し",
      },
      {
        file: "rendered/en/06-segment-adoption-multiples.svg",
        label_en: "Segments",
        label_ja: "セグメント",
      },
      {
        file: "rendered/en/07-product-priority-two-by-two.svg",
        label_en: "Priorities",
        label_ja: "優先度",
      },
      {
        file: "rendered/en/08-board-closing.svg",
        label_en: "Asks",
        label_ja: "決議事項",
      },
      {
        file: "rendered/en/09-deck-end-cover.svg",
        label_en: "Close",
        label_ja: "クローズ",
      },
    ],
  },
  ja: {
    deck: "ja-deck.html",
    slides: [
      { file: "rendered/ja/01-cover.svg", label_en: "Cover", label_ja: "表紙" },
      {
        file: "rendered/ja/02-agenda.svg",
        label_en: "Agenda",
        label_ja: "アジェンダ",
      },
      {
        file: "rendered/ja/03-executive-summary.svg",
        label_en: "Exec summary",
        label_ja: "役員要約",
      },
      {
        file: "rendered/ja/04-kpi-scorecard.svg",
        label_en: "KPI",
        label_ja: "KPI",
      },
      {
        file: "rendered/ja/05-arr-waterfall.svg",
        label_en: "ARR bridge",
        label_ja: "ARR橋渡し",
      },
      {
        file: "rendered/ja/06-adoption-trend.svg",
        label_en: "Adoption",
        label_ja: "導入率",
      },
      {
        file: "rendered/ja/07-risks.svg",
        label_en: "Risks",
        label_ja: "リスク",
      },
      {
        file: "rendered/ja/08-closing.svg",
        label_en: "Asks",
        label_ja: "決議",
      },
      {
        file: "rendered/ja/09-end-cover.svg",
        label_en: "Close",
        label_ja: "クローズ",
      },
    ],
  },
};

function uiCopy(total) {
  return IS_JA
    ? {
        user: "ARRが$10M→$15M。エンタープライズ新規+$3M、拡大+$2.5M、チャーン-$0.5M。役員会向けに、表紙からクローズまで一式のデッキをつくって。",
        status: "strategy-consulting-visualization スキルを実行中…",
        building: (n) => `スライドを描画中… ${n} / ${total}`,
        reply: `できた。メモから ${total} 枚の役員会デッキを描いた。下で枚が進んでいく。`,
        whoUser: "あなた",
        whoAgent: "エージェント",
        chrome: "エージェント · strategy-consulting-visualization",
        count: (i) => `${i} / ${total} 枚`,
        caption: "自動再生",
        stackAria: "生成されたデッキのスライド",
        deckTitle: "チャット依頼から生成された役員会デッキ",
        composer: "役員会スライドを依頼…",
      }
    : {
        user: "ARR went $10M → $15M. Enterprise +$3M, expansion +$2.5M, churn −$0.5M. Build a full board deck — cover through close, not just one slide.",
        status: "Using strategy-consulting-visualization…",
        building: (n) => `Rendering slides… ${n} / ${total}`,
        reply: `Done. ${total} slides for the board, from your notes. Watch them flip through below.`,
        whoUser: "You",
        whoAgent: "Agent",
        chrome: "Agent · strategy-consulting-visualization",
        count: (i) => `${i} / ${total} slides`,
        caption: "autoplaying",
        stackAria: "Slides in the generated deck",
        deckTitle: "Board deck generated from the chat request",
        composer: "Ask for a board slide…",
      };
}

async function loadDeckPack() {
  try {
    const res = await fetch(new URL("decks-manifest.json", ARTIFACT).href);
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    if (!data?.[LANG]?.slides?.length) throw new Error("empty pack");
    return data[LANG];
  } catch {
    return FALLBACK[LANG];
  }
}

function wait(ms, state) {
  return new Promise((resolve) => {
    if (state?.cancelled) {
      resolve();
      return;
    }
    const t = setTimeout(resolve, ms);
    const clear = () => {
      clearTimeout(t);
      resolve();
    };
    if (state) {
      const prev = state._clearWait;
      state._clearWait = () => {
        clear();
        prev?.();
      };
    }
  });
}

function typeInto(el, text, ms, state) {
  return new Promise((resolve) => {
    if (!el) {
      resolve();
      return;
    }
    if (reducedMotion || state?.cancelled) {
      el.textContent = text;
      resolve();
      return;
    }
    let i = 0;
    el.textContent = "";
    const timer = setInterval(() => {
      if (state?.cancelled) {
        clearInterval(timer);
        el.textContent = text;
        resolve();
        return;
      }
      i += 1;
      el.textContent = text.slice(0, i);
      if (i >= text.length) {
        clearInterval(timer);
        resolve();
      }
    }, ms);
  });
}

function show(el) {
  if (!el) return;
  el.hidden = false;
  el.classList.remove("is-in");
  void el.offsetWidth;
  el.classList.add("is-in");
}

function hide(el) {
  if (!el) return;
  el.classList.remove("is-in");
  el.hidden = true;
}

function slideLabel(entry) {
  return IS_JA ? entry.label_ja : entry.label_en;
}

function applyStaticCopy(root, script) {
  const chrome = root.querySelector(".chat-chrome-title");
  if (chrome) chrome.textContent = script.chrome;
  const stack = root.querySelector("#chat-stack");
  if (stack) stack.setAttribute("aria-label", script.stackAria);
  const frame = root.querySelector("#chat-deck-frame");
  if (frame) frame.title = script.deckTitle;
  const composer = root.querySelector(".chat-composer-fake");
  if (composer) composer.textContent = script.composer;
  root.querySelectorAll(".chat-who").forEach((el) => {
    el.textContent = el.closest(".chat-msg-user")
      ? script.whoUser
      : script.whoAgent;
  });
}

function setCount(root, script, index1based) {
  const count = root.querySelector("#chat-slide-count");
  const caption = root.querySelector("#chat-slide-caption");
  if (count) count.textContent = script.count(Math.max(index1based, 0));
  if (caption) caption.textContent = script.caption;
}

function clearStack(stack) {
  if (!stack) return;
  stack.replaceChildren();
}

function markStack(stack, index) {
  if (!stack) return;
  stack.querySelectorAll(".chat-stack-item").forEach((item, i) => {
    item.classList.toggle("is-on", i === index);
  });
}

function ensureDeck(root, deckFile) {
  const frame = root.querySelector("#chat-deck-frame");
  if (!frame) return null;
  const src = new URL(`${deckFile}?embed=1`, ARTIFACT).href;
  frame.setAttribute("data-src", src);
  if (frame.getAttribute("src") !== src) frame.setAttribute("src", src);
  return frame;
}

function whenDeckReady(iframe) {
  return new Promise((resolve) => {
    if (!iframe) {
      resolve();
      return;
    }
    const ready = () => {
      try {
        if (iframe.contentDocument?.querySelector(".slide")) {
          resolve();
          return true;
        }
      } catch {
        /* ignore */
      }
      return false;
    };
    if (ready()) return;
    iframe.addEventListener("load", () => resolve(), { once: true });
    setTimeout(resolve, 2500);
  });
}

async function buildStack(root, script, slides, progressEl, state) {
  const stack = root.querySelector("#chat-stack");
  if (!stack) return;
  clearStack(stack);
  const total = slides.length;

  for (let i = 0; i < total; i += 1) {
    if (state.cancelled) return;
    const entry = slides[i];
    const li = document.createElement("li");
    li.className = "chat-stack-item";

    const img = document.createElement("img");
    img.className = "chat-stack-thumb";
    img.loading = "eager";
    img.alt = slideLabel(entry);
    img.src = new URL(entry.file, ARTIFACT).href;

    const meta = document.createElement("div");
    meta.className = "chat-stack-meta";

    const num = document.createElement("span");
    num.className = "chat-stack-num";
    num.textContent = String(i + 1).padStart(2, "0");

    const label = document.createElement("span");
    label.className = "chat-stack-label";
    label.textContent = slideLabel(entry);

    meta.append(num, label);
    li.append(img, meta);
    stack.appendChild(li);
    void li.offsetWidth;
    li.classList.add("is-in");
    markStack(stack, i);
    if (progressEl) progressEl.textContent = script.building(i + 1);
    setCount(root, script, i + 1);
    await wait(BUILD_STEP_MS, state);
  }
}

function resetThread(root, script) {
  ["user", "thinking", "reply"].forEach((step) => {
    hide(root.querySelector(`[data-step="${step}"]`));
  });
  const slide = root.querySelector(".chat-slide");
  if (slide) slide.classList.remove("is-revealed");
  clearStack(root.querySelector("#chat-stack"));
  const userText = root.querySelector("#chat-user-text");
  const replyText = root.querySelector("#chat-reply-text");
  if (userText) userText.textContent = "";
  if (replyText) replyText.textContent = "";
  setCount(root, script, 0);
  root.classList.remove("is-fading");
}

async function playOnce(root, pack, script, state) {
  const userStep = root.querySelector('[data-step="user"]');
  const thinkStep = root.querySelector('[data-step="thinking"]');
  const replyStep = root.querySelector('[data-step="reply"]');
  const userText = root.querySelector("#chat-user-text");
  const statusText = root.querySelector("#chat-status-text");
  const replyText = root.querySelector("#chat-reply-text");
  const slide = root.querySelector(".chat-slide");
  const stack = root.querySelector("#chat-stack");
  const slides = pack.slides;
  const total = slides.length;

  applyStaticCopy(root, script);
  if (statusText) statusText.textContent = script.status;

  resetThread(root, script);
  if (state.cancelled) return;

  const iframe = ensureDeck(root, pack.deck);

  show(userStep);
  await typeInto(userText, script.user, 13, state);
  if (state.cancelled) return;
  await wait(reducedMotion ? 140 : 480, state);
  if (state.cancelled) return;

  show(thinkStep);
  await Promise.all([
    wait(reducedMotion ? 220 : 700, state),
    whenDeckReady(iframe),
  ]);
  if (state.cancelled) return;

  hide(thinkStep);
  show(replyStep);
  if (replyText) replyText.textContent = "";

  await buildStack(root, script, slides, replyText, state);
  if (state.cancelled) return;
  await wait(reducedMotion ? 100 : 320, state);
  if (state.cancelled) return;

  await typeInto(replyText, script.reply, 12, state);
  if (state.cancelled) return;
  await wait(reducedMotion ? 80 : 200, state);
  if (state.cancelled) return;

  postDeck(iframe, "goto", { index: 0 });
  markStack(stack, 0);
  setCount(root, script, 1);
  if (slide) {
    slide.classList.add("is-revealed");
    slide.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  await wait(80, state);
  postDeck(iframe, "goto", { index: 0 });

  state.stopAutopilot?.();
  state.stopAutopilot = null;

  let current = 0;
  if (iframe && !reducedMotion) {
    state.stopAutopilot = initDeckAutopilot(iframe, {
      root,
      intervalMs: 2200,
      startAt: 0,
      onTick: (isStart) => {
        if (isStart) current = 0;
        else current = (current + 1) % total;
        markStack(stack, current);
        setCount(root, script, current + 1);
      },
    });
    markStack(stack, 0);
    setCount(root, script, 1);
  } else if (iframe) {
    postDeck(iframe, "goto", { index: 0 });
    setCount(root, script, total);
  }

  await wait(HOLD_MS, state);

  state.stopAutopilot?.();
  state.stopAutopilot = null;
}

async function loop(root, pack, script, state) {
  while (!state.cancelled) {
    await playOnce(root, pack, script, state);
    if (state.cancelled) break;
    root.classList.add("is-fading");
    await wait(LOOP_GAP_MS, state);
    root.classList.remove("is-fading");
  }
}

export function initChatDemo(root = document.getElementById("chat-demo")) {
  if (!root) return;

  const state = {
    cancelled: true,
    stopAutopilot: null,
    running: false,
    _clearWait: null,
    pack: null,
    script: null,
  };

  function stop() {
    state.cancelled = true;
    state._clearWait?.();
    state._clearWait = null;
    state.stopAutopilot?.();
    state.stopAutopilot = null;
    state.running = false;
  }

  async function start() {
    if (state.running) return;
    if (!state.pack) {
      state.pack = await loadDeckPack();
      state.script = uiCopy(state.pack.slides.length);
      applyStaticCopy(root, state.script);
      setCount(root, state.script, 0);
      ensureDeck(root, state.pack.deck);
    }
    state.cancelled = false;
    state.running = true;
    loop(root, state.pack, state.script, state).finally(() => {
      state.running = false;
    });
  }

  const io = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) start();
      else stop();
    },
    { threshold: 0.25 },
  );
  io.observe(root);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => initChatDemo());
} else {
  initChatDemo();
}
