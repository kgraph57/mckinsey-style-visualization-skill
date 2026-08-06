const RENDERED_BASE = "./site/artifacts/rendered/";
const SPECS_BASE = "./site/artifacts/specs/";
const SAFE_FILENAME = /^[\w-]+\.svg$/;
const IS_JA = document.documentElement.lang === "ja";
const STR_LOADING = IS_JA ? "specを読み込み中…" : "Loading spec…";
const STR_UNAVAILABLE = IS_JA ? "specを表示できません。" : "Spec unavailable.";

function createLightbox(dialog) {
  const stage = dialog.querySelector(".gal-lightbox-stage");
  const code = dialog.querySelector(".gal-lightbox-spec code");
  const captionPattern = dialog.querySelector(
    ".gal-lightbox-caption .gal-card-pattern",
  );
  const captionHeadline = dialog.querySelector(".gal-lightbox-headline");
  const closeButton = dialog.querySelector(".gal-lightbox-close");
  const prevButton = dialog.querySelector(".gal-lightbox-prev");
  const nextButton = dialog.querySelector(".gal-lightbox-next");

  let items = [];
  let index = 0;
  let originator = null;
  let previousOverflow = "";
  let specRequest = 0;

  async function render() {
    const item = items[index];
    if (!item || !SAFE_FILENAME.test(item.file || "")) return;

    const img = document.createElement("img");
    img.src = `${RENDERED_BASE}${item.file}`;
    img.alt = item.headline;
    stage.replaceChildren(img);

    captionPattern.textContent = item.pattern;
    captionHeadline.textContent = item.headline;

    const stem = item.file.replace(/\.svg$/, "");
    const requestId = ++specRequest;
    code.textContent = STR_LOADING;
    try {
      const response = await fetch(`${SPECS_BASE}${stem}.json`);
      if (!response.ok) throw new Error(`spec ${response.status}`);
      const data = await response.json();
      if (requestId !== specRequest) return; // stale: user navigated away
      code.textContent = JSON.stringify(data, null, 2);
    } catch {
      if (requestId === specRequest) code.textContent = STR_UNAVAILABLE;
    }
  }

  function show(nextIndex) {
    index = (nextIndex + items.length) % items.length;
    render();
  }

  prevButton.addEventListener("click", () => show(index - 1));
  nextButton.addEventListener("click", () => show(index + 1));
  closeButton.addEventListener("click", () => dialog.close());

  dialog.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      show(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      show(index + 1);
    }
  });

  dialog.addEventListener("click", (event) => {
    const rect = dialog.getBoundingClientRect();
    const inside =
      event.clientX >= rect.left &&
      event.clientX <= rect.right &&
      event.clientY >= rect.top &&
      event.clientY <= rect.bottom;
    if (!inside) dialog.close();
  });

  dialog.addEventListener("close", () => {
    document.body.style.overflow = previousOverflow;
    if (originator && originator.isConnected) originator.focus();
    originator = null;
  });

  return {
    open(nextItems, startIndex) {
      items = Array.isArray(nextItems) ? nextItems : [];
      if (!items.length) return;
      const si = Number.isFinite(startIndex) ? startIndex : 0;
      index = ((si % items.length) + items.length) % items.length;
      if (!dialog.open) {
        originator = document.activeElement;
        previousOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        dialog.showModal();
        closeButton.focus();
      }
      render();
    },
  };
}

const lightboxes = new WeakMap();

export function openLightbox(dialog, items, startIndex) {
  let lightbox = lightboxes.get(dialog);
  if (!lightbox) {
    lightbox = createLightbox(dialog);
    lightboxes.set(dialog, lightbox);
  }
  lightbox.open(items, startIndex);
}
