// Inline editing for the structural sections of the sheet.
// Each section renders a READ view and (on "Edit") an EDIT view. Saving a change
// patches the whole array for that section; the server re-derives and broadcasts.
// While a section is in edit mode it ignores inbound re-renders so it never
// clobbers a form you're typing in.

(function () {
  const socket = window.gmSocket;
  const patch = window.gmPatch;
  if (!socket) return;
  let char = window.__CHAR__;

  const ABIL = ['Strength', 'Dexterity', 'Constitution', 'Intelligence', 'Wisdom', 'Charisma'];
  const uid = () => 'x' + Math.random().toString(36).slice(2, 9);
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const escAttr = (s) => esc(s).replace(/"/g, '&quot;');
  const stripTags = (h) => { const d = document.createElement('div'); d.innerHTML = h || ''; return d.textContent || ''; };
  const textToHtml = (t) => (t || '').split(/\n{2,}/).map((p) => '<p>' + esc(p).replace(/\n/g, '<br>') + '</p>').join('');

  const editing = {}; // section -> bool

  // ---------- section definitions ----------
  const SECTIONS = {
    attacks: {
      get: () => char.definition.attacks || [],
      set: (arr) => patch('definition.attacks', arr),
      blank: () => ({ id: uid(), name: 'New Attack', ability: 'Strength', proficient: true, damage: '1d6', damageType: '', range: '', magicalModifier: 0 }),
      readEmpty: 'No attacks.',
      renderRead() {
        const der = char.derived.attacks || [];
        if (!der.length) return `<div class="sec-empty">No attacks.</div>`;
        return `<table class="atk"><thead><tr><th>Name</th><th>To hit</th><th>Damage</th><th>Range</th></tr></thead><tbody>` +
          der.map((a) => `<tr><td>${esc(a.name)}</td><td class="numeral">${esc(a.toHit)}</td>
            <td class="numeral">${esc(a.damage)} ${esc(a.damageType)}</td><td>${esc(a.range)}</td></tr>`).join('') +
          `</tbody></table>`;
      },
      renderEditRow(a, i) {
        return `<div class="erow" data-i="${i}">
          <div class="efields">
            <input data-f="name" value="${escAttr(a.name)}" placeholder="Name" style="flex:2">
            <select data-f="ability">${ABIL.map((x) => `<option ${a.ability === x ? 'selected' : ''}>${x}</option>`).join('')}</select>
            <input data-f="damage" value="${escAttr(a.damage)}" placeholder="1d8" style="width:70px">
            <input data-f="damageType" value="${escAttr(a.damageType)}" placeholder="type" style="width:90px">
            <input data-f="range" value="${escAttr(a.range)}" placeholder="range" style="width:90px">
            <input data-f="magicalModifier" type="number" value="${a.magicalModifier || 0}" title="magic +" style="width:56px">
            <label class="ecbx"><input data-f="proficient" type="checkbox" ${a.proficient ? 'checked' : ''}> prof</label>
          </div>
          <button class="erm" data-rm="${i}" title="Remove">×</button>
        </div>`;
      },
      readField(row) {
        return {
          name: row.querySelector('[data-f=name]').value,
          ability: row.querySelector('[data-f=ability]').value,
          damage: row.querySelector('[data-f=damage]').value,
          damageType: row.querySelector('[data-f=damageType]').value,
          range: row.querySelector('[data-f=range]').value,
          magicalModifier: Number(row.querySelector('[data-f=magicalModifier]').value) || 0,
          proficient: row.querySelector('[data-f=proficient]').checked,
        };
      },
      merge: (orig, f) => ({ ...orig, ...f }),
    },

    inventory: {
      get: () => char.definition.inventory.items || [],
      set: (arr) => patch('definition.inventory.items', arr),
      blank: () => ({ id: uid(), name: 'New Item', quantity: 1, equipped: false, type: '', subType: '' }),
      renderRead() {
        const items = char.definition.inventory.items || [];
        if (!items.length) return `<div class="sec-empty">Empty.</div>`;
        return `<div class="cols-2">` + items.map((it) =>
          `<div class="kv"><span class="k">${esc(it.name)}${it.equipped ? ' <span style="color:var(--sage)">▣</span>' : ''}</span>
            <span class="numeral">×${it.quantity || 1}</span></div>`).join('') + `</div>`;
      },
      renderEditRow(it, i) {
        return `<div class="erow" data-i="${i}">
          <div class="efields">
            <input data-f="name" value="${escAttr(it.name)}" placeholder="Item name" style="flex:2">
            <input data-f="quantity" type="number" value="${it.quantity || 1}" title="qty" style="width:60px">
            <input data-f="subType" value="${escAttr(it.subType)}" placeholder="e.g. Studded Leather Armor" style="flex:1" title="armor subtype enables AC auto-calc">
            <label class="ecbx"><input data-f="equipped" type="checkbox" ${it.equipped ? 'checked' : ''}> equipped</label>
          </div>
          <button class="erm" data-rm="${i}" title="Remove">×</button>
        </div>`;
      },
      readField(row) {
        return {
          name: row.querySelector('[data-f=name]').value,
          quantity: Number(row.querySelector('[data-f=quantity]').value) || 1,
          subType: row.querySelector('[data-f=subType]').value,
          equipped: row.querySelector('[data-f=equipped]').checked,
        };
      },
      merge: (orig, f) => ({ ...orig, ...f }),
    },

    features: {
      get: () => char.definition.features || [],
      set: (arr) => patch('definition.features', arr),
      blank: () => ({ id: uid(), name: 'New Feature', html: '' }),
      renderRead() {
        const fs = char.definition.features || [];
        if (!fs.length) return `<div class="sec-empty">No features.</div>`;
        return fs.map((f) => `<details class="feat"><summary>${esc(f.name)}</summary>
          <div class="body">${f.html || ''}</div></details>`).join('');
      },
      renderEditRow(f, i) {
        return `<div class="erow col" data-i="${i}">
          <div class="efields"><input data-f="name" value="${escAttr(f.name)}" placeholder="Feature name" style="flex:1">
            <button class="erm" data-rm="${i}" title="Remove">×</button></div>
          <textarea data-f="html" placeholder="Description" rows="3">${esc(stripTags(f.html))}</textarea>
        </div>`;
      },
      readField(row) {
        return { name: row.querySelector('[data-f=name]').value, html: textToHtml(row.querySelector('[data-f=html]').value) };
      },
      merge: (orig, f) => ({ ...orig, ...f }),
    },

    spells: {
      get: () => char.definition.spellcasting.spells || [],
      set: (arr) => patch('definition.spellcasting.spells', arr),
      blank: () => ({ id: uid(), name: 'New Spell', level: 1, prepared: false, html: '' }),
      renderRead() {
        const sp = (char.definition.spellcasting.spells || []).slice().sort((a, b) => (a.level - b.level) || a.name.localeCompare(b.name));
        if (!sp.length) return `<div class="sec-empty">No spells.</div>`;
        return sp.map((s) => `<details class="feat"><summary>${esc(s.name)}
          <span style="color:var(--ink-soft);font-size:12px">${s.level ? 'Lvl ' + s.level : 'Cantrip'}${s.prepared ? ' · prepared' : ''}</span></summary>
          <div class="body">${s.html || ''}</div></details>`).join('');
      },
      renderEditRow(s, i) {
        return `<div class="erow col" data-i="${i}">
          <div class="efields">
            <input data-f="name" value="${escAttr(s.name)}" placeholder="Spell name" style="flex:2">
            <input data-f="level" type="number" min="0" max="9" value="${s.level || 0}" title="level (0=cantrip)" style="width:60px">
            <label class="ecbx"><input data-f="prepared" type="checkbox" ${s.prepared ? 'checked' : ''}> prepared</label>
            <button class="erm" data-rm="${i}" title="Remove">×</button>
          </div>
          <textarea data-f="html" placeholder="Description" rows="2">${esc(stripTags(s.html))}</textarea>
        </div>`;
      },
      readField(row) {
        return {
          name: row.querySelector('[data-f=name]').value,
          level: Number(row.querySelector('[data-f=level]').value) || 0,
          prepared: row.querySelector('[data-f=prepared]').checked,
          html: textToHtml(row.querySelector('[data-f=html]').value),
        };
      },
      merge: (orig, f) => ({ ...orig, ...f }),
    },
  };

  // ---------- resources (defs + pips) ----------
  function renderResources() {
    const box = document.getElementById('sec-resources');
    if (!box) return;
    const defs = char.definition.resources || [];
    const exp = char.state.resourcesExpended || {};
    if (editing.resources) {
      box.innerHTML = defs.map((r, i) => `
        <div class="erow" data-i="${i}">
          <div class="efields">
            <input data-f="name" value="${escAttr(r.name)}" placeholder="Resource" style="flex:2">
            <input data-f="max" type="number" min="1" value="${r.max || 1}" title="max uses" style="width:60px">
            <label class="ecbx"><input data-f="short" type="checkbox" ${/(short)/i.test((r.restoreOn || []).join(',')) ? 'checked' : ''}> short</label>
            <label class="ecbx"><input data-f="long" type="checkbox" ${/(long)/i.test((r.restoreOn || []).join(',')) ? 'checked' : ''}> long</label>
          </div>
          <button class="erm" data-rm="${i}" title="Remove">×</button>
        </div>`).join('') +
        `<button class="sec-add" data-add="resources">+ Add resource</button>`;
      wireResEdit(box);
    } else {
      if (!defs.length) { box.innerHTML = `<div class="sec-empty">No resources.</div>`; return; }
      box.innerHTML = defs.map((r) => {
        const used = exp[r.id] || 0;
        let pips = '';
        for (let i = 0; i < r.max; i++) pips += `<button class="pip ${i >= used ? 'filled' : ''}" data-i="${i}"></button>`;
        return `<div class="slot-row"><span class="lvl" style="width:auto;min-width:120px">${esc(r.name)}</span>
          <div class="pips" data-resource="${r.id}" data-max="${r.max}">${pips}</div></div>`;
      }).join('');
      box.querySelectorAll('[data-resource]').forEach((pbox) => {
        const id = pbox.dataset.resource, max = Number(pbox.dataset.max);
        pbox.querySelectorAll('.pip').forEach((pip) => pip.addEventListener('click', () => {
          const i = Number(pip.dataset.i);
          const used = exp[id] || 0;
          const next = (i >= used) ? max - i : max - (i + 1);
          patch('state.resourcesExpended.' + id, Math.max(0, Math.min(max, next)));
        }));
      });
    }
  }
  function wireResEdit(box) {
    const commit = () => {
      const defs = [...box.querySelectorAll('.erow')].map((row) => {
        const i = Number(row.dataset.i);
        const orig = char.definition.resources[i] || { id: uid() };
        const restore = [];
        if (row.querySelector('[data-f=short]').checked) restore.push('Short Rest');
        if (row.querySelector('[data-f=long]').checked) restore.push('Long Rest');
        return { id: orig.id || uid(), name: row.querySelector('[data-f=name]').value, max: Number(row.querySelector('[data-f=max]').value) || 1, restoreOn: restore };
      });
      char.definition.resources = defs;
      // reconcile expended map: keep ids, clamp, drop removed
      const exp = {};
      defs.forEach((d) => { const cur = (char.state.resourcesExpended || {})[d.id] || 0; exp[d.id] = Math.min(cur, d.max); });
      char.state.resourcesExpended = exp;
      patch('definition.resources', defs);
      patch('state.resourcesExpended', exp);
    };
    box.querySelectorAll('input').forEach((el) => el.addEventListener('change', commit));
    box.querySelectorAll('[data-rm]').forEach((b) => b.addEventListener('click', () => {
      char.definition.resources.splice(Number(b.dataset.rm), 1); commit(); renderResources();
    }));
    const add = box.querySelector('[data-add=resources]');
    if (add) add.addEventListener('click', () => {
      char.definition.resources = (char.definition.resources || []).concat({ id: uid(), name: 'New Resource', max: 1, restoreOn: ['Long Rest'] });
      commit(); renderResources();
    });
  }

  // ---------- spell slots (maxes + pips) ----------
  function renderSlots() {
    const box = document.getElementById('sec-slots');
    if (!box) return;
    const sm = char.definition.spellcasting.slotsMax || {};
    const cur = char.state.slotsCurrent || {};
    if (editing.slots) {
      let rows = '';
      for (let l = 1; l <= 9; l++) rows += `<div class="erow"><div class="efields"><span class="lvl">Level ${l}</span>
        <input data-lvl="${l}" type="number" min="0" max="9" value="${sm[l] || 0}" style="width:64px"> slots</div></div>`;
      box.innerHTML = `<div class="efields" style="margin-bottom:8px"><label>Casting ability</label>
        <select id="sc-ability">${['', 'Intelligence', 'Wisdom', 'Charisma'].map((a) => `<option ${char.definition.spellcasting.ability === a ? 'selected' : ''}>${a || '—'}</option>`).join('')}</select></div>` + rows;
      box.querySelector('#sc-ability').addEventListener('change', (e) =>
        patch('definition.spellcasting.ability', e.target.value === '—' ? null : e.target.value));
      box.querySelectorAll('[data-lvl]').forEach((el) => el.addEventListener('change', () => {
        const newMax = {};
        box.querySelectorAll('[data-lvl]').forEach((x) => { newMax[x.dataset.lvl] = Number(x.value) || 0; });
        const nc = {};
        Object.keys(newMax).forEach((l) => { nc[l] = Math.min(cur[l] != null ? cur[l] : newMax[l], newMax[l]); });
        char.definition.spellcasting.slotsMax = newMax; char.state.slotsCurrent = nc;
        patch('definition.spellcasting.slotsMax', newMax);
        patch('state.slotsCurrent', nc);
      }));
    } else {
      const rows = [];
      for (let l = 1; l <= 9; l++) {
        const mx = sm[l] || 0; if (!mx) continue;
        let pips = '';
        for (let i = 0; i < mx; i++) pips += `<button class="pip ${i < (cur[l] || 0) ? 'filled' : ''}" data-i="${i}"></button>`;
        rows.push(`<div class="slot-row"><span class="lvl">Level ${l}</span><div class="pips" data-slots="${l}" data-max="${mx}">${pips}</div></div>`);
      }
      box.innerHTML = rows.length ? rows.join('') : `<div class="sec-empty">No spell slots.</div>`;
      box.querySelectorAll('[data-slots]').forEach((pbox) => {
        const l = pbox.dataset.slots;
        pbox.querySelectorAll('.pip').forEach((pip) => pip.addEventListener('click', () => {
          const i = Number(pip.dataset.i);
          const c = cur[l] || 0;
          const next = (i + 1 === c) ? i : i + 1;
          patch('state.slotsCurrent.' + l, next);
        }));
      });
    }
  }

  // ---------- generic list section render ----------
  function renderSection(key) {
    const sec = SECTIONS[key];
    const box = document.getElementById('sec-' + key);
    if (!box || !sec) return;
    if (!editing[key]) { box.innerHTML = sec.renderRead(); return; }
    const arr = sec.get();
    box.innerHTML = arr.map((it, i) => sec.renderEditRow(it, i)).join('') +
      `<button class="sec-add" data-add="${key}">+ Add</button>`;
    const commit = () => {
      const rows = [...box.querySelectorAll('.erow')];
      const next = rows.map((row) => {
        const i = Number(row.dataset.i);
        const orig = sec.get()[i] || sec.blank();
        return sec.merge(orig, sec.readField(row));
      });
      sec.set(next);
      // keep local copy in sync so re-open shows latest
      assignBack(key, next);
    };
    box.querySelectorAll('input,select,textarea').forEach((el) => el.addEventListener('change', commit));
    box.querySelectorAll('[data-rm]').forEach((b) => b.addEventListener('click', () => {
      const next = sec.get().slice(); next.splice(Number(b.dataset.rm), 1);
      assignBack(key, next); sec.set(next); renderSection(key);
    }));
    box.querySelector('[data-add]').addEventListener('click', () => {
      const next = sec.get().concat(sec.blank());
      assignBack(key, next); sec.set(next); renderSection(key);
    });
  }
  function assignBack(key, arr) {
    if (key === 'inventory') char.definition.inventory.items = arr;
    else if (key === 'spells') char.definition.spellcasting.spells = arr;
    else char.definition[key] = arr;
  }

  // ---------- edit toggles ----------
  document.querySelectorAll('.sec-edit').forEach((btn) => {
    const key = btn.dataset.edit;
    btn.addEventListener('click', () => {
      editing[key] = !editing[key];
      btn.textContent = editing[key] ? 'Done' : 'Edit';
      btn.classList.toggle('on', editing[key]);
      rerender(key);
    });
  });

  function rerender(key) {
    if (key === 'resources') renderResources();
    else if (key === 'slots') renderSlots();
    else renderSection(key);
  }

  // ---------- inbound updates: refresh sections not being edited ----------
  socket.on('character:update', (fresh) => {
    char = fresh;
    ['attacks', 'inventory', 'features', 'spells'].forEach((k) => { if (!editing[k]) renderSection(k); });
    if (!editing.resources) renderResources();
    if (!editing.slots) renderSlots();
  });

  // initial render
  ['attacks', 'inventory', 'features', 'spells'].forEach(renderSection);
  renderResources();
  renderSlots();
})();
