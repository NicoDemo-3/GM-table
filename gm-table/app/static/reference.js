// Reference layer: hover for a tooltip, click to pin a full explanation.
// Works on any page that includes #tooltip and (optionally) the .explainer bar.
// Reads window.__REF__ (glossary/abilities) and, if present, window.__CHAR__.

(function () {
  const REF = window.__REF__ || { glossary: {}, abilities: {} };
  const tip = document.getElementById('tooltip');

  function modStr(n) { return (n >= 0 ? '+' : '') + n; }

  // Resolve the {mod} placeholder for glossary entries that need a live number.
  function fillMods(text) {
    if (!text || text.indexOf('{mod}') === -1) return text;
    let v = '';
    const c = window.__CHAR__;
    if (c && c.derived) v = modStr(c.derived.initiative); // only 'initiative' uses {mod} here
    return text.replace(/\{mod\}/g, v);
  }

  // Build the reference entry for an element (term or ability).
  function entryFor(el) {
    if (el.dataset.ability) {
      const a = REF.abilities[el.dataset.ability];
      if (!a) return null;
      const mod = modStr(Number(el.dataset.mod || 0));
      return {
        title: a.name,
        text: a.covers,
        roll: (a.roll || '').replace(/\{mod\}/g, mod),
        save: (a.save || '').replace(/\{mod\}/g, mod),
      };
    }
    const g = REF.glossary[el.dataset.term];
    if (!g) return null;
    return { title: g.title, text: fillMods(g.text), roll: '', save: '' };
  }

  // ---- hover tooltip ----
  function showTip(e, entry) {
    let html = `<div class="tt-title">${entry.title}</div><div>${entry.text}</div>`;
    if (entry.roll) html += `<div class="tt-roll">🎲 ${entry.roll}</div>`;
    tip.innerHTML = html;
    tip.classList.add('show');
    positionTip(e);
  }
  function positionTip(e) {
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = e.clientX + pad, y = e.clientY + pad;
    if (x + w > innerWidth - 8) x = e.clientX - w - pad;
    if (y + h > innerHeight - 8) y = e.clientY - h - pad;
    tip.style.left = Math.max(8, x) + 'px';
    tip.style.top = Math.max(8, y) + 'px';
  }
  function hideTip() { tip.classList.remove('show'); }

  // ---- click-to-pin explainer ----
  const bar = document.getElementById('explainer');
  function pin(entry) {
    if (!bar) return;
    document.getElementById('e-title').textContent = entry.title;
    document.getElementById('e-text').textContent = entry.text;
    const rollEl = document.getElementById('e-roll');
    const parts = [];
    if (entry.roll) parts.push('🎲 ' + entry.roll);
    if (entry.save) parts.push('🛡 ' + entry.save);
    rollEl.innerHTML = parts.join('<br>');
    bar.classList.add('show');
    bar.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  if (bar) {
    document.getElementById('explainer-close').addEventListener('click', () => bar.classList.remove('show'));
  }

  // ---- delegate events ----
  function targetFor(node) {
    return node.closest('[data-term],[data-ability]');
  }
  document.addEventListener('mouseover', (e) => {
    const el = targetFor(e.target);
    if (!el) return;
    const entry = entryFor(el);
    if (entry) showTip(e, entry);
  });
  document.addEventListener('mousemove', (e) => {
    if (tip.classList.contains('show') && targetFor(e.target)) positionTip(e);
  });
  document.addEventListener('mouseout', (e) => {
    if (targetFor(e.target)) hideTip();
  });
  document.addEventListener('click', (e) => {
    const el = targetFor(e.target);
    if (!el) return;
    // don't hijack clicks on inputs/buttons inside a labelled tile
    if (e.target.closest('input, button, .pip, .toggle-chip')) return;
    const entry = entryFor(el);
    if (entry) { hideTip(); pin(entry); }
  });

  window.__REFERENCE_READY__ = true;
})();
