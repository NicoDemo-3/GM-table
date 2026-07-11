// Sheet Builder: drop Widget Library widgets onto a card canvas and position them.
// Saves a per-card layout (campaign.layouts[card]) that the card renderers consume.
(function () {
  const cid = window.__CID__;
  const LIB = window.__LIB__ || [];
  const LAYOUTS = window.__LAYOUTS__ || {};
  const CARDS = window.__CARDS__ || ['sheet', 'party', 'combat', 'npc', 'bestiary'];
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  let card = 'party';
  let items = (LAYOUTS[card] || []).slice();

  const canvas = document.getElementById('canvas');
  const palette = document.getElementById('palette');

  // card tabs
  document.getElementById('cardtabs').innerHTML = CARDS.map((c) =>
    `<button class="btn ghost ctab" data-card="${c}">${c[0].toUpperCase() + c.slice(1)} card</button>`).join('');
  document.querySelectorAll('.ctab').forEach((b) => b.addEventListener('click', () => {
    card = b.dataset.card; items = (LAYOUTS[card] || []).slice();
    document.querySelectorAll('.ctab').forEach((x) => x.classList.toggle('on', x.dataset.card === card));
    setPreview(); renderPalette(); renderCanvas();
  }));

  function forCard() { return LIB.filter((w) => (w.cards || []).includes(card)); }
  function renderPalette() {
    palette.innerHTML = forCard().map((w) =>
      `<button class="btn ghost palitem" data-wid="${w.id}">${esc(w.label)}
        <span style="color:var(--ink-soft);font-size:10px">${w.source === 'system' ? 'sys' : 'custom'}</span></button>`).join('')
      || '<p class="sec-empty">No widgets target this card. Add some in the Widget Library.</p>';
    palette.querySelectorAll('.palitem').forEach((b) => b.addEventListener('click', () => {
      const w = LIB.find((x) => x.id === b.dataset.wid);
      items.push({ wid: w.id, key: w.key || w.id, label: w.label, source: w.source, describes: w.describes || null, type: w.type, x: 12, y: 12 });
      renderCanvas();
    }));
  }
  function renderCanvas() {
    canvas.innerHTML = items.map((it, i) =>
      `<div class="bld-w" data-i="${i}" style="left:${it.x}px;top:${it.y}px">
        <span class="bld-lb">${esc(it.label)}</span><span class="bld-val">·</span>
        <button class="bld-rm" data-rm="${i}">×</button></div>`).join('');
    canvas.querySelectorAll('.bld-w').forEach((el) => drag(el));
    canvas.querySelectorAll('.bld-rm').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation(); items.splice(Number(b.dataset.rm), 1); renderCanvas();
    }));
  }
  function drag(el) {
    const i = Number(el.dataset.i);
    let on = false, ox = 0, oy = 0;
    el.addEventListener('pointerdown', (e) => {
      if (e.target.classList.contains('bld-rm')) return;
      on = true; el.setPointerCapture(e.pointerId);
      const r = canvas.getBoundingClientRect();
      ox = e.clientX - r.left - items[i].x; oy = e.clientY - r.top - items[i].y;
    });
    el.addEventListener('pointermove', (e) => {
      if (!on) return;
      const r = canvas.getBoundingClientRect();
      items[i].x = Math.max(0, Math.min(r.width - 40, e.clientX - r.left - ox));
      items[i].y = Math.max(0, Math.min(r.height - 20, e.clientY - r.top - oy));
      el.style.left = items[i].x + 'px'; el.style.top = items[i].y + 'px';
    });
    el.addEventListener('pointerup', () => { on = false; });
  }

  function setPreview() { document.getElementById('preview').href = '/c/' + cid + '/cards/' + card; }

  document.getElementById('save').addEventListener('click', async () => {
    const r = await fetch('/api/campaign/' + cid + '/layout/' + card, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(items),
    });
    LAYOUTS[card] = items.slice();
    document.getElementById('save').textContent = r.ok ? 'Saved ✓' : 'Failed';
    setTimeout(() => document.getElementById('save').textContent = 'Save layout', 1200);
  });

  document.querySelector('.ctab[data-card="party"]').classList.add('on');
  setPreview(); renderPalette(); renderCanvas();
})();
