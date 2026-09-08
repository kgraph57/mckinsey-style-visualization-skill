/* Static examples stay readable without JavaScript; controls only enhance them. */
const showcase = document.getElementById('showcase');
if (showcase) {
  const controls = showcase.querySelector('.showcase-switches');
  const buttons = [...controls.querySelectorAll('button[data-example]')];
  const panels = [...showcase.querySelectorAll('.showcase-case')];
  const sourceLink = showcase.querySelector('.showcase-spec');
  const specs = { growth: 'arr-waterfall', summary: 'executive-summary', priority: 'product-priority-two-by-two' };
  controls.hidden = false;
  for (const button of buttons) {
    button.addEventListener('click', () => {
      const key = button.dataset.example;
      for (const item of buttons) item.setAttribute('aria-pressed', String(item === button));
      for (const panel of panels) panel.hidden = panel.id !== `case-${key}`;
      sourceLink.href = new URL(`../artifacts/specs/${specs[key]}.json`, import.meta.url).href;
    });
  }
}
