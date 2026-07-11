// Combat / initiative tracker. The whole encounter object is the unit of sync:
// any change writes window.enc and emits 'combat:update'; the server persists and
// broadcasts to the campaign room (DM tracker + player view stay in lockstep).

(function () {
  const cid = window.__CID__;
  const socket = io();
  const CAT = (window.__REF__ && window.__REF__.catalog) || [];
  let enc = window.__ENCOUNTER__ || { active: false, round: 1, turn: 0, combatants: [] };

  const uid = () => 'k' + Math.random().toString(36).slice(2, 8);
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const d20 = () => 1 + Math.floor(Math.random() * 20);

  socket.on('connect', () => socket.emit('join', { campaignId: cid }));
  socket.on('combat:update', (m) => { enc = m.encounter; render(); });

  function commit() { socket.emit('combat:update', { campaignId: cid, encounter: enc }); }
  function sorted() { return enc.combatants.slice().sort((a, b) => b.init - a.init); }

  function addCombatant(c) {
    enc.combatants.push(Object.assign({ id: uid(), init: 0, conditions: [], tint: '' }, c));
    commit(); render();
  }

  // ---- add menus ----
  function buildAdders() {
    document.getElementById('add-party').innerHTML = (window.__PARTY__ || []).map((p) =>
      `<button class="btn ghost addbtn" data-kind="pc" data-id="${p.id}">${esc(p.definition.name)}</button>`).join('') || '<span class="sec-empty">No party.</span>';
    document.getElementById('add-best').innerHTML = (window.__BESTIARY__ || []).map((b) =>
      `<button class="btn ghost addbtn" data-kind="monster" data-id="${b.id}">${esc(b.name)}</button>`).join('') || '<span class="sec-empty">Empty — build it in the Bestiary.</span>';
    document.getElementById('add-npc').innerHTML = (window.__NPCS__ || []).map((n) =>
      `<button class="btn ghost addbtn" data-kind="npc" data-id="${n.id}">${esc(n.name)}</button>`).join('') || '<span class="sec-empty">No NPCs.</span>';

    document.querySelectorAll('.addbtn').forEach((b) => b.addEventListener('click', () => {
      const kind = b.dataset.kind, id = b.dataset.id;
      if (kind === 'pc') {
        const p = window.__PARTY__.find((x) => x.id === id);
        addCombatant({ name: p.definition.name, kind: 'pc', refId: id, initMod: p.derived.initiative,
          ac: p.derived.armorClass.value, hpCurrent: p.state.currentHp, hpMax: p.derived.maxHp.value });
      } else if (kind === 'monster') {
        const m = window.__BESTIARY__.find((x) => x.id === id);
        const n = enc.combatants.filter((c) => c.refId === id).length + 1;
        addCombatant({ name: m.name + ' ' + n, kind: 'monster', refId: id, initMod: 0,
          ac: Number(m.ac) || 10, hpCurrent: Number(m.hp) || 1, hpMax: Number(m.hpMax || m.hp) || 1 });
      } else {
        const np = window.__NPCS__.find((x) => x.id === id);
        addCombatant({ name: np.name, kind: 'npc', refId: id, initMod: 0, ac: 10, hpCurrent: 10, hpMax: 10 });
      }
    }));
  }

  document.getElementById('m-add').addEventListener('click', () => {
    const name = document.getElementById('m-name').value.trim(); if (!name) return;
    addCombatant({ name, kind: 'monster', initMod: 0,
      ac: Number(document.getElementById('m-ac').value) || 10,
      hpCurrent: Number(document.getElementById('m-hp').value) || 1,
      hpMax: Number(document.getElementById('m-hp').value) || 1 });
    document.getElementById('m-name').value = ''; document.getElementById('m-ac').value = ''; document.getElementById('m-hp').value = '';
  });

  document.getElementById('btn-roll').addEventListener('click', () => {
    enc.combatants.forEach((c) => { c.init = d20() + (c.initMod || 0); });
    enc.active = true; enc.turn = 0; commit(); render();
  });
  document.getElementById('btn-next').addEventListener('click', () => {
    const n = enc.combatants.length; if (!n) return;
    enc.active = true; enc.turn = (enc.turn + 1) % n;
    if (enc.turn === 0) {
      enc.round = (enc.round || 1) + 1;
      // tick down timed conditions at the top of each new round
      enc.combatants.forEach((c) => {
        c.conditions = (c.conditions || []).filter((x) => {
          if (x.rounds == null) return true;
          x.rounds -= 1;
          return x.rounds > 0;
        });
      });
    }
    commit(); render();
  });
  document.getElementById('btn-clear').addEventListener('click', () => {
    if (!confirm('Clear the whole encounter?')) return;
    enc = { active: false, round: 1, turn: 0, combatants: [] }; commit(); render();
  });

  // ---- render ----
  function render() {
    document.getElementById('round-badge').textContent = 'Round ' + (enc.round || 1);
    const order = sorted();
    const track = document.getElementById('track');
    if (!order.length) { track.innerHTML = '<div class="sec-empty">No combatants yet. Add from the left.</div>'; return; }
    track.innerHTML = order.map((c, idx) => {
      const isTurn = enc.active && order[enc.turn] && order[enc.turn].id === c.id;
      const pct = c.hpMax ? Math.max(0, 100 * c.hpCurrent / c.hpMax) : 0;
      const conds = (c.conditions || []).map((x) => `<span class="cond ${x.kind}" title="${esc(x.base||'')}">${esc(x.name)}${x.level?(' '+x.level):''}${x.rounds?(' ('+x.rounds+'r)'):''}</span>`).join('');
      return `<div class="cmb ${isTurn ? 'turn' : ''} ${c.kind}" data-id="${c.id}">
        <div class="cmb-init">
          <input class="init-in" data-init="${c.id}" type="number" value="${c.init}" title="Edit initiative">
          <div class="init-nudge"><button data-up="${c.id}" title="Move up">▲</button><button data-down="${c.id}" title="Move down">▼</button></div>
        </div>
        <div class="cmb-main">
          <div class="cmb-name">${esc(c.name)} <span class="cmb-ac">AC ${c.ac}</span></div>
          <div class="hpbar ${pct < 35 ? 'low' : ''}"><i style="width:${pct}%"></i></div>
          <div class="cmb-hp"><button data-dmg="${c.id}">−</button>
            <span>${c.hpCurrent}/${c.hpMax}</span>
            <button data-heal="${c.id}">+</button>
            <button class="cmb-cond" data-cond="${c.id}">+ effect</button></div>
          <div class="cmb-conds">${conds}</div>
        </div>
        <button class="erm" data-rm="${c.id}">×</button>
      </div>`;
    }).join('');

    track.querySelectorAll('[data-dmg]').forEach((b) => b.addEventListener('click', () => hp(b.dataset.dmg, -1)));
    track.querySelectorAll('[data-heal]').forEach((b) => b.addEventListener('click', () => hp(b.dataset.heal, 1)));
    track.querySelectorAll('[data-rm]').forEach((b) => b.addEventListener('click', () => {
      enc.combatants = enc.combatants.filter((c) => c.id !== b.dataset.rm);
      if (enc.turn >= enc.combatants.length) enc.turn = 0;
      commit(); render();
    }));
    track.querySelectorAll('[data-cond]').forEach((b) => b.addEventListener('click', () => condMenu(b.dataset.cond, b)));

    // editable initiative
    track.querySelectorAll('[data-init]').forEach((inp) => inp.addEventListener('change', () => {
      const c = enc.combatants.find((x) => x.id === inp.dataset.init); if (!c) return;
      c.init = Number(inp.value) || 0; commit(); render();
    }));
    // reorder nudges: move a combatant just above/below its neighbour in the order
    const reorder = (id, dir) => {
      const ord = sorted();
      const i = ord.findIndex((x) => x.id === id);
      const j = i + dir;
      if (i < 0 || j < 0 || j >= ord.length) return;
      const me = enc.combatants.find((x) => x.id === id);
      const nb = ord[j];
      // place me on the neighbour's value, nudged so the sort puts me on the right side
      me.init = nb.init + (dir < 0 ? 1 : -1);
      // keep everyone distinct enough by also bumping the neighbour the other way if equal
      if (me.init === nb.init) nb.init -= dir < 0 ? 1 : -1;
      commit(); render();
    };
    track.querySelectorAll('[data-up]').forEach((b) => b.addEventListener('click', () => reorder(b.dataset.up, -1)));
    track.querySelectorAll('[data-down]').forEach((b) => b.addEventListener('click', () => reorder(b.dataset.down, 1)));
  }

  function hp(id, dir) {
    const c = enc.combatants.find((x) => x.id === id); if (!c) return;
    const amt = parseInt(prompt(dir < 0 ? 'Damage amount:' : 'Heal amount:', '1'), 10);
    if (isNaN(amt)) return;
    c.hpCurrent = Math.max(0, Math.min(c.hpMax, c.hpCurrent + dir * amt));
    commit(); render();
  }

  function condMenu(id, anchor) {
    const c = enc.combatants.find((x) => x.id === id); if (!c) return;
    const name = prompt('Add effect (type a name; matches the 2024 list if it can):', 'Poisoned');
    if (!name) return;
    const hit = CAT.find((x) => x.name.toLowerCase() === name.toLowerCase());
    c.conditions = c.conditions || [];
    const rounds = parseInt(prompt('Lasts how many rounds? (blank = until removed)', ''), 10);
    const cond = hit ? { name: hit.name, kind: hit.kind, base: hit.text } : { name, kind: 'debuff', base: '' };
    if (!isNaN(rounds) && rounds > 0) cond.rounds = rounds;
    c.conditions.push(cond);
    commit(); render();
  }

  // ---- saved encounters (pre-made lineups, persisted per campaign) ----
  let presets = window.__PRESETS__ || [];

  function templateOf(c) {
    // Store the recipe, not the moment: full HP, no initiative, no conditions.
    return { name: c.name, kind: c.kind, refId: c.refId || null,
      initMod: c.initMod || 0, ac: c.ac, hpMax: c.hpMax };
  }
  function instantiate(t) {
    if (t.kind === 'pc' && t.refId) {
      // PCs load with their *live* sheet stats, not the snapshot.
      const p = (window.__PARTY__ || []).find((x) => x.id === t.refId);
      if (p) return { id: uid(), name: p.definition.name, kind: 'pc', refId: t.refId,
        initMod: p.derived.initiative, ac: p.derived.armorClass.value,
        hpCurrent: p.state.currentHp, hpMax: p.derived.maxHp.value,
        init: 0, conditions: [], tint: '' };
    }
    return { id: uid(), name: t.name, kind: t.kind || 'monster', refId: t.refId || null,
      initMod: t.initMod || 0, ac: t.ac || 10, hpCurrent: t.hpMax || 1, hpMax: t.hpMax || 1,
      init: 0, conditions: [], tint: '' };
  }

  function renderPresets() {
    const el = document.getElementById('preset-list');
    if (!el) return;
    el.innerHTML = presets.length ? presets.map((p) => `
      <div class="tool-row"><span class="grow"><b>${esc(p.name)}</b>
        <span style="color:var(--ink-soft);font-size:12px">${(p.combatants || []).length} combatant${(p.combatants || []).length === 1 ? '' : 's'} — ${esc((p.combatants || []).map((c) => c.name).join(', '))}</span></span>
        <button class="btn ghost" data-pload="${p.id}" title="Replace current encounter">Load</button>
        <button class="btn ghost" data-padd="${p.id}" title="Add to current encounter">＋</button>
        <button class="erm" data-pdel="${p.id}">×</button></div>`).join('')
      : '<span class="sec-empty">None yet. Build a lineup, name it, save it.</span>';
    el.querySelectorAll('[data-pload]').forEach((b) => b.addEventListener('click', () => loadPreset(b.dataset.pload, true)));
    el.querySelectorAll('[data-padd]').forEach((b) => b.addEventListener('click', () => loadPreset(b.dataset.padd, false)));
    el.querySelectorAll('[data-pdel]').forEach((b) => b.addEventListener('click', async () => {
      const p = presets.find((x) => x.id === b.dataset.pdel);
      if (!confirm('Delete saved encounter "' + (p ? p.name : '') + '"?')) return;
      await fetch('/api/campaign/' + cid + '/encounters/' + b.dataset.pdel, { method: 'DELETE' });
      presets = presets.filter((x) => x.id !== b.dataset.pdel);
      renderPresets();
    }));
  }

  function loadPreset(id, replace) {
    const p = presets.find((x) => x.id === id); if (!p) return;
    if (replace && enc.combatants.length && !confirm('Replace the current encounter with "' + p.name + '"?')) return;
    const fresh = (p.combatants || []).map(instantiate);
    if (replace) enc = { active: false, round: 1, turn: 0, combatants: fresh };
    else enc.combatants = enc.combatants.concat(fresh);
    commit(); render();
  }

  document.getElementById('preset-save').addEventListener('click', async () => {
    const name = document.getElementById('preset-name').value.trim();
    if (!name) { alert('Name the encounter first.'); return; }
    if (!enc.combatants.length) { alert('Nothing to save — add combatants first.'); return; }
    const body = { name, combatants: enc.combatants.map(templateOf) };
    const r = await fetch('/api/campaign/' + cid + '/encounters', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    const d = await r.json();
    presets.push(d.item);
    document.getElementById('preset-name').value = '';
    renderPresets();
  });

  buildAdders();
  renderPresets();
  render();
})();
