/* Opt-in decision presentation. Runs inside the shared stateful runtime. */
  function updateDecisionPage(p) {
    const node = element(p);
    const heading = $('h1', node);
    const marker = $('[data-decision-status]', node);
    if (!marker) return;
    let title = p.title, label = 'PRIORITY FOR INVESTIGATION', met = true;
    if (p.kind === 'ranking') {
      const constrained = state[p.id].scenario === 'constrained';
      title = constrained ? p.title : 'North leads; Central ranks second in the base case';
      label = constrained ? 'EAST RANKS SECOND UNDER CONSTRAINT' : 'BASE CASE | CENTRAL RANKS SECOND';
      const rank = Number($('[data-hero]',node).textContent);
      $('.hero-unit',node).textContent = ['th','st','nd','rd'][rank] || 'th';
    }
    if (p.kind === 'model') {
      const adoption = state[p.id].input, actual = value(p), model = p.model;
      met = actual >= model.threshold;
      title = met ? `${adoption}% adoption meets the $${(model.threshold/100).toFixed(1)}m annual-value gate` : `${adoption}% adoption falls short of the annual-value gate`;
      label = met ? 'VALUE GATE MET' : 'VALUE GATE NOT MET';
      $('.hero-unit',node).textContent = 'm/year';
      const minimum = (model.threshold-model.intercept)/model.coefficient;
      $('.panel-copy',node).textContent = `Minimum adoption: ${fmt(minimum)}%. Readiness and staffing must also pass.`;
      const baseline = model.intercept + model.coefficient*p.input.initial;
      const bx = 100+(p.input.initial-p.input.min)/(p.input.max-p.input.min)*850;
      const by = 490-(baseline-model.domain[0])/(model.domain[1]-model.domain[0])*420;
      const ghost = $('[data-baseline-point]',node), caption = $('[data-baseline-label]',node);
      ghost.setAttribute('cx',bx); ghost.setAttribute('cy',by);
      ghost.style.display = caption.style.display = adoption === p.input.initial ? 'none' : '';
      caption.setAttribute('x',bx+24); caption.setAttribute('y',by+46);
      caption.textContent = `Initial: $${(baseline/100).toFixed(1)}m`;
      const reset = $('[data-model-reset]',node);
      reset.disabled = adoption === p.input.initial;
      reset.onclick = () => {
        state[p.id].input = p.input.initial; updateAll();
        status(`Reset to ${p.input.initial}% adoption.`);
      };
    }
    if (p.kind === 'gap') {
      const actual = score(p);
      met = actual >= p.threshold;
      title = met ? `Readiness reaches ${actual}; the execution gate is ${p.threshold}` : `Readiness falls to ${actual}; close the ${p.threshold-actual}-point gap`;
      label = met ? 'EXECUTION GATE MET' : 'EXECUTION GATE NOT MET';
      $('.panel-copy',node).textContent = met ? 'Manager capacity and integration are both required at these scores.' : 'Restore the missing capacity before adding East.';
    }
    if (p.kind === 'sequence') {
      const checks = gateChecks(p), passed = checks.filter(c=>c.pass).length;
      met = passed === checks.length;
      label = `${passed} OF ${checks.length} CONDITIONS MET`;
      title = met ? 'Add East only after Week 6 review; decide on scale at Week 12' : 'Hold East until every condition passes; continue North';
      // The week number is a milestone, not an approval or a readiness score.
      $('.hero-unit',node).textContent = 'Week';
    }
    heading.textContent = title;
    marker.textContent = label;
    marker.dataset.met = String(met);
    node.dataset.decision = met ? 'met' : 'hold';
    const quantity = $('[data-hero]',node).textContent;
    const spoken = p.kind === 'model' ? `$${quantity} million per year` : p.kind === 'ranking' ? `Rank ${quantity}` : p.kind === 'sequence' ? `Week ${quantity}` : `${quantity} ${p.kind === 'gap' ? 'points' : 'percent'}`;
    $('.hero-number',node).setAttribute('aria-label', `${spoken}. ${label}. Select to view evidence.`);
  }
