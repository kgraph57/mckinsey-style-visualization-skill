import { openLightbox } from "./lightbox.js";

const MANIFEST_URL = "./site/artifacts/gallery-manifest.json";
const RENDERED_BASE = "./site/artifacts/rendered/";
const SAFE_FILENAME = /^[\w-]+\.svg$/;

function buildCard(item, onOpen) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "gal-card";
  card.setAttribute("role", "listitem");

  const img = document.createElement("img");
  img.loading = "lazy";
  img.src = `${RENDERED_BASE}${item.file}`;
  img.alt = item.headline;

  const pattern = document.createElement("span");
  pattern.className = "gal-card-pattern";
  pattern.textContent = item.pattern;

  const headline = document.createElement("span");
  headline.className = "gal-card-headline";
  headline.textContent = item.headline;

  card.append(img, pattern, headline);
  card.addEventListener("click", onOpen);
  return card;
}

export function initGallery(section) {
  const grid = section.querySelector(".gal-grid");
  if (!grid) return;
  const dialog = section.querySelector(".gal-lightbox");

  (async () => {
    try {
      const response = await fetch(MANIFEST_URL);
      if (!response.ok) return;
      const items = await response.json();
      if (!Array.isArray(items)) return;

      const safeItems = items.filter(
        (item) =>
          item &&
          typeof item.file === "string" &&
          SAFE_FILENAME.test(item.file),
      );
      const fragment = document.createDocumentFragment();
      safeItems.forEach((item, index) => {
        const open = dialog
          ? () => openLightbox(dialog, safeItems, index)
          : () => {};
        fragment.appendChild(buildCard(item, open));
      });
      grid.appendChild(fragment);
    } catch {
      /* fetch/parse failure leaves the section heading and lede only */
    }
  })();
}
