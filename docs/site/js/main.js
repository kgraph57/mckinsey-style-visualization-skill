/* Site orchestrator: progressive enhancement only.
   Every feature degrades to static content when JS or motion is unavailable. */

window.__siteBooted = true;

const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;

const copiedLabel =
  document.documentElement.lang === "ja" ? "コピーしました" : "Copied";

async function initGallerySection() {
  const section = document.getElementById("gallery");
  if (!section) return;
  try {
    const mod = await import("./gallery.js");
    mod.initGallery(section);
  } catch {
    /* manifest fetch or render failure leaves the section heading only */
  }
}

function initCopyButtons() {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy]");
    if (!button) return;
    const target = document.querySelector(button.getAttribute("data-copy"));
    if (!target) return;
    const text = target.textContent;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    const label = button.textContent;
    button.textContent = copiedLabel;
    setTimeout(() => {
      button.textContent = label;
    }, 1600);
  });
}

document.documentElement.classList.add("js");

function initReveals() {
  if (reducedMotion) return;
  const targets = [];
  document
    .querySelectorAll(
      "main section:not(#hero):not(#pipeline) .wrap > *, .ft-shell .wrap > *",
    )
    .forEach((el) => {
      if (!el.classList.contains("gal-lightbox")) targets.push(el);
    });
  const perParent = new Map();
  targets.forEach((el) => {
    const n = perParent.get(el.parentElement) || 0;
    perParent.set(el.parentElement, n + 1);
    el.classList.add("rv");
    el.style.setProperty("--rv-d", `${Math.min(n, 4) * 70}ms`);
  });
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("rv-in");
          io.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
  );
  targets.forEach((el) => io.observe(el));
}

function initScrollspy() {
  const links = [...document.querySelectorAll(".site-nav a")];
  const map = new Map();
  links.forEach((a) => {
    const href = a.getAttribute("href");
    if (href && href.startsWith("#")) {
      const sec = document.querySelector(href);
      if (sec) map.set(sec, a);
    }
  });
  if (!map.size) return;
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          links.forEach((l) => l.classList.remove("is-current"));
          map.get(entry.target)?.classList.add("is-current");
        }
      });
    },
    { rootMargin: "-45% 0px -50% 0px" },
  );
  map.forEach((_, sec) => io.observe(sec));
}

function initPipeline() {
  const section = document.getElementById("pipeline");
  if (!section) return;
  const steps = [...section.querySelectorAll(".pl-step")];
  const fill = section.querySelector(".pl-track-fill");
  if (!steps.length) return;

  // Light one-shot reveal — no sticky / multi-viewport scroll hijack.
  section.classList.add("pl-live");
  if (reducedMotion) {
    steps.forEach((s) => s.classList.add("pl-active"));
    if (fill) fill.style.transform = "scaleX(1)";
    return;
  }

  const play = () => {
    steps.forEach((s, i) => {
      window.setTimeout(() => s.classList.add("pl-active"), i * 140);
    });
    if (fill) {
      fill.style.transition = "transform 520ms ease";
      fill.style.transform = "scaleX(1)";
    }
  };

  const io = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        play();
        io.disconnect();
      }
    },
    { threshold: 0.35 },
  );
  io.observe(section);
}

function initGalleryFilters() {
  const group = document.querySelector(".gal-filters");
  if (!group) return;
  group.addEventListener("click", (event) => {
    const chip = event.target.closest(".gal-chip");
    if (!chip) return;
    group.querySelectorAll(".gal-chip").forEach((c) => {
      const on = c === chip;
      c.classList.toggle("is-active", on);
      c.setAttribute("aria-pressed", String(on));
    });
    const filter = chip.dataset.filter;
    document.querySelectorAll(".gal-card").forEach((card) => {
      card.hidden = filter !== "all" && card.dataset.family !== filter;
    });
  });
}

function initModeTabs() {
  const tabs = [...document.querySelectorAll(".md-tab")];
  if (!tabs.length) return;
  const section = document.getElementById("modes");
  const panels = new Map(
    [...document.querySelectorAll(".md-panel")].map((p) => [
      p.id.replace("md-panel-", ""),
      p,
    ]),
  );
  let userPaused = false;
  let tabTimer = null;
  const TAB_MS = 8000;

  function activate(tab, { fromAuto = false } = {}) {
    if (!fromAuto) userPaused = true;
    clearTimeout(tabTimer);
    tabs.forEach((t) => {
      const on = t === tab;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", String(on));
    });
    panels.forEach((panel, key) => {
      const on = key === tab.dataset.mode;
      panel.hidden = !on;
      panel.classList.toggle("is-active", on);
      if (on) {
        const iframe = panel.querySelector("iframe[data-src]");
        if (iframe) {
          iframe.src = iframe.dataset.src;
          iframe.removeAttribute("data-src");
        }
      }
    });
    if (
      !reducedMotion &&
      !userPaused &&
      section?.classList.contains("md-live")
    ) {
      tabTimer = setTimeout(() => {
        const i = tabs.indexOf(tab);
        activate(tabs[(i + 1) % tabs.length], { fromAuto: true });
      }, TAB_MS);
    }
  }
  tabs.forEach((tab, i) => {
    tab.addEventListener("click", () => activate(tab));
    tab.addEventListener("keydown", (event) => {
      if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
        event.preventDefault();
        const next =
          tabs[
            (i + (event.key === "ArrowRight" ? 1 : tabs.length - 1)) %
              tabs.length
          ];
        next.focus();
        activate(next);
      }
    });
  });
  if (!section || reducedMotion) return;
  const io = new IntersectionObserver(
    (entries) => {
      const on = entries.some((e) => e.isIntersecting);
      section.classList.toggle("md-live", on);
      if (on && !userPaused) {
        const current =
          tabs.find((t) => t.classList.contains("is-active")) || tabs[0];
        activate(current, { fromAuto: true });
      } else {
        clearTimeout(tabTimer);
      }
    },
    { threshold: 0.4 },
  );
  io.observe(section);
}

initGallerySection();
initCopyButtons();
initReveals();
initScrollspy();
initPipeline();
initGalleryFilters();
initModeTabs();
