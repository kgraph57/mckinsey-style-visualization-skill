/* Fetch the renderer's prompt references (copied into artifacts by build_site.py). */

const ARTIFACTS = new URL("../../artifacts/", import.meta.url);

export async function fetchRefs() {
  const files = {
    patterns: "prompt/visualization-patterns.md",
    templates: "prompt/prompt-templates.md",
    triage: "prompt/input-triage.md",
  };
  const entries = await Promise.all(
    Object.entries(files).map(async ([key, path]) => {
      const res = await fetch(new URL(path, ARTIFACTS));
      if (!res.ok) throw new Error(`failed to load ${path}: ${res.status}`);
      return [key, await res.text()];
    }),
  );
  return Object.fromEntries(entries);
}
