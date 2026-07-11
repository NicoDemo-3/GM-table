// DM map: cell-based fog of war + draggable tokens.
// Fog mask and tokens both sync over the campaign room; the image is a URL.
// Tokens are DOM elements positioned as a % of the image, so they scale with it.

(function () {
  const cid = window.__CID__;
  const socket = io();
  let M = window.__MAP__ || {};
  M.fog = M.fog || { cols: 0, rows: 0, cell: 48, revealed: [] };
  M.tokens = M.tokens || [];

  const cv = document.getElementById('map');
  const ctx = cv.getContext('2d');
  const noimg = document.getElementById('noimg');
  const stage = document.getElementById('stage');
  const layer = document.getElementById('tokens');
  let img = null;
  let revealed = new Set(M.fog.revealed || []);
  let mode = 'reveal';
  let dmOpacity = parseFloat(localStorage.getItem('gmFogOpacity'));
  if (isNaN(dmOpacity)) dmOpacity = 0.4;
  let selId = null;

  const uid = () => 't' + Math.random().toString(36).slice(2, 8);
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  socket.on('connect', () => socket.emit('join', { campaignId: cid }));

  function loadImage() {
    if (!M.image) { stage.style.display = 'none'; noimg.style.display = 'block'; return; }
    img = new Image();
    img.onload = () => {
      cv.width = img.naturalWidth; cv.height = img.naturalHeight;
      stage.style.display = 'inline-block'; noimg.style.display = 'none';
      const cell = M.fog.cell || 48;
      if (!M.fog.cols) {
        M.fog.cols = Math.ceil(img.naturalWidth / cell);
        M.fog.rows = Math.ceil(img.naturalHeight / cell);
        revealed = new Set(); commitFog(false);
      }
      draw(); renderTokens();
    };
    img.src = M.image;
  }
  function draw() {
    if (!img) return;
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.drawImage(img, 0, 0);
    const f = M.fog, cell = f.cell || 48;
    ctx.fillStyle = 'rgba(0,0,0,' + dmOpacity + ')';
    for (let y = 0; y < f.rows; y++)
      for (let x = 0; x < f.cols; x++)
        if (!revealed.has(y * f.cols + x)) ctx.fillRect(x * cell, y * cell, cell, cell);
    if (M.grid && M.grid.show) {
      const g = M.grid.size || 70;
      ctx.strokeStyle = 'rgba(255,255,255,.25)'; ctx.lineWidth = 1;
      for (let x = g; x < cv.width; x += g) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, cv.height); ctx.stroke(); }
      for (let y = g; y < cv.height; y += g) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cv.width, y); ctx.stroke(); }
    }
  }
  let pendF = null;
  function commitFog(throttled) {
    M.fog.revealed = [...revealed];
    if (throttled) { if (pendF) return; pendF = setTimeout(() => { pendF = null; socket.emit('map:fog', { campaignId: cid, fog: M.fog }); }, 150); }
    else socket.emit('map:fog', { campaignId: cid, fog: M.fog });
  }

  function commitTokens() { socket.emit('map:tokens', { campaignId: cid, tokens: M.tokens }); }
  function renderTokens() {
    if (!img) return;
    const iw = img.naturalWidth, ih = img.naturalHeight;
    layer.innerHTML = M.tokens.map((t) => {
      const left = (t.x / iw) * 100, top = (t.y / ih) * 100, w = (t.size / iw) * 100;
      const inner = t.image ? `<img src="${t.image}" alt="">` : `<span class="tok-init">${esc((t.label || '?').slice(0, 2))}</span>`;
      return `<div class="token shape-${t.shape || 'circle'} ${selId === t.id ? 'sel' : ''}" data-id="${t.id}"
        style="left:${left}%;top:${top}%;width:${w}%;--tc:${t.color || '#7d2230'}">
        ${inner}<span class="tok-label">${esc(t.label || '')}</span></div>`;
    }).join('');
    layer.querySelectorAll('.token').forEach((el) => wireToken(el));
  }
  function wireToken(el) {
    const id = el.dataset.id;
    let dragging = false;
    el.addEventListener('pointerdown', (e) => { e.preventDefault(); e.stopPropagation(); dragging = true; el.setPointerCapture(e.pointerId); select(id); });
    el.addEventListener('pointermove', (e) => {
      if (!dragging) return;
      const r = layer.getBoundingClientRect();
      const t = M.tokens.find((x) => x.id === id); if (!t) return;
      t.x = Math.max(0, Math.min(img.naturalWidth, (e.clientX - r.left) / r.width * img.naturalWidth));
      t.y = Math.max(0, Math.min(img.naturalHeight, (e.clientY - r.top) / r.height * img.naturalHeight));
      el.style.left = (t.x / img.naturalWidth) * 100 + '%';
      el.style.top = (t.y / img.naturalHeight) * 100 + '%';
    });
    el.addEventListener('pointerup', () => { if (dragging) { dragging = false; commitTokens(); } });
  }
  function select(id) {
    selId = id;
    const t = M.tokens.find((x) => x.id === id);
    const insp = document.getElementById('tok-inspector');
    document.getElementById('tok-hint').style.display = t ? 'none' : 'block';
    insp.style.display = t ? 'block' : 'none';
    layer.querySelectorAll('.token').forEach((el) => el.classList.toggle('sel', el.dataset.id === id));
    if (!t) return;
    document.getElementById('ti-label').value = t.label || '';
    document.getElementById('ti-shape').value = t.shape || 'circle';
    document.getElementById('ti-color').value = t.color || '#7d2230';
    document.getElementById('ti-size').value = t.size || 48;
    document.getElementById('ti-size-val').textContent = t.size || 48;
  }
  function selected() { return M.tokens.find((x) => x.id === selId); }
  function updSel(fn) { const t = selected(); if (!t) return; fn(t); renderTokens(); select(selId); commitTokens(); }
  function addToken(props) {
    const iw = img ? img.naturalWidth : 1000, ih = img ? img.naturalHeight : 700;
    const t = Object.assign({ id: uid(), x: iw / 2, y: ih / 2, size: 48, label: 'Token', color: '#7d2230', shape: 'circle', image: null }, props);
    M.tokens.push(t); renderTokens(); select(t.id); commitTokens();
  }

  document.getElementById('tok-add').onclick = () => { if (!img) return alert('Upload a map first.'); addToken({}); };
  document.getElementById('tok-party').onclick = () => {
    if (!img) return alert('Upload a map first.');
    (window.__PARTY__ || []).forEach((p, i) => addToken({ label: p.definition.name, image: p.definition.portrait || null, shape: 'circle', color: '#4d5b48', x: img.naturalWidth * (0.2 + i * 0.12), y: img.naturalHeight * 0.85 }));
  };
  document.getElementById('tok-combat').onclick = () => {
    if (!img) return alert('Upload a map first.');
    const enc = window.__ENCOUNTER__ || { combatants: [] };
    (enc.combatants || []).forEach((c, i) => addToken({ label: c.name, shape: 'square', color: c.kind === 'pc' ? '#4d5b48' : '#7d2230', x: img.naturalWidth * (0.2 + i * 0.1), y: img.naturalHeight * 0.5 }));
  };
  document.getElementById('ti-label').oninput = (e) => updSel((t) => t.label = e.target.value);
  document.getElementById('ti-shape').onchange = (e) => updSel((t) => t.shape = e.target.value);
  document.getElementById('ti-color').oninput = (e) => updSel((t) => t.color = e.target.value);
  document.getElementById('ti-size').oninput = (e) => { document.getElementById('ti-size-val').textContent = e.target.value; updSel((t) => t.size = +e.target.value); };
  document.getElementById('ti-clearimg').onclick = () => updSel((t) => t.image = null);
  document.getElementById('ti-del').onclick = () => { M.tokens = M.tokens.filter((x) => x.id !== selId); selId = null; renderTokens(); select(null); commitTokens(); };
  document.getElementById('ti-img').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f || !selId) return;
    const fd = new FormData(); fd.append('file', f);
    const r = await fetch('/api/campaign/' + cid + '/token/image', { method: 'POST', body: fd });
    const d = await r.json(); if (d.url) updSel((t) => t.image = d.url);
  });

  let painting = false;
  function cellAt(ev) {
    const r = cv.getBoundingClientRect();
    const px = (ev.clientX - r.left) * (cv.width / r.width), py = (ev.clientY - r.top) * (cv.height / r.height);
    const cell = M.fog.cell || 48; return { cx: Math.floor(px / cell), cy: Math.floor(py / cell) };
  }
  function paint(ev) {
    if (!img) return;
    const { cx, cy } = cellAt(ev), rad = parseInt(document.getElementById('brush').value, 10) - 1;
    for (let dy = -rad; dy <= rad; dy++) for (let dx = -rad; dx <= rad; dx++) {
      const x = cx + dx, y = cy + dy;
      if (x < 0 || y < 0 || x >= M.fog.cols || y >= M.fog.rows) continue;
      const idx = y * M.fog.cols + x;
      if (mode === 'reveal') revealed.add(idx); else revealed.delete(idx);
    }
    draw();
  }
  cv.addEventListener('pointerdown', (e) => { select(null); painting = true; cv.setPointerCapture(e.pointerId); paint(e); commitFog(true); });
  cv.addEventListener('pointermove', (e) => { if (painting) { paint(e); commitFog(true); } });
  cv.addEventListener('pointerup', () => { painting = false; commitFog(false); });

  function setMode(m) { mode = m; document.getElementById('mode-reveal').className = 'btn' + (m === 'reveal' ? '' : ' ghost'); document.getElementById('mode-hide').className = 'btn' + (m === 'hide' ? '' : ' ghost'); }
  document.getElementById('mode-reveal').onclick = () => setMode('reveal');
  document.getElementById('mode-hide').onclick = () => setMode('hide');
  document.getElementById('brush').oninput = (e) => document.getElementById('bs-val').textContent = e.target.value;
  document.getElementById('reveal-all').onclick = () => { revealed = new Set(); for (let i = 0; i < M.fog.cols * M.fog.rows; i++) revealed.add(i); draw(); commitFog(false); };
  document.getElementById('hide-all').onclick = () => { revealed = new Set(); draw(); commitFog(false); };
  const dmop = document.getElementById('dmop'); dmop.value = Math.round(dmOpacity * 100); document.getElementById('dmop-val').textContent = dmop.value + '%';
  dmop.oninput = (e) => { dmOpacity = e.target.value / 100; document.getElementById('dmop-val').textContent = e.target.value + '%'; localStorage.setItem('gmFogOpacity', dmOpacity); draw(); };
  const plop = document.getElementById('plop'); plop.value = Math.round((M.playerOpacity != null ? M.playerOpacity : 1) * 100); document.getElementById('plop-val').textContent = plop.value + '%';
  plop.oninput = (e) => { document.getElementById('plop-val').textContent = e.target.value + '%'; M.playerOpacity = e.target.value / 100; socket.emit('map:opacity', { campaignId: cid, playerOpacity: M.playerOpacity }); };
  const gridon = document.getElementById('gridon'); gridon.checked = !!(M.grid && M.grid.show);
  function commitGrid() { socket.emit('map:grid', { campaignId: cid, grid: M.grid }); draw(); }
  gridon.onchange = (e) => { M.grid = M.grid || { size: 70 }; M.grid.show = e.target.checked; commitGrid(); };
  const gs = document.getElementById('gridsize'); gs.value = (M.grid && M.grid.size) || 70; document.getElementById('gs-val').textContent = gs.value;
  gs.oninput = (e) => { document.getElementById('gs-val').textContent = e.target.value; M.grid = M.grid || {}; M.grid.size = +e.target.value; draw(); };
  gs.onchange = commitGrid;

  document.getElementById('mapimg').addEventListener('change', async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const fd = new FormData(); fd.append('file', f);
    const r = await fetch('/api/campaign/' + cid + '/map/image', { method: 'POST', body: fd });
    const d = await r.json(); if (!r.ok) return alert(d.error || 'Upload failed');
    M.image = d.image; M.fog = { cols: 0, rows: 0, cell: M.fog.cell || 48, revealed: [] }; revealed = new Set(); loadImage();
  });

  socket.on('map:fog', (m) => { M.fog = m.fog; revealed = new Set(m.fog.revealed || []); draw(); });
  socket.on('map:tokens', (m) => { M.tokens = m.tokens || []; renderTokens(); });
  socket.on('map:image', (m) => { M.image = m.image; M.fog = m.fog; revealed = new Set(); loadImage(); });

  setMode('reveal'); loadImage();
})();
