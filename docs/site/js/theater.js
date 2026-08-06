/* Hero product theater — CF OS-style tabs + live product stage.
   Motion is the product (deck / SVG carousel / typing demo), not particles. */

import { postDeck, initDeckAutopilot } from "./deck-autopilot.js";

const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;

const TRY_SCRIPT =
  document.documentElement.lang === "ja"
    ? "ARR $4.2M → $6.1M\nチャーン改善 -1.8pt\nエンタープライズ +3件\n→ ボード向けウォーターフォールを1枚で"
    : "ARR $4.2M → $6.1M\nchurn improved -1.8pt\n+3 enterprise logos\n→ one ARR waterfall for the board";

const SLIDE_MS = 3200;
const TYPE_MS = 18;

export function initTheater(root = document.getElementById("hd-theater")) {
  if (!root) return;

  const tabs = [...root.querySelectorAll(".hd-tab")];
  const panels = new Map(
    [...root.querySelectorAll(".hd-panel")].map((p) => [p.dataset.panel, p]),
  );
  const deckFrame = root.querySelector("#hd-deck-frame");
  const jaFrame = root.querySelector("#hd-ja-frame");
  const slideshow = root.querySelector("[data-slideshow]");
  const typed = root.querySelector("#hd-try-typed");
  const tryOut = root.querySelector(".hd-try-out");

  let active = "deck";
  let userPaused = false;
  let inView = false;
  let deckTimer = null;
  let slideTimer = null;
  let tabTimer = null;
  let typeTimer = null;

  function clearTimers() {
    clearInterval(deckTimer);
    clearInterval(slideTimer);
    clearTimeout(tabTimer);
    clearInterval(typeTimer);
    deckTimer = slideTimer = tabTimer = typeTimer = null;
  }

  function ensureSrc(iframe) {
    if (!iframe) return;
    if (iframe.dataset.src && !iframe.getAttribute("src")) {
      iframe.src = iframe.dataset.src;
      iframe.removeAttribute("data-src");
    }
  }

  function runSlideshow() {
    if (!slideshow || reducedMotion) return;
    const imgs = [...slideshow.querySelectorAll("img")];
    if (imgs.length < 2) return;
    let i = imgs.findIndex((img) => img.classList.contains("is-on"));
    if (i < 0) i = 0;
    clearInterval(slideTimer);
    slideTimer = setInterval(() => {
      imgs[i].classList.remove("is-on");
      imgs[i].hidden = true;
      i = (i + 1) % imgs.length;
      imgs[i].hidden = false;
      imgs[i].classList.add("is-on");
    }, SLIDE_MS);
  }

  function runDeck(iframe, { startAt = 0 } = {}) {
    if (!iframe || reducedMotion) return;
    const start = () => {
      if (startAt > 0) postDeck(iframe, "goto", { index: startAt });
      clearInterval(deckTimer);
      deckTimer = setInterval(() => postDeck(iframe, "next"), SLIDE_MS);
    };
    try {
      if (iframe.contentDocument?.readyState === "complete") {
        start();
        return;
      }
    } catch {
      /* ignore */
    }
    iframe.addEventListener("load", start, { once: true });
    setTimeout(start, 400);
  }

  function runTyping() {
    if (!typed) return;
    typed.textContent = "";
    tryOut?.classList.remove("is-reveal");
    if (reducedMotion) {
      typed.textContent = TRY_SCRIPT;
      tryOut?.classList.add("is-reveal");
      return;
    }
    let i = 0;
    clearInterval(typeTimer);
    typeTimer = setInterval(() => {
      i += 1;
      typed.textContent = TRY_SCRIPT.slice(0, i);
      if (i >= TRY_SCRIPT.length) {
        clearInterval(typeTimer);
        typeTimer = null;
        tryOut?.classList.add("is-reveal");
      }
    }, TYPE_MS);
  }

  function activate(tab, { fromAuto = false } = {}) {
    if (!tab) return;
    if (!fromAuto) userPaused = true;
    active = tab.dataset.panel;
    clearTimers();

    tabs.forEach((t) => {
      const on = t === tab;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", String(on));
      t.tabIndex = on ? 0 : -1;
    });

    panels.forEach((panel, key) => {
      const on = key === active;
      panel.hidden = !on;
      panel.classList.toggle("is-active", on);
    });

    if (active === "deck") {
      ensureSrc(deckFrame);
      // Nudge layout after un-hiding — recovers 0×0 iframes.
      requestAnimationFrame(() => {
        if (deckFrame) void deckFrame.offsetWidth;
        runDeck(deckFrame, { startAt: 3 });
      });
    } else if (active === "slides") {
      runSlideshow();
    } else if (active === "ja") {
      ensureSrc(jaFrame);
      requestAnimationFrame(() => {
        if (jaFrame) void jaFrame.offsetWidth;
        runDeck(jaFrame, { startAt: 1 });
      });
    } else if (active === "try") {
      runTyping();
    }

    // No auto tab-cycling — it hid the live deck and left a blank stage.
  }

  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const next =
        tabs[
          (i + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length
        ];
      next.focus();
      activate(next);
    });
  });

  root.addEventListener("pointerenter", () => {
    userPaused = true;
  });
  root.addEventListener("focusin", () => {
    userPaused = true;
  });

  const io = new IntersectionObserver(
    (entries) => {
      inView = entries.some((e) => e.isIntersecting);
      if (inView) {
        const current =
          tabs.find((t) => t.classList.contains("is-active")) || tabs[0];
        activate(current, { fromAuto: true });
      } else {
        clearTimers();
      }
    },
    { threshold: 0.35 },
  );
  io.observe(root);

  // Start on the live deck immediately.
  activate(tabs[0], { fromAuto: true });
}

/** Japanese section: real ja-deck autoplays in view; profile chips pulse in sync. */
export function initCjkAutopilot(section = document.getElementById("cjk")) {
  if (!section) return;
  const iframe = section.querySelector("iframe");
  const chips = [...section.querySelectorAll(".cjk-chip")];
  let chipIndex = 0;

  function highlightChip(reset = false) {
    if (!chips.length) return;
    if (reset) chipIndex = 0;
    else chipIndex = (chipIndex + 1) % chips.length;
    chips.forEach((chip, i) => chip.classList.toggle("is-on", i === chipIndex));
  }

  if (chips.length) chips[0].classList.add("is-on");

  initDeckAutopilot(iframe, {
    root: section,
    intervalMs: 3000,
    startAt: 1,
    onTick: (isStart) => highlightChip(Boolean(isStart)),
  });
}

function boot() {
  initTheater();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
