// Renders the campaign's custom widgets on the sheet, editable + live-synced.
// Values live on the character at definition.custom[widgetId]; we patch that path
// so they flow through the same sync engine as everything else.

(function () {
  const socket = window.gmSocket;
  const patch = window.gmPatch;
  const defs = window.__CUSTOM_WIDGETS__ || [];
  const box = document.getElementById('sec-custom');
  if (!box || !socket || !defs.length) return;
  let char = window.__CHAR__;

  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const val = (w) => {
    const c = (char.definition.custom || {});
    return (w.id in c) ? c[w.id] : w.default;
  };

  function render() {
    box.innerHTML = defs.map((w) => {
      const v = val(w);
      let control;
      if (w.type === 'checkbox') {
        control = `<input type="checkbox" data-wid="${w.id}" ${v ? 'checked' : ''}>`;
      } else if (w.type === 'resource') {
        const r = v || { max: 1, used: 0 };
        let pips = '';
        for (let i = 0; i < r.max; i++) pips += `<button class="pip ${i >= r.used ? 'filled' : ''}" data-wid="${w.id}" data-i="${i}"></button>`;
        control = `<div class="pips" data-res-wid="${w.id}" data-max="${r.max}">${pips}</div>`;
      } else if (w.type === 'text') {
        control = `<input type="text" data-wid="${w.id}" value="${esc(v)}" style="width:140px">`;
      } else {
        control = `<input type="number" data-wid="${w.id}" value="${v != null ? v : 0}" style="width:80px">`;
      }
      return `<div class="kv"><span class="k">${esc(w.label)}</span><span>${control}</span></div>`;
    }).join('');

    box.querySelectorAll('input[data-wid]').forEach((el) => {
      el.addEventListener('change', () => {
        const v = el.type === 'checkbox' ? el.checked : (el.type === 'number' ? (Number(el.value) || 0) : el.value);
        patch('definition.custom.' + el.dataset.wid, v);
      });
    });
    box.querySelectorAll('[data-res-wid] .pip').forEach((pip) => {
      pip.addEventListener('click', () => {
        const wid = pip.dataset.wid, i = Number(pip.dataset.i);
        const w = defs.find((x) => x.id === wid);
        const r = { ...(val(w) || { max: 1, used: 0 }) };
        const used0 = r.used || 0;
        r.used = (i >= used0) ? r.max - i : r.max - (i + 1);
        r.used = Math.max(0, Math.min(r.max, r.used));
        patch('definition.custom.' + wid, r);
      });
    });
  }

  socket.on('character:update', (fresh) => { char = fresh; render(); });
  render();
})();
