/* Examples page: three clear views — deck / patterns / formats. */

import { initDeckAutopilot } from "./deck-autopilot.js";

const PANELS = ["live-deck", "patterns", "formats"];
const HASH_ALIASES = {
  gallery: "patterns",
  modes: "formats",
  cjk: "live-deck",
  japanese: "live-deck",
  deck: "live-deck",
  ja: "live-deck",
};

const ARTIFACT_BASE = new URL("../artifacts/", import.meta.url).href;
const PAGE_JA = document.documentElement.lang === "ja";

const DECK = {
  en: {
    src: new URL("demo-deck.html?embed=1", ARTIFACT_BASE).href,
    openHref: new URL("demo-deck.html", ARTIFACT_BASE).href,
    url: PAGE_JA ? "demo-deck.html — 自動再生" : "demo-deck.html — autoplaying",
    caption: PAGE_JA
      ? "英語のボードストーリー：spec → SVG → アニメーションHTML。枠をクリックしてから矢印キーで送れます。"
      : "English board story: specs → SVG → animated HTML. Arrow keys work after you click the frame.",
    title: PAGE_JA
      ? "このリポジトリが生成したアニメーションデモデッキ"
      : "Animated demo deck built by this repo",
  },
  ja: {
    src: new URL("ja-deck.html?embed=1", ARTIFACT_BASE).href,
    openHref: new URL("ja-deck.html", ARTIFACT_BASE).href,
    url: PAGE_JA
      ? "ja-deck.html — 役員会アップデート（日本語）、自動再生"
      : "ja-deck.html — board-update-ja, autoplaying",
    caption: PAGE_JA
      ? "日本語の役員会デッキ。CJKは全角文字単位で折り返します（スペースでは割りません）。"
      : "Japanese board deck. CJK wraps per fullwidth character — never by spaces.",
    title: PAGE_JA
      ? "日本語の役員会アップデート・デモデッキ — 自動再生"
      : "Japanese board-update demo deck — autoplaying",
  },
};

let stopAutopilot = null;
let deckLang = PAGE_JA ? "ja" : "en";

function resolvePanel(raw) {
  const id = HASH_ALIASES[raw] || raw;
  return PANELS.includes(id) ? id : "live-deck";
}

function activate(panelId, { pushHash = true } = {}) {
  panelId = resolvePanel(panelId);

  document.querySelectorAll(".ex-tab").forEach((tab) => {
    const on = tab.dataset.panel === panelId;
    tab.classList.toggle("is-active", on);
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
  });

  document.querySelectorAll(".ex-panel").forEach((panel) => {
    const on = panel.id === panelId;
    panel.hidden = !on;
    panel.classList.toggle("is-active", on);
    if (on) {
      panel.querySelectorAll("iframe[data-src]").forEach((iframe) => {
        if (!iframe.getAttribute("src")) {
          iframe.src = iframe.dataset.src;
          iframe.removeAttribute("data-src");
        }
      });
    }
  });

  if (panelId === "live-deck") startDeckAutopilot();
  else stopDeckAutopilot();

  if (pushHash) {
    const url = new URL(location.href);
    url.hash = panelId === "live-deck" ? "" : panelId;
    history.replaceState(null, "", url.pathname + url.search + url.hash);
  }

  document.querySelector(".ex-head")?.scrollIntoView({ block: "start" });
}

function stopDeckAutopilot() {
  if (typeof stopAutopilot === "function") stopAutopilot();
  stopAutopilot = null;
}

function startDeckAutopilot() {
  stopDeckAutopilot();
  const iframe = document.getElementById("ex-deck-frame");
  if (!iframe) return;
  stopAutopilot = initDeckAutopilot(iframe, {
    root: document.getElementById("live-deck"),
    intervalMs: 3200,
    startAt: deckLang === "ja" ? 1 : 3,
    onTick: (isStart) => {
      if (deckLang !== "ja") return;
      const chips = [
        ...document.querySelectorAll("#ex-deck-profiles .cjk-chip"),
      ];
      if (!chips.length) return;
      let i = chips.findIndex((c) => c.classList.contains("is-on"));
      if (isStart) i = 0;
      else i = (Math.max(i, 0) + 1) % chips.length;
      chips.forEach((c, n) => c.classList.toggle("is-on", n === i));
    },
  });
}

function setDeckLang(lang) {
  if (!DECK[lang]) return;
  deckLang = lang;
  const conf = DECK[lang];
  const iframe = document.getElementById("ex-deck-frame");
  const url = document.getElementById("ex-deck-url");
  const caption = document.getElementById("ex-deck-caption");
  const open = document.getElementById("ex-deck-open");
  const profiles = document.getElementById("ex-deck-profiles");

  document.querySelectorAll(".ex-lang-btn").forEach((btn) => {
    const on = btn.dataset.lang === lang;
    btn.classList.toggle("is-on", on);
    btn.setAttribute("aria-pressed", String(on));
  });

  if (iframe) {
    iframe.src = conf.src;
    iframe.title = conf.title;
  }
  if (url) url.textContent = conf.url;
  if (caption) caption.textContent = conf.caption;
  if (open) open.href = conf.openHref || conf.src;
  if (profiles) profiles.hidden = lang !== "ja";

  if (!document.getElementById("live-deck")?.hidden) startDeckAutopilot();
}

function initTabs() {
  const tabs = [...document.querySelectorAll(".ex-tab")];
  if (!tabs.length) return;

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => activate(tab.dataset.panel));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const next =
        tabs[
          (i + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length
        ];
      next.focus();
      activate(next.dataset.panel);
    });
  });

  const raw = location.hash.replace(/^#/, "");
  if (raw === "cjk" || raw === "japanese" || raw === "ja") setDeckLang("ja");
  else setDeckLang(deckLang);
  activate(resolvePanel(raw), { pushHash: false });

  window.addEventListener("hashchange", () => {
    const id = location.hash.replace(/^#/, "");
    if (id === "cjk" || id === "japanese" || id === "ja") setDeckLang("ja");
    activate(resolvePanel(id), { pushHash: false });
  });
}

function initLangToggle() {
  document.querySelector(".ex-lang")?.addEventListener("click", (event) => {
    const btn = event.target.closest(".ex-lang-btn");
    if (!btn) return;
    setDeckLang(btn.dataset.lang);
  });
}

initTabs();
initLangToggle();
