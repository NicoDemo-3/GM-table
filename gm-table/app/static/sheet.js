// Live-sync glue for the character sheet.
// Source of truth is the server; we send field patches and re-render from the
// authoritative character it broadcasts back.

const charId = document.body.dataset.charId;
const socket = io();
let char = window.__CHAR__;

const dot = document.getElementById('conn-dot');
const connText = document.getElementById('conn-text');

socket.on('connect', () => {
  socket.emit('join', { characterId: charId });
  dot.classList.add('live');
  connText.textContent = 'live';
});
socket.on('disconnect', () => {
  dot.classList.remove('live');
  connText.textContent = 'reconnecting…';
});

function patch(path, value) {
  socket.emit('patch', { characterId: charId, path, value });
}
// shared hooks for editing.js
window.gmSocket = socket;
window.gmCharId = charId;
window.gmPatch = patch;

// ---- read a dotted path out of the char doc ----
function dig(obj, path) {
  return path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj);
}
const sign = (n) => (n >= 0 ? '+' + n : '' + n);

// ============ OUTBOUND: local edits -> patches ============

// number inputs bound to a state path, or to an override (path|kind)
document.querySelectorAll('input[data-bind]').forEach((el) => {
  el.addEventListener('change', () => {
    const [path, kind] = el.dataset.bind.split('|');
    let value = el.value === '' ? null : Number(el.value);
    if (kind === 'ac' || kind === 'max') {
      // override tile: if the typed value equals the computed value, clear the
      // override (back to "computed"); otherwise store it as an override.
      const tile = el.closest('[data-computed]');
      const computed = Number(tile.dataset.computed);
      value = (value === computed || value == null) ? null : value;
    }
    patch(path, value);
  });
});

// inspiration / boolean chips
document.querySelectorAll('[data-toggle]').forEach((el) => {
  el.addEventListener('click', () => {
    const on = !el.hasAttribute('data-on');
    patch(el.dataset.toggle, on);
  });
});

// (spell-slot & resource pips are owned by editing.js)

// ============ INBOUND: authoritative update -> re-render ============

socket.on('character:update', (fresh) => {
  char = fresh;

  // derived numbers
  document.querySelectorAll('[data-derived]').forEach((el) => {
    let v = dig(fresh.derived, el.dataset.derived);
    if (v == null) v = '—';
    else if (el.hasAttribute('data-sign') && typeof v === 'number') v = sign(v);
    flashIfChanged(el, String(v));
  });

  // bound inputs (HP, temp, overrides)
  document.querySelectorAll('input[data-bind]').forEach((el) => {
    if (document.activeElement === el) return; // don't fight the typer
    const [path, kind] = el.dataset.bind.split('|');
    let v;
    if (kind === 'ac') v = fresh.derived.armorClass.value;
    else if (kind === 'max') v = fresh.derived.maxHp.value;
    else v = dig(fresh, path);
    if (String(v) !== el.value) { el.value = v; flashEl(el.closest('.tile') || el); }
  });

  // override "set" flags
  syncOvr('definition.acOverride', fresh.derived.armorClass.overridden);
  syncOvr('definition.maxHpOverride', fresh.derived.maxHp.overridden);

  // inspiration chip
  document.querySelectorAll('[data-toggle]').forEach((el) => {
    const on = dig(fresh, el.dataset.toggle);
    el.classList.toggle('on', !!on);
    on ? el.setAttribute('data-on', '') : el.removeAttribute('data-on');
  });

  // (spell slots & resources are re-rendered by editing.js)
});

function syncOvr(path, overridden) {
  const tile = document.querySelector(`[data-edit-tile="${path}"]`);
  if (!tile) return;
  const flag = tile.querySelector('[data-ovr-flag]');
  if (flag) flag.hidden = !overridden;
}

function flashIfChanged(el, text) {
  if (el.textContent !== text) { el.textContent = text; flashEl(el); }
}
function flashEl(el) {
  el.classList.remove('flash'); void el.offsetWidth; el.classList.add('flash');
}

