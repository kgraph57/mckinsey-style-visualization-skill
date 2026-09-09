/* Presentation UI uses only escaped SVGs produced by the local renderer. */
export function createPresenter({ getResults, getHtml, getTitle }) {
  const ja = document.documentElement.lang === 'ja';
  const dialog = document.createElement('dialog');
  dialog.className = 'mobile-presenter';
  dialog.setAttribute('aria-label', ja ? 'プレゼンテーション' : 'Presentation');
  const stage = document.createElement('div');
  stage.className = 'presenter-stage';
  const controls = document.createElement('div');
  controls.className = 'presenter-controls';
  function button(label, action) {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = label;
    b.addEventListener('click', action); controls.append(b); return b;
  }
  let current = 0, slides = [], previousTitle = '';
  const previous = button(ja ? '← 前へ' : '← Previous', () => show(current - 1));
  const count = document.createElement('span'); count.setAttribute('aria-live', 'polite'); controls.append(count);
  const next = button(ja ? '次へ →' : 'Next →', () => show(current + 1));
  button(ja ? 'PDF / 印刷' : 'PDF / Print', () => window.print());
  const full = button(ja ? '全画面' : 'Full screen', async () => {
    try { if (document.fullscreenElement === dialog) await document.exitFullscreen(); else await dialog.requestFullscreen(); } catch { /* Modal remains usable without fullscreen support. */ }
  });
  full.hidden = !dialog.requestFullscreen;
  button(ja ? '閉じる' : 'Close', () => dialog.close());
  const hint = document.createElement('p'); hint.className = 'presenter-hint';
  hint.textContent = ja ? '左右にスワイプして移動。PDFは印刷画面で横向きを選び、共有メニューから保存。' : 'Swipe to move. For PDF, choose landscape in the print dialog, then share or save.';
  dialog.append(stage, controls, hint); document.body.append(dialog);
  function show(index) {
    current = Math.max(0, Math.min(index, slides.length - 1));
    [...stage.children].forEach((slide, i) => { slide.hidden = i !== current; });
    count.textContent = `${current + 1} / ${slides.length}`;
    previous.disabled = current === 0; next.disabled = current === slides.length - 1;
  }
  dialog.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); show(current + (event.key === 'ArrowRight' ? 1 : -1)); }
  });
  let start = null;
  stage.addEventListener('touchstart', event => { start = event.touches.length === 1 ? [event.touches[0].clientX, event.touches[0].clientY] : null; }, { passive: true });
  stage.addEventListener('touchend', event => {
    if (!start) return;
    const dx = event.changedTouches[0].clientX - start[0], dy = event.changedTouches[0].clientY - start[1]; start = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) show(current + (dx < 0 ? 1 : -1));
  }, { passive: true });
  stage.addEventListener('touchcancel', () => { start = null; });
  dialog.addEventListener('close', () => { document.title = previousTitle; document.body.classList.remove('presenting'); if (document.fullscreenElement === dialog) document.exitFullscreen().catch(() => {}); });
  return {
    open() {
      slides = getResults().filter(r => r.ok);
      if (!slides.length) return;
      stage.replaceChildren();
      for (const result of slides) { const page = document.createElement('div'); page.className = 'presenter-page'; page.innerHTML = result.svg; stage.append(page); }
      show(0); previousTitle = document.title; document.title = getTitle(); document.body.classList.add('presenting'); dialog.showModal();
    },
    async share() {
      if (!getHtml()) return;
      const file = new File([getHtml()], 'presentation.html', { type: 'text/html' });
      if (navigator.canShare?.({ files: [file] }) && navigator.share) {
        try { await navigator.share({ files: [file] }); return 'shared'; }
        catch (error) { if (error.name === 'AbortError') return 'cancelled'; }
      }
      const url = URL.createObjectURL(file), link = document.createElement('a');
      link.href = url; link.download = file.name; document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000); return 'downloaded';
    },
  };
}
