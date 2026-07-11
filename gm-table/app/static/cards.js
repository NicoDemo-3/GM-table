// Renders entities as cards using a saved Sheet Builder layout, resolving live
// values per entity type. One resolver handles characters, combatants, NPCs, and
// bestiary stat blocks, so every built card surface shows real data.
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  function path(o, p) { return p.split('.').reduce((a, k) => (a == null ? undefined : a[k]), o); }
  function fmt(v) {
    if (v == null || v === '') return '—';
    if (typeof v === 'boolean') return v ? '✓' : '—';
    if (typeof v === 'object') { if ('used' in v && 'max' in v) return (v.max - v.used) + '/' + v.max; return esc(JSON.stringify(v)); }
    return esc(v);
  }
  function nameOf(e, type) { return (type === 'sheet' || type === 'party') ? e.definition.name : (e.name || '—'); }
  function portraitOf(e, type) { return (type === 'sheet' || type === 'party') ? e.definition.portrait : (e.image || null); }

  function resolve(e, type, item) {
    if (type === 'sheet' || type === 'party') {
      if (item.describes) { const v = path(e, item.describes); if (v !== undefined) return fmt(v); }
      const c = e.definition.custom || {}; return fmt(item.wid in c ? c[item.wid] : '');
    }
    const k = item.key;
    const maps = {
      combat: { name: e.name, ac: e.ac, currentHp: e.hpCurrent, maxHp: e.hpMax, tempHp: e.tempHp,
        initiative: e.init, conditions: (e.conditions || []).map((c) => c.name).join(', ') },
      npc: { name: e.name, role: e.role, description: e.description, tags: (e.tags || []).join(', ') },
      bestiary: { name: e.name, ac: e.ac, maxHp: (e.hpMax != null ? e.hpMax : e.hp), currentHp: e.hp,
        level: e.cr, cr: e.cr, speed: e.speed },
    };
    const m = maps[type] || {};
    if (k in m && m[k] != null && m[k] !== '') return fmt(m[k]);
    if (e[k] != null && e[k] !== '') return fmt(e[k]);   // generic fallback
    return '—';
  }

  window.renderCards = function (containerId, entities, type, layout, fallbackLabel) {
    const box = document.getElementById(containerId);
    if (!entities.length) { box.innerHTML = '<p class="empty">Nothing to show for this card.</p>'; return; }
    box.innerHTML = entities.map((e) => {
      const port = portraitOf(e, type);
      const widgets = layout.length
        ? layout.map((it) => `<div class="pc-w" style="left:${it.x}px;top:${it.y}px">
            <div class="pc-lb">${esc(it.label)}</div><div class="pc-val">${resolve(e, type, it)}</div></div>`).join('')
        : `<div class="pc-w" style="left:14px;top:14px"><div class="pc-lb">${esc(fallbackLabel || 'Name')}</div>
            <div class="pc-val">${esc(nameOf(e, type))}</div></div>`;
      return `<div class="panel" style="padding:14px">
        <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px">
          ${port ? `<img src="${port}" style="width:40px;height:40px;border-radius:50%;object-fit:cover">` : ''}
          <b>${esc(nameOf(e, type))}</b></div>
        <div class="pc-card">${widgets}</div></div>`;
    }).join('');
  };
})();
