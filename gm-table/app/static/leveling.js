// XP bar, award, DM quick level-set, and the level-up modal.
(function () {
  const socket = window.gmSocket, patch = window.gmPatch, charId = window.gmCharId;
  if (!socket) return;
  let char = window.__CHAR__;
  const ABIL = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];
  const esc = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const fill = document.getElementById('xp-fill');
  const xpText = document.getElementById('xp-text');
  const xpLevel = document.getElementById('xp-level');
  const luBtn = document.getElementById('xp-levelup');
  const setClass = document.getElementById('set-class');

  function renderXp() {
    const xp = char.derived.xp;
    xpLevel.textContent = xp.level;
    const pct = char.derived.totalLevel >= 20 ? 100 : Math.min(100, 100 * xp.intoLevel / xp.span);
    fill.style.width = pct + '%';
    xpText.textContent = char.derived.totalLevel >= 20 ? `${xp.current} XP (max level)` : `${xp.current} / ${xp.nextLevelAt} XP`;
    luBtn.style.display = xp.pending > 0 ? '' : 'none';
    if (xp.pending > 1) luBtn.textContent = `⬆ Level Up! (${xp.pending})`;
    // class picker
    const classes = char.definition.classes || [];
    if (setClass.options.length !== classes.length) {
      setClass.innerHTML = classes.map((c) => `<option value="${esc(c.name)}">${esc(c.name)} ${c.level}</option>`).join('');
    }
  }

  document.getElementById('xp-award').addEventListener('click', () => {
    const inp = document.getElementById('xp-amount');
    const amt = Number(inp.value);
    if (!amt) return;
    socket.emit('xp:award', { characterId: charId, amount: amt });
    inp.value = '';
  });

  document.getElementById('do-setlevel').addEventListener('click', () => {
    const lvl = Number(document.getElementById('set-level').value);
    if (!lvl) return;
    socket.emit('level:set', { characterId: charId, class: setClass.value, level: lvl });
  });

  // ---------- level-up modal ----------
  const modal = document.getElementById('lvl-modal');
  const body = document.getElementById('lvl-body');
  let choices = {};

  async function openLevelUp() {
    // multiclass: ask which class gains the level (default the first / picker value)
    const classes = char.definition.classes || [];
    let gaining = classes.length ? classes[0].name : null;
    if (classes.length > 1) {
      gaining = setClass.value || gaining;
    }
    const plan = await fetch(`/api/levelup/plan/${charId}?class=${encodeURIComponent(gaining)}`).then((r) => r.json());
    if (plan.error) { alert(plan.error); return; }
    choices = { gainingClass: plan.gainingClass, hpGain: 0, asi: null, feat: null, subclassName: '' };
    renderModal(plan, classes);
    modal.classList.add('show');
  }

  function renderModal(plan, classes) {
    const catReady = window.__CATALOG__;
    let h = `<p class="lu-sub">Taking <b>${esc(plan.gainingClass)}</b> to level ${plan.newClassLevel}
      (character level ${plan.newTotalLevel}).</p>`;

    if (classes.length > 1) {
      h += `<div class="lu-step"><label class="lu-q">Which class gains this level?</label>
        <select id="lu-class">${classes.map((c) => `<option ${c.name === plan.gainingClass ? 'selected' : ''}>${esc(c.name)}</option>`).join('')}</select></div>`;
    }

    plan.steps.forEach((step) => {
      if (step.type === 'hp') {
        h += `<div class="lu-step"><label class="lu-q">Hit points</label>
          <div class="lu-help">${esc(step.help)}</div>
          <div class="lu-hp">
            <label><input type="radio" name="hp" value="avg" checked> Average (${step.average})</label>
            <label><input type="radio" name="hp" value="roll"> Rolled: <input type="number" id="hp-roll" style="width:60px" placeholder="total"> + CON ${step.conMod >= 0 ? '+' : ''}${step.conMod}</label>
          </div></div>`;
        choices.hpGain = step.average;
        choices._hpAvg = step.average; choices._die = step.die; choices._con = step.conMod;
      } else if (step.type === 'asi_feat') {
        h += `<div class="lu-step"><label class="lu-q">Ability Score Improvement or Feat</label>
          <div class="lu-help">${esc(step.help)}</div>
          <div class="lu-toggle"><label><input type="radio" name="af" value="asi" checked> Improve abilities</label>
            <label><input type="radio" name="af" value="feat"> Take a feat</label></div>
          <div id="af-asi">
            <div class="lu-help">+2 to one, or +1 to two (max 20).</div>
            ${ABIL.map((a) => `<label class="asi-pick">${a} <input type="number" min="0" max="2" value="0" data-asi="${a}" style="width:48px"></label>`).join('')}
          </div>
          <div id="af-feat" style="display:none">
            <select id="feat-pick"><option value="">— choose a feat —</option></select>
            <div id="feat-desc" class="lu-help"></div>
            <div id="feat-asi" style="display:none"><label class="lu-q" style="font-size:12px">This feat also grants an ability point:</label>
              <select id="feat-asi-pick">${ABIL.map((a) => `<option>${a}</option>`).join('')}</select></div>
          </div></div>`;
      } else {
        h += `<div class="lu-step"><label class="lu-q">${step.type === 'subclass' ? 'Subclass' : step.type === 'spells' ? 'Spells' : 'New features'}</label>
          <div class="lu-help">${esc(step.help)}</div>
          ${step.type === 'subclass' ? `<input id="subclass-name" placeholder="Subclass name (e.g. Hunter)" style="width:100%">` : ''}</div>`;
      }
    });
    body.innerHTML = h;
    wireModal(plan);
  }

  function wireModal(plan) {
    const clsSel = document.getElementById('lu-class');
    if (clsSel) clsSel.addEventListener('change', async () => {
      const p = await fetch(`/api/levelup/plan/${charId}?class=${encodeURIComponent(clsSel.value)}`).then((r) => r.json());
      choices.gainingClass = p.gainingClass;
      renderModal(p, char.definition.classes);
    });

    body.querySelectorAll('input[name=hp]').forEach((r) => r.addEventListener('change', updateHp));
    const hpRoll = document.getElementById('hp-roll');
    if (hpRoll) hpRoll.addEventListener('input', updateHp);
    function updateHp() {
      const mode = (body.querySelector('input[name=hp]:checked') || {}).value;
      if (mode === 'roll') {
        const rolled = Number((document.getElementById('hp-roll') || {}).value) || 0;
        choices.hpGain = Math.max(1, rolled + choices._con);
      } else {
        choices.hpGain = choices._hpAvg;
      }
    }

    // ASI vs feat
    const afAsi = document.getElementById('af-asi'), afFeat = document.getElementById('af-feat');
    body.querySelectorAll('input[name=af]').forEach((r) => r.addEventListener('change', () => {
      const v = body.querySelector('input[name=af]:checked').value;
      if (afAsi) afAsi.style.display = v === 'asi' ? '' : 'none';
      if (afFeat) afFeat.style.display = v === 'feat' ? '' : 'none';
    }));

    // populate feat dropdown from catalog
    const featPick = document.getElementById('feat-pick');
    if (featPick && window.__CATALOG__) {
      window.__CATALOG__.feats.forEach((f) => {
        const o = document.createElement('option'); o.value = f.name; o.textContent = `${f.name} (${f.category})`;
        o._feat = f; featPick.appendChild(o);
      });
      featPick.addEventListener('change', () => {
        const f = featPick.selectedOptions[0] && featPick.selectedOptions[0]._feat;
        document.getElementById('feat-desc').textContent = f ? f.text : '';
        const fa = document.getElementById('feat-asi');
        fa.style.display = (f && (f.asi === 'choice' || f.asi === 'STR_or_DEX')) ? '' : 'none';
      });
    }
  }

  document.getElementById('lvl-confirm').addEventListener('click', () => {
    // gather ASI / feat
    const af = (body.querySelector('input[name=af]:checked') || {}).value;
    let asi = null, feat = null;
    if (af === 'asi') {
      asi = {};
      body.querySelectorAll('[data-asi]').forEach((i) => { const v = Number(i.value) || 0; if (v) asi[i.dataset.asi] = v; });
      if (!Object.keys(asi).length) asi = null;
    } else if (af === 'feat') {
      const sel = document.getElementById('feat-pick');
      const f = sel && sel.selectedOptions[0] && sel.selectedOptions[0]._feat;
      if (f) {
        feat = { name: f.name, text: f.text };
        const fa = document.getElementById('feat-asi');
        if (fa && fa.style.display !== 'none') asi = { [document.getElementById('feat-asi-pick').value]: 1 };
      }
    }
    const sub = document.getElementById('subclass-name');
    socket.emit('levelup:apply', {
      characterId: charId, gainingClass: choices.gainingClass,
      hpGain: choices.hpGain, asi, feat, subclassName: sub ? sub.value : '',
    });
    modal.classList.remove('show');
  });

  luBtn.addEventListener('click', openLevelUp);
  document.getElementById('lvl-close').addEventListener('click', () => modal.classList.remove('show'));
  document.getElementById('lvl-cancel').addEventListener('click', () => modal.classList.remove('show'));

  // load catalog once for the feat picker
  fetch('/api/content').then((r) => r.json()).then((c) => { window.__CATALOG__ = c; });

  socket.on('character:update', (fresh) => { char = fresh; renderXp(); });
  renderXp();
})();