// ============ CONDITIONS / BUFFS / DEBUFFS ============
(function () {
  const CATALOG = (window.__REF__ && window.__REF__.catalog) || [];
  const listEl = document.getElementById('cond-list');
  const menuEl = document.getElementById('cond-menu');
  const detailEl = document.getElementById('cond-detail');
  const addBtn = document.getElementById('add-cond-btn');
  if (!listEl) return;

  let conds = (char.state.conditions || []).slice();
  const uid = () => 'c' + Math.random().toString(36).slice(2, 9);

  function commit() { patch('state.conditions', conds); }

  function render() {
    listEl.innerHTML = '';
    if (!conds.length) {
      const e = document.createElement('span');
      e.className = 'cond empty';
      e.textContent = 'No active effects';
      listEl.appendChild(e);
      return;
    }
    conds.forEach((c) => {
      const chip = document.createElement('span');
      chip.className = 'cond ' + c.kind;
      let label = c.name;
      chip.innerHTML = `<span>${label}</span>`;
      if (c.level != null) chip.innerHTML += `<span class="lvl-badge">${c.level}</span>`;
      chip.innerHTML += `<span class="rm" title="Remove">×</span>`;
      chip.querySelector('.rm').addEventListener('click', (ev) => {
        ev.stopPropagation();
        conds = conds.filter((x) => x.id !== c.id); commit(); render(); detailEl.style.display = 'none';
      });
      chip.addEventListener('click', () => openDetail(c));
      listEl.appendChild(chip);
    });
  }

  function openDetail(c) {
    detailEl.style.display = 'block';
    let html = `<div class="cd-title ${c.kind}" style="color:var(--${c.kind === 'buff' ? 'sage' : 'garnet'})">${c.name}</div>`;
    html += `<div class="cd-base">${c.base || 'Custom effect.'}</div>`;
    if (c.level != null) {
      html += `<div class="lvl-row"><label>Level</label>
        <input type="number" min="1" max="6" value="${c.level}" id="cd-level" style="width:64px">
        <span style="font-size:12px;color:var(--ink-soft)">(−${c.level * 2} to d20 rolls, −${c.level * 5} ft speed)</span></div>`;
    }
    html += `<label style="font-size:12px;color:var(--ink-soft)">Your notes (duration, source, reminders — never changes the rules text above)</label>
      <textarea id="cd-note" placeholder="e.g. until end of my next turn, from the goblin shaman">${c.note || ''}</textarea>`;
    detailEl.innerHTML = html;
    const note = detailEl.querySelector('#cd-note');
    note.addEventListener('change', () => { c.note = note.value; commit(); });
    const lvl = detailEl.querySelector('#cd-level');
    if (lvl) lvl.addEventListener('change', () => {
      c.level = Math.max(1, Math.min(6, Number(lvl.value) || 1)); commit(); render(); openDetail(c);
    });
  }

  // ---- add menu ----
  function buildMenu() {
    const debuffs = CATALOG.filter((c) => c.kind === 'debuff');
    const buffs = CATALOG.filter((c) => c.kind === 'buff');
    let html = '';
    const sect = (title, arr) => {
      let h = `<div class="grp">${title}</div>`;
      arr.forEach((c) => {
        h += `<div class="opt" data-key="${c.key}">
          <div class="o-name ${c.kind}">${c.name}${c.levels ? ' (levels)' : ''}</div>
          <div class="o-desc">${c.text}</div></div>`;
      });
      return h;
    };
    html += sect('Debuffs — 2024 conditions & spells', debuffs);
    html += sect('Buffs', buffs);
    html += `<div class="grp">Custom</div>
      <div style="padding:6px 8px">
        <input id="custom-name" placeholder="Effect name">
        <select id="custom-kind"><option value="debuff">Debuff (hinders)</option><option value="buff">Buff (helps)</option></select>
        <textarea id="custom-desc" placeholder="What does it do? (optional)"></textarea>
        <button class="btn" id="custom-add" style="width:100%">Add custom effect</button>
      </div>`;
    menuEl.innerHTML = html;

    menuEl.querySelectorAll('.opt').forEach((opt) => {
      opt.addEventListener('click', () => {
        const cat = CATALOG.find((c) => c.key === opt.dataset.key);
        const inst = { id: uid(), key: cat.key, name: cat.name, kind: cat.kind, base: cat.text, note: '' };
        if (cat.levels) inst.level = 1;
        conds.push(inst); commit(); render(); closeMenu(); openDetail(inst);
      });
    });
    menuEl.querySelector('#custom-add').addEventListener('click', () => {
      const name = menuEl.querySelector('#custom-name').value.trim();
      if (!name) return;
      const inst = {
        id: uid(), key: 'custom', name,
        kind: menuEl.querySelector('#custom-kind').value,
        base: menuEl.querySelector('#custom-desc').value.trim(), note: '',
      };
      conds.push(inst); commit(); render(); closeMenu(); openDetail(inst);
    });
  }
  function openMenu() { buildMenu(); menuEl.classList.add('show'); }
  function closeMenu() { menuEl.classList.remove('show'); }
  addBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    menuEl.classList.contains('show') ? closeMenu() : openMenu();
  });
  document.addEventListener('click', (e) => {
    if (!menuEl.contains(e.target) && e.target !== addBtn) closeMenu();
  });

  // keep in sync with server broadcasts
  socket.on('character:update', (fresh) => {
    conds = (fresh.state.conditions || []).slice();
    render();
  });

  render();
})();

