/* Shared BYOK key field: save/mask/change/clear against localStorage. */

const KEY_STORAGE = "scv-anthropic-key";

export function getKey() {
  return localStorage.getItem(KEY_STORAGE) || "";
}

function mask(key) {
  return key.length > 10 ? `${key.slice(0, 7)}…${key.slice(-4)}` : "…";
}

export function initKeyField({ input, save, state }) {
  const isJa = document.documentElement.lang === "ja";
  const labels = {
    saved: isJa ? "保存済み" : "saved",
    change: isJa ? "変更" : "Change",
    clear: isJa ? "消去" : "Clear",
  };

  function makeButton(text, onClick) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-ghost";
    button.textContent = text;
    button.addEventListener("click", onClick);
    return button;
  }

  function refresh() {
    const key = getKey();
    if (!key) {
      state.hidden = true;
      input.value = "";
      return;
    }
    input.value = "";
    input.placeholder = mask(key);
    state.hidden = false;
    state.textContent = "";
    const label = document.createElement("span");
    label.textContent = `${labels.saved}: ${mask(key)}`;
    state.append(
      label,
      makeButton(labels.change, () => {
        state.hidden = true;
        input.value = key;
        input.focus();
      }),
      makeButton(labels.clear, () => {
        localStorage.removeItem(KEY_STORAGE);
        refresh();
      }),
    );
  }

  save.addEventListener("click", () => {
    const value = input.value.trim();
    if (value) localStorage.setItem(KEY_STORAGE, value);
    refresh();
  });

  refresh();
}
