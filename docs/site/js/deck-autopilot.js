/* Shared deck autopilot: drive same-origin demo decks via postMessage.
   Used by the hero theater and the Japanese (CJK) section. */

const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;

export function postDeck(iframe, action, extra = {}) {
  if (!iframe?.contentWindow) return;
  try {
    iframe.contentWindow.postMessage(
      { type: "deck-control", action, ...extra },
      "*",
    );
  } catch {
    /* not ready */
  }
}

/** Auto-advance a deck iframe while its root is in view. */
export function initDeckAutopilot(iframe, options = {}) {
  if (!iframe || reducedMotion) return () => {};

  const {
    root = iframe.closest("section") || iframe,
    intervalMs = 3200,
    startAt = 1,
    onTick = null,
  } = options;

  let timer = null;
  let started = false;

  function tick() {
    postDeck(iframe, "next");
    onTick?.();
  }

  function start() {
    if (started) return;
    started = true;
    const go = () => {
      if (startAt > 0) postDeck(iframe, "goto", { index: startAt });
      clearInterval(timer);
      timer = setInterval(tick, intervalMs);
      onTick?.(true);
    };
    try {
      if (iframe.contentDocument?.readyState === "complete") {
        go();
        return;
      }
    } catch {
      /* ignore */
    }
    iframe.addEventListener("load", go, { once: true });
    setTimeout(go, 500);
  }

  function stop() {
    started = false;
    clearInterval(timer);
    timer = null;
  }

  const io = new IntersectionObserver(
    (entries) => {
      if (entries.some((e) => e.isIntersecting)) start();
      else stop();
    },
    { threshold: 0.35 },
  );
  io.observe(root);

  root.addEventListener(
    "pointerdown",
    () => {
      /* user took over; pause autoplay until they leave the section */
      stop();
      const resume = () => {
        start();
        root.removeEventListener("pointerleave", resume);
      };
      root.addEventListener("pointerleave", resume, { once: true });
    },
    { passive: true },
  );

  return () => {
    stop();
    io.disconnect();
  };
}