// ---- rest buttons (fired from the left rail) ----
document.addEventListener('gm-rest', (e) => {
  socket.emit('rest', { characterId: charId, kind: e.detail.kind });
});

// ============ QUICK ACTIONS: damage/heal, death saves, hit dice ============
(function () {
  let c = window.__CHAR__;
  const amt = () => Math.max(0, parseInt(document.getElementById('qa-amt').value, 10) || 0);
  document.getElementById('qa-damage').addEventListener('click', () => {
    if (amt()) socket.emit('hp:apply', { characterId: charId, delta: -amt() });
  });
  document.getElementById('qa-heal').addEventListener('click', () => {
    if (amt()) socket.emit('hp:apply', { characterId: charId, delta: amt() });
  });
  document.querySelectorAll('[data-ds]').forEach((el) => {
    el.addEventListener('click', () => {
      socket.emit('deathsave', { characterId: charId, result: el.dataset.ds });
    });
  });
  document.getElementById('ds-reset').addEventListener('click', () =>
    socket.emit('deathsave', { characterId: charId, result: 'reset' }));

  function renderQA(fresh) {
    c = fresh;
    const ds = c.state.deathSaves || { success: 0, failure: 0};
    document.querySelectorAll('[data-ds]').forEach((el) => {
      const k = el.dataset.ds, n = ds[k] || 0;
      el.innerHTML = [0, 1, 2].map((i) =>
        `<span class="ds-pip ${k} ${i < n ? 'on' : ''}">${k === 'success' ? '✓' : '✗'}</span>`).join('');
    });
    // hide death saves unless at 0 HP or some marked
    document.getElementById('qa-death').style.display =
      (c.state.currentHp === 0 || ds.success || ds.failure) ? 'flex' : 'none';
    // hit dice buttons
    const hd = c.state.hitDiceCurrent || {};
    const max = c.definition.hitDiceMax || {};
    document.getElementById('hd-btns').innerHTML = Object.keys(max).map((die) =>
      `<button class="btn ghost hd-btn" data-die="${die}" ${(hd[die] || 0) <= 0 ? 'disabled' : ''}>${die} (${hd[die] || 0}/${max[die]})</button>`).join('') || '<span class="sec-empty">—</span>';
    document.querySelectorAll('.hd-btn').forEach((b) => b.addEventListener('click', () =>
      socket.emit('spendhd', { characterId: charId, die: b.dataset.die })));
  }
  socket.on('hd:healed', (m) => { const a = document.getElementById('qa-amt'); if (a) { a.value = ''; } });
  socket.on('character:update', renderQA);
  renderQA(c);
})();
