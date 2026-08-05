/* Site orchestrator: progressive enhancement only.
   Every feature degrades to static content when JS, WebGL, or motion is unavailable. */

const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;

function webglAvailable() {
  try {
    const probe = document.createElement("canvas");
    return !!(probe.getContext("webgl2") || probe.getContext("webgl"));
  } catch {
    return false;
  }
}

function showHeroFallback(heroSection) {
  if (heroSection.querySelector(".hd-fallback")) return;
  const figure = document.createElement("figure");
  figure.className = "hd-fallback wrap";
  const img = document.createElement("img");
  img.src = "./site/artifacts/rendered/arr-waterfall.svg";
  img.alt = "Rendered ARR waterfall slide produced by the skill";
  figure.appendChild(img);
  heroSection.appendChild(figure);
}

async function initHeroSection() {
  const heroSection = document.getElementById("hero");
  if (!heroSection) return;
  const canvas = heroSection.querySelector(".hd-canvas");
  if (reducedMotion || !webglAvailable() || !canvas) {
    showHeroFallback(heroSection);
    return;
  }
  let hero;
  try {
    const mod = await import("./hero.js");
    hero = mod.initHero(canvas, { reducedMotion: false });
  } catch {
    showHeroFallback(heroSection);
    return;
  }
  if (!hero || typeof hero.setProgress !== "function") return;

  let active = true;
  new IntersectionObserver((entries) => {
    active = entries[0]?.isIntersecting ?? true;
  }).observe(heroSection);

  let ticking = false;
  const update = () => {
    ticking = false;
    if (!active) return;
    const rect = heroSection.getBoundingClientRect();
    const range = rect.height - window.innerHeight;
    const t = range > 0 ? Math.min(1, Math.max(0, -rect.top / range)) : 1;
    hero.setProgress(t);
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    },
    { passive: true },
  );
  update();
}

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
    button.textContent = "Copied";
    setTimeout(() => {
      button.textContent = label;
    }, 1600);
  });
}

initHeroSection();
initGallerySection();
initCopyButtons();
