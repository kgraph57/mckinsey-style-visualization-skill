/* Static examples stay readable without JavaScript; controls only enhance them. */
const showcase = document.getElementById('showcase');
if (showcase) {
  const controls = showcase.querySelector('.showcase-switches');
  const buttons = [...controls.querySelectorAll('button[data-example]')];
  const panels = [...showcase.querySelectorAll('.showcase-case')];
  const sourceLink = showcase.querySelector('.showcase-spec');
  const specs = { growth: 'arr-waterfall', summary: 'executive-summary', priority: 'product-priority-two-by-two' };
  controls.hidden = false;
  const play = showcase.querySelector('.showcase-play');
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const ja = document.documentElement.lang === 'ja';
  let timer;
  let playing = false;
  let index = 0;
  function select(button) {
    index = buttons.indexOf(button);
    const key = button.dataset.example;
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    panels.forEach(panel => { panel.hidden = panel.id !== `case-${key}`; });
    sourceLink.href = new URL(`../artifacts/specs/${specs[key]}.json`, import.meta.url).href;
  }
  function setPlaying(value) {
    playing = value;
    clearInterval(timer);
    showcase.classList.toggle('is-playing', playing);
    play.setAttribute('aria-pressed', String(!playing));
    play.textContent = ja ? (playing ? 'デモを停止' : 'デモを再生') : (playing ? 'Pause demo' : 'Play demo');
    play.setAttribute('aria-label', play.textContent);
    if (playing) timer = setInterval(() => {
      if (!document.hidden && (!showcase.contains(document.activeElement) || document.activeElement === play)) select(buttons[(index + 1) % buttons.length]);
    }, 6000);
  }
  play.hidden = false;
  play.addEventListener('click', () => setPlaying(!playing));
  reduceMotion.addEventListener('change', () => { if (reduceMotion.matches) setPlaying(false); });
  setPlaying(!reduceMotion.matches);
  for (const button of buttons) {
    button.addEventListener('click', () => {
      setPlaying(false);
      select(button);
    });
  }
}
