// Infinite-canvas dashboard with focus presets.
// Presets reference shared window configs (windows[]); removing a window only
// drops it from the preset's members — its config stays in the stash to re-add.
// The "shared layout" toggle decides whether geometry lives globally (one position
// everywhere) or per-preset (each preset keeps its own override).
(function () {
  const cid = window.__CID__;
  const TOOLS = window.__TOOLS__ || [];
  let C = window.__CANVAS__;
  C.windows = C.windows || {};
  C.presets = C.presets || [{ id: 'p_default', name: 'Default', members: [], pan: { x: 0, y: 0 }, zoom: 1, overrides: {} }];
  C.active = C.active || C.presets[0].id;

  const wrap = document.getElementById('wrap');
  const surface = document.getElementById('surface');
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const uid = (p) => p + Math.random().toString(36).slice(2, 8);

  const preset = () => C.presets.find((p) => p.id === C.active) || C.presets[0];
  function geom(id) {
    const base = C.windows[id] || { x: 60, y: 60, w: 360, h: 300 };
    if (C.shared) return { x: base.x, y: base.y, w: base.w, h: base.h };
    const ov = (preset().overrides || {})[id] || {};
    return { x: ov.x != null ? ov.x : base.x, y: ov.y != null ? ov.y : base.y, w: ov.w != null ? ov.w : base.w, h: ov.h != null ? ov.h : base.h };
  }
  function setGeom(id, g) {
    if (C.shared) { Object.assign(C.windows[id], g); }
    else { const p = preset(); p.overrides = p.overrides || {}; p.overrides[id] = Object.assign(p.overrides[id] || {}, g); }
  }

  // ---- save (debounced) ----
  let saveT = null;
  function save() { clearTimeout(saveT); saveT = setTimeout(() => {
    fetch('/api/campaign/' + cid + '/canvas', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(C) });
  }, 400); }

  // ---- transform ----
  function applyTransform() {
    const p = preset();
    surface.style.transform = `translate(${p.pan.x}px, ${p.pan.y}px) scale(${p.zoom || 1})`;
  }

  // ---- render windows ----
  function render() {
    const p = preset();
    surface.innerHTML = (p.members || []).map((id) => {
      const w = C.windows[id]; if (!w) return '';
      const g = geom(id);
      return `<div class="cv-win" data-id="${id}" style="left:${g.x}px;top:${g.y}px;width:${g.w}px;height:${g.h}px">
        <div class="cv-bar" data-drag="${id}"><span>${esc(w.title)}</span><button class="cv-x" data-close="${id}">&times;</button></div>
        <div class="cv-body"><iframe src="/c/${cid}/${w.type}" loading="lazy"></iframe></div>
        <div class="cv-resize" data-resize="${id}"></div>
      </div>`;
    }).join('');
    surface.querySelectorAll('[data-drag]').forEach((bar) => dragWin(bar));
    surface.querySelectorAll('[data-resize]').forEach((h) => resizeWin(h));
    surface.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation(); const id = b.dataset.close;
      preset().members = preset().members.filter((x) => x !== id);  // keep C.windows[id] (stash)
      render(); renderDock(); save();
    }));
    applyTransform();
  }

  function dragWin(bar) {
    const id = bar.dataset.drag, el = bar.closest('.cv-win');
    let on = false, sx = 0, sy = 0, g0;
    bar.addEventListener('pointerdown', (e) => {
      if (e.target.classList.contains('cv-x')) return;
      on = true; bar.setPointerCapture(e.pointerId); sx = e.clientX; sy = e.clientY; g0 = geom(id);
    });
    bar.addEventListener('pointermove', (e) => {
      if (!on) return; const z = preset().zoom || 1;
      const g = { x: g0.x + (e.clientX - sx) / z, y: g0.y + (e.clientY - sy) / z, w: g0.w, h: g0.h };
      el.style.left = g.x + 'px'; el.style.top = g.y + 'px'; setGeom(id, g);
    });
    bar.addEventListener('pointerup', () => { if (on) { on = false; save(); } });
  }
  function resizeWin(h) {
    const id = h.dataset.resize, el = h.closest('.cv-win');
    let on = false, sx = 0, sy = 0, g0;
    h.addEventListener('pointerdown', (e) => { e.stopPropagation(); on = true; h.setPointerCapture(e.pointerId); sx = e.clientX; sy = e.clientY; g0 = geom(id); });
    h.addEventListener('pointermove', (e) => {
      if (!on) return; const z = preset().zoom || 1;
      const g = { x: g0.x, y: g0.y, w: Math.max(220, g0.w + (e.clientX - sx) / z), h: Math.max(140, g0.h + (e.clientY - sy) / z) };
      el.style.width = g.w + 'px'; el.style.height = g.h + 'px'; setGeom(id, g);
    });
    h.addEventListener('pointerup', () => { if (on) { on = false; save(); } });
  }

  // ---- pan + zoom ----
  let panning = false, px = 0, py = 0, pan0;
  wrap.addEventListener('pointerdown', (e) => {
    if (e.target !== wrap && e.target !== surface) return;
    panning = true; wrap.classList.add('panning'); px = e.clientX; py = e.clientY; pan0 = { ...preset().pan };
  });
  window.addEventListener('pointermove', (e) => {
    if (!panning) return;
    preset().pan = { x: pan0.x + (e.clientX - px), y: pan0.y + (e.clientY - py) }; applyTransform();
  });
  window.addEventListener('pointerup', () => { if (panning) { panning = false; wrap.classList.remove('panning'); save(); } });
  function zoom(d) { const p = preset(); p.zoom = Math.min(2, Math.max(0.3, (p.zoom || 1) + d)); applyTransform(); save(); }
  document.getElementById('zin').onclick = () => zoom(0.1);
  document.getElementById('zout').onclick = () => zoom(-0.1);
  document.getElementById('zreset').onclick = () => { const p = preset(); p.zoom = 1; p.pan = { x: 0, y: 0 }; applyTransform(); save(); };

  // ---- add / re-add windows ----
  function addWindow(type, title) {
    // re-use a stashed window of this type (not in current preset) so its config survives
    const inPreset = new Set(preset().members);
    const stashed = Object.values(C.windows).find((w) => w.type === type && !inPreset.has(w.id));
    if (stashed) { preset().members.push(stashed.id); }
    else {
      const id = uid('w_');
      const n = preset().members.length;
      C.windows[id] = { id, type, title, x: 40 + n * 28, y: 40 + n * 28, w: 380, h: 320 };
      preset().members.push(id);
    }
    render(); renderDock(); save();
  }

  // ---- dock ----
  function renderDock() {
    const pl = document.getElementById('presets');
    pl.innerHTML = C.presets.map((p) =>
      `<div class="cv-preset ${p.id === C.active ? 'active' : ''}" data-p="${p.id}">
        <span style="flex:1">${esc(p.name)}</span>
        <span data-ren="${p.id}" title="Rename" style="cursor:pointer">✎</span>
        ${C.presets.length > 1 ? `<span data-delp="${p.id}" title="Delete" style="cursor:pointer">×</span>` : ''}</div>`).join('');
    pl.querySelectorAll('.cv-preset').forEach((el) => el.addEventListener('click', (e) => {
      if (e.target.dataset.ren || e.target.dataset.delp) return;
      C.active = el.dataset.p; render(); renderDock(); save();
    }));
    pl.querySelectorAll('[data-ren]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation(); const p = C.presets.find((x) => x.id === b.dataset.ren);
      const n = prompt('Preset name:', p.name); if (n) { p.name = n; renderDock(); save(); }
    }));
    pl.querySelectorAll('[data-delp]').forEach((b) => b.addEventListener('click', (e) => {
      e.stopPropagation(); C.presets = C.presets.filter((x) => x.id !== b.dataset.delp);
      if (C.active === b.dataset.delp) C.active = C.presets[0].id;
      render(); renderDock(); save();
    }));

    document.getElementById('shared').checked = !!C.shared;
    document.getElementById('addwins').innerHTML = TOOLS.map(([type, label]) =>
      `<button class="btn ghost" style="font-size:11px;padding:4px 8px" data-add="${type}" data-title="${esc(label)}">${esc(label)}</button>`).join('');
    document.querySelectorAll('[data-add]').forEach((b) => b.addEventListener('click', () => addWindow(b.dataset.add, b.dataset.title)));

    // stash: windows not in the active preset (kept configs)
    const inPreset = new Set(preset().members);
    const stash = Object.values(C.windows).filter((w) => !inPreset.has(w.id));
    document.getElementById('stash').innerHTML = stash.length
      ? stash.map((w) => `<div class="cv-preset"><span style="flex:1">${esc(w.title)}</span>
          <span data-readd="${w.id}" style="cursor:pointer" title="Add back">＋</span>
          <span data-purge="${w.id}" style="cursor:pointer" title="Delete for good">🗑</span></div>`).join('')
      : '<div class="sec-empty" style="font-size:12px">None</div>';
    document.querySelectorAll('[data-readd]').forEach((b) => b.addEventListener('click', () => { preset().members.push(b.dataset.readd); render(); renderDock(); save(); }));
    document.querySelectorAll('[data-purge]').forEach((b) => b.addEventListener('click', () => { delete C.windows[b.dataset.purge]; renderDock(); save(); }));
  }

  document.getElementById('add-preset').onclick = () => {
    const name = prompt('New preset name:', 'Preset ' + (C.presets.length + 1)); if (!name) return;
    const id = uid('p_'); C.presets.push({ id, name, members: [...preset().members], pan: { ...preset().pan }, zoom: preset().zoom || 1, overrides: {} });
    C.active = id; render(); renderDock(); save();
  };
  document.getElementById('shared').onchange = (e) => { C.shared = e.target.checked; render(); save(); };
  let dockOpen = true;
  document.getElementById('dock-toggle').onclick = () => { dockOpen = !dockOpen; document.getElementById('dock').classList.toggle('collapsed', !dockOpen); };

  render(); renderDock();
})();
