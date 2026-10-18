/* Original story-deck runtime. Data, drawing and evidence use one state. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('motion-data').textContent);
  const stage = document.getElementById('stage');
  const pages = [...stage.querySelectorAll('.motion-page')];
  const evidence = document.getElementById('evidence-dialog');
  const overview = document.getElementById('overview-dialog');
  const tip = document.getElementById('motion-tip');
  const cursor = document.getElementById('demo-cursor');
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  const state = Object.create(null);
  let current = 0, staticMode = false, demo = null, entryTimer = null, hintTimer = null, generation = 0;
  let evidencePage = null, evidenceItem = null, beforePrint = null;
  const $ = (selector, node = document) => node.querySelector(selector);
  const $$ = (selector, node = document) => [...node.querySelectorAll(selector)];
  const escape = text => String(text).replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
  const fmt = number => Number.isInteger(number) ? String(number) : number.toFixed(1);
  const element = page => pages[data.pages.indexOf(page)];
  const pageTitle = index => $('h1', pages[index]).textContent;
  const reduced = () => media.matches || staticMode;
  const mobile = () => innerWidth <= 760;
  const status = text => { $('#live-status').textContent = text; };
  data.pages.forEach(p => {
    state[p.id] = p.kind === 'ranking' ? {scenario:p.initial} : p.kind === 'model' ? {input:p.input.initial} :
      p.kind === 'gap' ? Object.fromEntries(p.components.filter(c => c.toggle).map(c => [c.id, Boolean(c.initial)])) :
      p.kind === 'sequence' ? {step:0} : {};
  });
  function score(p) { return p.components.reduce((total, c) => total + (c.toggle && !state[p.id][c.id] ? 0 : c.value), 0); }
  function value(p) { return p.model.intercept + p.model.coefficient * state[p.id].input; }
  function setText(page, selector, text) { const target = $(selector, element(page)); if (target) target.textContent = text; }
  function comparison(p, rows) { $('[data-comparison]', element(p)).innerHTML = rows.map(r => `<div><span>${escape(r[0])}</span><strong>${escape(r[1])}</strong></div>`).join(''); }
  function gateChecks(p) {
    return (p.conditions || []).map(c => {
      const parent = data.pages.find(item => item.id === c.page);
      const actual = parent.kind === 'model' ? value(parent) : parent.kind === 'gap' ? score(parent) : state[parent.id].scenario;
      return {label:c.label, pass:c.scenario ? actual === c.scenario : actual >= c.threshold};
    });
  }
  function updateRanking(p) {
    const selected = state[p.id].scenario;
    const order = [...p.items].sort((a,b) => b[selected] - a[selected]);
    const node = element(p), focus = p.items.find(r => r.focus) || order[0];
    const baseOrder = [...p.items].sort((a,b) => b.base - a.base);
    p.items.forEach(item => {
      const row = $(`[data-item="${item.id}"]`, node), index = order.indexOf(item);
      row.style.transform = `translateY(${index * (mobile() ? 100 : 150)}px)`;
      $('.bar-fill', row).style.transform = `scaleX(${item[selected]/p.domain[1]})`;
      $('[data-bar-value]', row).textContent = fmt(item[selected]);
      $('[data-rank]', row).textContent = index + 1;
      const delta = item[selected] - item.base;
      $('[data-bar-delta]', row).textContent = selected === 'base' ? '' : `${fmt(item.base)} → ${fmt(item[selected])}点（${delta >= 0 ? '＋' : '−'}${fmt(Math.abs(delta))}）`;
      row.setAttribute('aria-label', `${item.label} ${index+1}位 ${item[selected]}点。押すと根拠を表示`);
    });
    $$('[data-scenario]', node).forEach(b => b.setAttribute('aria-pressed', String(b.dataset.scenario === selected)));
    const rank = order.indexOf(focus) + 1, before = baseOrder.indexOf(focus) + 1;
    setText(p, '[data-hero]', rank);
    setText(p, '[data-panel-label]', `${selected === 'base' ? '通常時' : '人員制約下'}での${focus.label}の順位`);
    $('.panel-copy',node).textContent = selected === 'base' ? `通常時の第2候補は${order[1].label}。人員制約を加え、地域の順位を確かめる。` : `${order[0].label}は1位のまま、第2候補が${baseOrder[1].label}から${order[1].label}へ変わる。`;
    comparison(p, [['東部の優先度', `${focus.base} → ${focus[selected]}点`], ['通常時との差', `${focus[selected]} − ${focus.base} = ${focus[selected]-focus.base >= 0 ? '＋' : '−'}${Math.abs(focus[selected]-focus.base)}点`]]);
    setText(p, '[data-takeaway]', selected === 'base' ? `通常時の第2候補は${order[1].label}。人員制約の影響を確認してから、地域の組合せを決める。` : `${focus.label}は${before}位から${rank}位へ。北部を先行し、東部の追加は6週目の条件判定で決める。`);
  }
  function updateModel(p) {
    const adoption = state[p.id].input, annual = value(p), m = p.model, v = p.input;
    const x = 100+(adoption-v.min)/(v.max-v.min)*850;
    const y = 490-(annual-m.domain[0])/(m.domain[1]-m.domain[0])*420;
    const node = element(p);
    $('[data-slider]', node).value = adoption;
    setText(p, '[data-input-value]', `${adoption}%`);
    const point = $('[data-model-point]', node);
    point.setAttribute('cx', x); point.setAttribute('cy', y);
    $('[data-point-guide]', node).setAttribute('d', `M100 ${y}H${x}V490`);
    const label = $('[data-point-label]', node);
    label.setAttribute('x', x < 300 ? x+30 : x-26);
    label.setAttribute('y', x < 300 ? y-120 : y-26);
    label.setAttribute('text-anchor', x < 300 ? 'start' : 'end');
    label.textContent = `${fmt(annual)}万ドル`;
    setText(p, '[data-hero]', fmt(annual));
    setText(p, '[data-panel-label]', `採用率${adoption}%での年間便益`);
    const difference = annual-m.threshold;
    comparison(p, [['投資判断の基準', `${m.threshold}万ドル／年`], ['基準との差', `${fmt(annual)} − ${m.threshold} = ${difference > 0 ? '＋' : ''}${fmt(difference)}万ドル`]]);
    setText(p, '[data-formula]', `試算：${m.intercept} ＋ ${m.coefficient} × ${adoption} = ${fmt(annual)}（万ドル／年）`);
    setText(p, '[data-takeaway]', difference >= 0 ? `基準を満たす：年間便益${fmt(annual)}万ドル。東部の追加には、準備度と人員制約の確認も必要。` : `基準まで${fmt(-difference)}万ドル不足。採用率を上げるか、実証の条件を見直す。`);
  }
  function updateGap(p) {
    const node = element(p), total = score(p), maximum = p.domain[1];
    let offset = 0;
    const values = [];
    p.components.forEach(c => {
      const contribution = c.toggle && !state[p.id][c.id] ? 0 : c.value;
      const segment = $(`[data-score-part="${c.id}"]`, node);
      segment.style.transform = `translateX(${offset/maximum*100}%) scaleX(${contribution/maximum})`;
      offset += contribution; values.push(contribution);
      if (c.toggle) {
        $(`[data-toggle="${c.id}"]`, node).checked = state[p.id][c.id];
        $(`[data-part-value="${c.id}"]`, node).innerHTML = `${contribution}<small>点</small>`;
      }
    });
    $('.score-reference', node).style.width = `${p.components.reduce((s,c)=>s+c.value,0)/maximum*100}%`;
    const missing = $('[data-missing]', node);
    missing.hidden = total >= p.threshold;
    missing.style.transform = `translateX(${total/maximum*100}%) scaleX(${Math.max(0,p.threshold-total)/maximum})`;
    setText(p, '[data-hero]', total);
    setText(p, '[data-panel-label]', total >= p.threshold ? '実行準備度は基準を上回る' : '実行準備度は基準に届かない');
    setText(p, '[data-gap-message]', total >= p.threshold ? `基準を${total-p.threshold}点上回る` : `基準まで${p.threshold-total}点不足`);
    comparison(p, [['実行判断の基準', `${p.threshold}点以上`], ['基準との差', `${total} − ${p.threshold} = ${total-p.threshold > 0 ? '＋' : ''}${total-p.threshold}点`]]);
    setText(p, '[data-formula]', `試算：${values.join(' ＋ ')} = ${total}点`);
    setText(p, '[data-takeaway]', total >= p.threshold ? `準備度は${total}点。管理者の対応枠を確保してから、東部の追加を判断する。` : `${p.threshold-total}点が不足。管理者枠や連携の条件を見直し、実行できる水準まで整える。`);
  }
  function updateSequence(p) {
    const node = element(p), step = p.steps[state[p.id].step], checks = gateChecks(p);
    const ready = checks.every(c => c.pass);
    const lastWeek = p.steps[p.steps.length-1].week;
    const x = 260+(step.week-1)/(lastWeek-1)*750;
    $('[data-now-line]', node).setAttribute('transform', `translate(${x} 0)`);
    setText(p, '[data-now-label]', `いま W${step.week}`);
    $$('[data-task]', node).forEach(rect => {
      const task = p.tasks[Number(rect.dataset.task)];
      const fraction = task.conditional && !ready ? 0 : step.week < task.start ? 0 : task.end === task.start ? 1 : Math.min(1, (step.week-task.start+1)/(task.end-task.start+1));
      rect.style.transform = `scaleX(${fraction})`;
    });
    setText(p, '[data-hero]', step.week);
    const held=step.conditional&&!ready;
    setText(p, '[data-panel-label]', held ? step.holdLabel : step.label);
    $('.panel-copy', node).textContent = held ? step.holdDetail : step.detail;
    $$('[data-mobile-step]',node).forEach(li=>{
      const i=Number(li.dataset.mobileStep),s=p.steps[i],blocked=s.conditional&&!ready;
      li.classList.toggle('completed',i<=state[p.id].step&&!blocked);
      li.classList.toggle('current',i===state[p.id].step);
      $('[data-mobile-step-label]',li).textContent=blocked?s.holdLabel:s.label;
      $('[data-mobile-step-detail]',li).textContent=blocked?s.holdDetail:s.detail;
    });
    comparison(p, checks.slice(0,2).map(c => [c.label, c.pass ? '条件を満たす' : '条件に届かない']));
    const next = $('[data-next-step]', node);
    next.disabled = state[p.id].step >= p.steps.length-1;
    next.textContent = next.disabled ? '12週目まで確認済み' : '次の工程へ ›';
    setText(p, '[data-gate-status]', checks.map(c => `${c.label}：${c.pass ? '可' : '未達'}`).join('　／　'));
    setText(p, '[data-takeaway]', p.tasks.some(t=>t.conditional&&step.week>=t.start) && !ready ? '現在の条件では東部を追加できません。北部の実証を続け、全体展開は別に判断します。' : step.detail);
  }
  function update(p) {
    if (p.kind === 'evidence') {
      p.items.forEach((r,i) => { $(`[data-item="${r.id}"]`, element(p)).style.transform = `translateY(${i*(mobile()?100:165)}px)`; });
    }
    if (p.kind === 'ranking') updateRanking(p);
    if (p.kind === 'model') updateModel(p);
    if (p.kind === 'gap') updateGap(p);
    if (p.kind === 'sequence') updateSequence(p);
    if (data.design === 'decision') updateDecisionPage(p);
  }
  function updateAll() { data.pages.forEach(update); }
  function fit() {
    if (!mobile() && !document.body.hasAttribute('data-static')) {
      const scale = Math.min((innerWidth-32)/1920, (innerHeight-88)/1080);
      stage.style.transform = `scale(${scale})`;
      stage.style.left = `${(innerWidth-1920*scale)/2}px`;
      stage.style.top = `${Math.max(8,(innerHeight-76-1080*scale)/2)}px`;
    }
    updateAll();
    if (overview.open) fitPreviews();
  }
  function writeHash() { history.replaceState(null,'',`#p${current+1}${staticMode?'.static':''}`); }
  function closeDialog(dialog) { if (dialog.open) dialog.close(); }
  function go(index, from=null, write=true) {
    if (typeof index === 'string') index = data.pages.findIndex(p => p.id === index);
    if (index < 0 || index >= pages.length) return;
    const origin = from ? from.getBoundingClientRect() : null;
    closeDialog(evidence); closeDialog(overview); tip.hidden = true;
    generation++; clearTimeout(entryTimer); clearTimeout(hintTimer);
    $$('.hint-ring',stage).forEach(el=>el.classList.remove('hint-ring'));
    pages.forEach((page,i) => {
      page.getAnimations().forEach(a => a.cancel());
      page.classList.toggle('active', i === index); page.inert = i !== index;
      if (i !== index) page.classList.remove('built');
    });
    current = index;
    updateAll();
    const page = pages[current], token = generation;
    page.classList.remove('built');
    const reveal = () => { if (generation === token) page.classList.add('built'); };
    if (reduced()) reveal();
    else {
      entryTimer = setTimeout(reveal, 50);
      const hint = $('[data-go], [data-scenario], [data-item].focus, [data-slider], [data-toggle], [data-next-step]',page);
      if(hint){hint.classList.add('hint-ring');hintTimer=setTimeout(()=>hint.classList.remove('hint-ring'),2000);}
      if (origin && !mobile()) {
        const frame = stage.getBoundingClientRect(), scale = frame.width/1920;
        page.style.transformOrigin = `${(origin.x+origin.width/2-frame.x)/scale}px ${(origin.y+origin.height/2-frame.y)/scale}px`;
        page.animate([{opacity:.4,transform:'scale(.965)'},{opacity:1,transform:'scale(1)'}], {duration:420,easing:'cubic-bezier(.23,1,.32,1)'});
      }
    }
    $('[data-page-count]').textContent = `${String(current+1).padStart(2,'0')} / ${String(pages.length).padStart(2,'0')}`;
    $('[data-prev]').disabled = current === 0; $('[data-next]').disabled = current === pages.length-1;
    if (mobile()) scrollTo({top:0,behavior:'instant'});
    if (write) writeHash();
    status(`${current+1}ページ。${pageTitle(current)}`);
  }
  function openEvidence(p, item=null) {
    evidencePage = p; evidenceItem = item;
    $('.drawer-crumb', evidence).textContent = `${p.section} › ${item ? item.label : '判断の根拠'}`;
    $('#evidence-head').textContent = p.evidence.head;
    $('.drawer-source', evidence).textContent = `${p.source}。${data.disclosure}。`;
    setTab('detail');
    if (!evidence.open) evidence.showModal();
    evidence.scrollTop = 0;
  }
  function setTab(tab) {
    $$('[data-tab]', evidence).forEach(b => { const on = b.dataset.tab === tab; b.setAttribute('aria-selected',String(on)); b.tabIndex = on ? 0 : -1; });
    const content = $('#drawer-content');
    content.setAttribute('aria-labelledby', tab === 'detail' ? 'evidence-detail' : 'evidence-source');
    const p = evidencePage;
    if (tab === 'source') content.innerHTML = p.evidence.assumptions.map(text => `<p>${escape(text)}</p>`).join('');
    else {
      let currentValue = '';
      if (evidenceItem) currentValue = `<p class="drawer-selected">選択した項目：${escape(evidenceItem.label)}</p>`;
      if (p.kind === 'model') currentValue = `<p class="drawer-selected">現在：採用率${state[p.id].input}% → ${fmt(value(p))}万ドル／年</p>`;
      if (p.kind === 'gap') currentValue = `<p class="drawer-selected">現在の準備度：${score(p)}点／基準${p.threshold}点</p>`;
      content.innerHTML = currentValue + '<table><thead><tr>' + p.evidence.headers.map(h=>`<th scope="col">${escape(h)}</th>`).join('') + '</tr></thead><tbody>' + p.evidence.rows.map(row=>'<tr>'+row.map((v,i)=>`<${i?'td':'th scope="row"'}>${escape(v)}</${i?'td':'th'}>`).join('')+'</tr>').join('') + '</tbody></table>';
    }
    if (p.kind === 'sequence' && tab === 'detail') {
      (p.conditions || []).forEach(c => {
        const b = document.createElement('button'); b.type = 'button'; b.className = 'drawer-link';
        b.textContent = `${c.label}のページへ ›`; b.onclick = () => go(c.page); content.append(b);
      });
    }
  }
  function fitPreviews() {
    $$('.preview-box', overview).forEach(box => { $('.motion-page', box).style.transform = `scale(${box.clientWidth/1920})`; });
  }
  function openOverview() {
    closeDialog(evidence);
    const grid = $('.overview-grid'); grid.replaceChildren();
    pages.forEach((page,index) => {
      const card = document.createElement('button'); card.type = 'button'; card.className = 'overview-card';
      card.setAttribute('aria-current', String(index === current)); card.setAttribute('aria-label',`${index+1}ページ ${pageTitle(index)}`);
      const preview = document.createElement('div'); preview.className = 'preview-box'; preview.setAttribute('aria-hidden','true');
      const copy = page.cloneNode(true); copy.removeAttribute('id'); copy.inert = true; copy.classList.add('built'); copy.style.transformOrigin='0 0';
      $$('[id]', copy).forEach(el => el.removeAttribute('id'));
      $$('button,input', copy).forEach(el => { const span = document.createElement('span'); span.className = el.className; span.style.cssText = el.style.cssText; span.innerHTML = el.innerHTML; el.replaceWith(span); });
      preview.append(copy); card.append(preview);
      const caption = document.createElement('div'); caption.className = 'overview-card-caption';
      caption.innerHTML = `<strong>${String(index+1).padStart(2,'0')}</strong>${escape(pageTitle(index))}`;
      card.append(caption); card.onclick = () => go(index); grid.append(card);
    });
    overview.showModal(); fitPreviews();
  }
  function showTip(row,p,event) {
    if (!matchMedia('(hover:hover) and (pointer:fine)').matches || evidence.open) return;
    const item = p.items.find(r=>r.id===row.dataset.item), n = p.kind==='ranking' ? item[state[p.id].scenario] : item.value;
    tip.innerHTML = `<strong>${fmt(n)}${p.kind==='ranking'?'点':'%'}</strong>${escape(item.label)}<small>${escape(p.source)}</small>`;
    tip.hidden = false;
    const box = row.getBoundingClientRect();
    tip.style.left = `${Math.max(8,Math.min(innerWidth-tip.offsetWidth-12,event.clientX+18 || box.x+80))}px`;
    tip.style.top = `${Math.max(8,Math.min(innerHeight-tip.offsetHeight-12,event.clientY+18 || box.y+20))}px`;
  }
  function finalStates() {
    data.pages.forEach(p => {
      if (p.kind==='ranking') state[p.id].scenario = p.initial;
      if (p.kind==='model') state[p.id].input = p.input.initial;
      if (p.kind==='gap') p.components.filter(c=>c.toggle).forEach(c=>{state[p.id][c.id]=true;});
      if (p.kind==='sequence') state[p.id].step = p.steps.length-1;
    }); updateAll();
  }
  function applyStatic(on, write=true) {
    staticMode = on; document.documentElement.classList.toggle('no-motion',on || media.matches);
    $('[data-static-toggle]').setAttribute('aria-pressed',String(on));
    if (on) finalStates();
    pages.forEach(p=>p.classList.add('built')); if(write)writeHash();
  }
  data.pages.forEach(p => {
    const node = element(p);
    $$('[data-go]',node).forEach(b=>b.onclick=()=>go(b.dataset.go,b));
    $$('[data-evidence]',node).forEach(b=>b.onclick=()=>openEvidence(p));
    $$('[data-item]',node).forEach(row=>{
      row.onclick=()=>openEvidence(p,p.items.find(r=>r.id===row.dataset.item));
      row.addEventListener('pointerenter', e=>showTip(row,p,e));
      row.addEventListener('pointermove',e=>showTip(row,p,e));
      row.addEventListener('pointerleave',()=>{tip.hidden=true;});
    });
    $$('[data-scenario]',node).forEach(b=>b.onclick=()=>{
      state[p.id].scenario=b.dataset.scenario; updateAll(); status($('[data-takeaway]',node).textContent);
    });
    if (p.kind==='model') $('[data-slider]',node).oninput=e=>{
      state[p.id].input=Math.max(p.input.min,Math.min(p.input.max,Number(e.target.value))); updateAll();
      status(`採用率${state[p.id].input}%。年間便益${fmt(value(p))}万ドル。`);
    };
    if (p.kind==='gap') $$('[data-toggle]',node).forEach(input=>input.onchange=()=>{
      state[p.id][input.dataset.toggle]=input.checked; updateAll(); status(`準備度${score(p)}点。`);
    });
    if (p.kind==='sequence') {
      $('[data-next-step]',node).onclick=()=>{state[p.id].step=Math.min(p.steps.length-1,state[p.id].step+1);update(p);status(p.steps[state[p.id].step].detail);};
      $('[data-step-reset]',node).onclick=()=>{state[p.id].step=0;update(p);};
    }
  });
  $$('[data-close]').forEach(b=>b.onclick=()=>b.closest('dialog').close());
  [evidence,overview].forEach(dialog=>dialog.addEventListener('click',event=>{
    if (event.target!==dialog) return;
    const r=dialog.getBoundingClientRect();
    if(event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) dialog.close();
  }));
  $$('[data-tab]',evidence).forEach(b=>{
    b.onclick=()=>setTab(b.dataset.tab);
    b.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const target=$(`[data-tab="${b.dataset.tab==='detail'?'source':'detail'}"]`,evidence);setTab(target.dataset.tab);target.focus();};
  });
  $('[data-prev]').onclick=()=>go(current-1);
  $('[data-next]').onclick=()=>go(current+1);
  $('[data-overview]').onclick=openOverview;
  $('[data-static-toggle]').onclick=()=>applyStatic(!staticMode);
  $('[data-fullscreen]').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch{status('この表示環境では全画面を利用できません。');}};
  $('[data-help]').onclick=()=>openEvidence({section:'操作方法',source:'この資料の操作',kind:'help',evidence:{head:'図や数字を押して、判断の根拠を確かめる',headers:['操作','動作'],rows:[['←・→・Space','ページを送る'],['1〜6','指定のページへ移動'],['O','全ページの一覧'],['D','自動デモを開始／停止'],['Esc','根拠や一覧を閉じる'],['静止表示','動きを止め、判断が見える状態にする']],assumptions:['入力の操作中はページ送りのキーを取りません。','根拠パネルは×、Esc、背景のクリックで閉じます。']}});
  function stopDemo() {
    if (!demo) return;
    demo.abort();demo=null;cursor.style.display='none';$('#demo-status').hidden=true;
    $('[data-demo-start]').textContent='自動デモ D';cursor.getAnimations().forEach(a=>a.cancel());
  }
  async function startDemo(options={}) {
    stopDemo();closeDialog(evidence);closeDialog(overview);
    const controller=new AbortController();demo=controller;
    const pace=Math.max(.01,Math.min(2,Number(options.pace)||1));
    $('#demo-status').hidden=false;$('#demo-status').textContent='自動デモ中 · D またはクリックで停止';
    $('[data-demo-start]').textContent='デモを停止';
    const sleep=ms=>new Promise((resolve,reject)=>{
      if(controller.signal.aborted){reject(new DOMException('Stopped','AbortError'));return;}
      const abort=()=>{clearTimeout(timer);reject(new DOMException('Stopped','AbortError'));};
      const timer=setTimeout(()=>{controller.signal.removeEventListener('abort',abort);resolve();},ms*pace);
      controller.signal.addEventListener('abort',abort,{once:true});
    });
    const touch=async(el,click=true)=>{
      if(!el)throw new Error('A demo target is missing');
      const r=el.getBoundingClientRect();
      if(!reduced()){
        cursor.style.display='block';const end=`translate(${r.x+r.width/2}px,${r.y+r.height/2}px)`;
        const a=cursor.animate([{transform:cursor.style.transform||end},{transform:end}],{duration:450*pace,easing:'cubic-bezier(.23,1,.32,1)',fill:'forwards'});
        await sleep(460);a.cancel();cursor.style.transform=end;
      }
      await sleep(200);
      if(controller.signal.aborted)throw new DOMException('Stopped','AbortError');
      if(click){cursor.classList.add('pressed');el.click();await sleep(160);cursor.classList.remove('pressed');}
      await sleep(500);
    };
    try {
      finalStates();data.pages.filter(p=>p.kind==='sequence').forEach(p=>{state[p.id].step=0;});
      go(0);await sleep(1300);
      for(let i=1;i<data.pages.length;i++){
        const p=data.pages[i], first=data.pages[0];
        const jump=$(`[data-go="${p.id}"]`,element(first));
        if(current===0 && jump)await touch(jump);else{await touch($('[data-next]'));}
        await sleep(1000);
        if(p.kind==='evidence'){
          await touch($('.bar-row.focus',element(p))||$('.bar-row',element(p)));
          await sleep(1100);await touch($('[data-tab=source]',evidence));await sleep(1000);await touch($('[data-close]',evidence));
        }else if(p.kind==='ranking'){
          await touch($('[data-scenario=base]',element(p)));await sleep(900);
          await touch($(`[data-scenario="${p.initial}"]`,element(p)));await sleep(1200);
          await touch($('[data-evidence]',element(p)));await sleep(900);await touch($('[data-close]',evidence));
        }else if(p.kind==='model'){
          const input=$('[data-slider]',element(p));await touch(input,false);
          for(const target of [p.input.min,p.input.initial]){
            const from=Number(input.value),direction=target>=from?1:-1;
            for(let n=from;n!==target;){
              n=direction>0?Math.min(target,n+p.input.step):Math.max(target,n-p.input.step);
              input.value=n;input.dispatchEvent(new Event('input',{bubbles:true}));
              if(!reduced()){
                const r=input.getBoundingClientRect();
                cursor.style.transform=`translate(${r.x+8+(n-p.input.min)/(p.input.max-p.input.min)*(r.width-16)}px,${r.y+r.height/2}px)`;
              }
              await sleep(140);
            }
            await sleep(1000);
          }
        }else if(p.kind==='gap'){
          const input=$('[data-toggle=manager]',element(p))||$('[data-toggle]',element(p));
          await touch(input);await sleep(1300);await touch(input);await sleep(1000);
        }else if(p.kind==='sequence'){
          for(let step=1;step<p.steps.length;step++){await touch($('[data-next-step]',element(p)));await sleep(1000);}
        }
      }
      cursor.style.display='none';openOverview();status('自動デモが完了しました。全ページの一覧です。');
    }catch(error){if(error.name!=='AbortError'){console.error('Motion demo:',error.message);status('デモを停止しました。');}}
    finally{if(demo===controller){demo=null;cursor.style.display='none';$('#demo-status').hidden=true;$('[data-demo-start]').textContent='自動デモ D';}}
  }
  $('[data-demo-start]').onclick=()=>demo?stopDemo():startDemo();
  document.addEventListener('pointerdown',e=>{if(e.isTrusted && demo)stopDemo();},true);
  document.addEventListener('keydown',event=>{
    const edit=event.target.closest('input,textarea,select,[contenteditable=true]');
    if(event.key==='Escape'){stopDemo();if(!evidence.open&&!overview.open&&current!==0)go(0);return;}
    if(event.key.toLowerCase()==='d' && demo && !event.altKey && !event.ctrlKey && !event.metaKey){event.preventDefault();stopDemo();return;}
    if(edit || evidence.open || overview.open || event.altKey || event.ctrlKey || event.metaKey)return;
    if(/^[1-9]$/.test(event.key)){go(Number(event.key)-1);return;}
    if(event.key.toLowerCase()==='o'){event.preventDefault();openOverview();return;}
    if(event.key.toLowerCase()==='d'){event.preventDefault();demo?stopDemo():startDemo();return;}
    if(event.target.closest('button,a'))return;
    if(['ArrowRight','ArrowLeft',' '].includes(event.key)){
      event.preventDefault();document.documentElement.classList.add('no-motion');
      go(current+(event.key==='ArrowLeft'?-1:1));
      requestAnimationFrame(()=>{if(!reduced())document.documentElement.classList.remove('no-motion');});
    }
  });
  function readHash(){const raw=location.hash;const found=raw.match(/(?:p|slide=)(\d+)/);applyStatic(raw.includes('static') || document.body.hasAttribute('data-static'),false);go(found?Math.min(pages.length-1,Math.max(0,Number(found[1])-1)):0,null,false);}
  addEventListener('hashchange',readHash);
  addEventListener('resize',fit);
  media.addEventListener('change',()=>document.documentElement.classList.toggle('no-motion',reduced()));
  addEventListener('beforeprint',()=>{beforePrint=JSON.stringify(state);finalStates();});
  addEventListener('afterprint',()=>{if(beforePrint){Object.assign(state,JSON.parse(beforePrint));updateAll();beforePrint=null;}});
  document.documentElement.classList.add('js');
  fit();readHash();
  const staticAll=document.body.hasAttribute('data-static');
  if(staticAll){finalStates();pages.forEach(p=>{p.inert=false;p.classList.add('built');});}
  window.MotionDeck=Object.freeze({
    go:target=>go(target),startDemo,stopDemo,
    snapshot:()=>({page:current+1,state:JSON.parse(JSON.stringify(state)),demo:Boolean(demo),overview:overview.open,evidence:evidence.open,static:staticMode})
  });
})();
