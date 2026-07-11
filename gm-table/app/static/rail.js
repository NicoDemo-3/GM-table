// Left vertical tool rail + dice roller.
// Dice behaviour matches the reference: tap a die to ADD it to the tray (one at a
// time, any mix of types), nothing rolls until you press Roll. Rest buttons fire a
// 'gm-rest' event that the sheet turns into a server call. No socket needed here.

(function () {
  document.body.classList.add('has-rail');

  // ---- dice icon SVGs (colored polygons, screenshot palette) ----
  const DICE = [
    { t: 'd4', sides: 4, color: '#f08a3c', poly: '17,3 31,29 3,29' },
    { t: 'd6', sides: 6, color: '#9b59c6', poly: '5,5 29,5 29,29 5,29' },
    { t: 'd8', sides: 8, color: '#3f6fd1', poly: '17,2 30,17 17,32 4,17' },
    { t: 'd10', sides: 10, color: '#46c7d6', poly: '17,2 30,13 24,30 10,30 4,13' },
    { t: 'd12', sides: 12, color: '#5fc16b', poly: '17,2 28,8 31,20 23,30 11,30 3,20 6,8' },
    { t: 'd20', sides: 20, color: '#e0473f', poly: '17,2 30,10 30,24 17,32 4,24 4,10' },
    { t: 'd100', sides: 100, color: '#45b6c4', poly: '17,2 30,13 24,30 10,30 4,13' },
  ];
  const SIDES = Object.fromEntries(DICE.map((d) => [d.t, d.sides]));
  function svg(d) {
    return `<svg viewBox="0 0 34 34"><polygon points="${d.poly}" fill="${d.color}"
      stroke="rgba(0,0,0,.35)" stroke-width="1.5" stroke-linejoin="round"/></svg>`;
  }
  function svgFor(t) { return svg(DICE.find((d) => d.t === t)); }

  // ---- build rail ----
  const rail = document.createElement('div');
  rail.className = 'rail';
  rail.innerHTML = `
    <button data-rail="short" title="Short Rest"><span class="ico">☕</span>Short</button>
    <button data-rail="long" title="Long Rest"><span class="ico">🌙</span>Long</button>
    <div class="sep"></div>
    <button data-rail="dice" title="Dice Roller"><span class="ico">🎲</span>Dice</button>
    <button data-rail="theme" title="Light / Dark" onclick="gmToggleTheme()"><span class="ico" data-theme-icon>☾</span>Theme</button>`;
  document.body.appendChild(rail);

  // ---- build dice popup ----
  const pop = document.createElement('div');
  pop.className = 'dice-pop';
  pop.innerHTML = `
    <div class="dice-head"><span class="t">Dice Roller</span><span class="x" id="dice-close">×</span></div>
    <div class="dice-body">
      <div class="dice-row" id="dice-row"></div>
      <div class="tray empty" id="dice-tray">Tap dice above to add them</div>
      <div class="dice-actions">
        <button class="btn ghost" id="dice-clear">Clear</button>
        <button class="btn" id="dice-roll">Roll</button>
      </div>
      <div class="dice-result" id="dice-result"></div>
    </div>`;
  document.body.appendChild(pop);

  const row = pop.querySelector('#dice-row');
  DICE.forEach((d) => {
    const b = document.createElement('button');
    b.className = 'die'; b.dataset.die = d.t;
    b.innerHTML = `${svg(d)}<span class="dl">${d.t.toUpperCase()}</span>`;
    b.addEventListener('click', () => add(d.t));
    row.appendChild(b);
  });

  let tray = {}; // { d6: 1, d12: 7, ... }
  const trayEl = pop.querySelector('#dice-tray');
  const resultEl = pop.querySelector('#dice-result');

  function add(t) { tray[t] = (tray[t] || 0) + 1; renderTray(); }
  function removeOne(t) { if (tray[t]) { tray[t]--; if (!tray[t]) delete tray[t]; renderTray(); } }

  function renderTray() {
    const keys = DICE.map((d) => d.t).filter((t) => tray[t]);
    if (!keys.length) {
      trayEl.className = 'tray empty';
      trayEl.textContent = 'Tap dice above to add them';
      return;
    }
    trayEl.className = 'tray';
    trayEl.innerHTML = keys.map((t) =>
      `<span class="grp" data-rm="${t}" title="Click to remove one">${tray[t]} ${svgFor(t)}</span>`
    ).join('');
    trayEl.querySelectorAll('[data-rm]').forEach((g) =>
      g.addEventListener('click', () => removeOne(g.dataset.rm)));
  }

  pop.querySelector('#dice-clear').addEventListener('click', () => {
    tray = {}; renderTray(); resultEl.className = 'dice-result';
  });

  pop.querySelector('#dice-roll').addEventListener('click', () => {
    const keys = DICE.map((d) => d.t).filter((t) => tray[t]);
    if (!keys.length) return;
    let total = 0;
    const parts = [];
    let critNote = '';
    keys.forEach((t) => {
      const sides = SIDES[t];
      const rolls = [];
      for (let i = 0; i < tray[t]; i++) {
        const r = 1 + Math.floor(Math.random() * sides);
        rolls.push(r); total += r;
        if (t === 'd20' && tray[t] === 1 && keys.length === 1) {
          if (r === 20) critNote = 'Natural 20!';
          else if (r === 1) critNote = 'Natural 1…';
        }
      }
      parts.push(`${tray[t]}${t} [${rolls.join(', ')}]`);
    });
    resultEl.className = 'dice-result show';
    resultEl.innerHTML =
      `<div class="total">${total}</div>` +
      (critNote ? `<div class="crit">${critNote}</div>` : '') +
      `<div class="breakdown">${parts.join('  ·  ')}</div>`;
  });

  // ---- rail wiring ----
  const diceBtn = rail.querySelector('[data-rail="dice"]');
  function toggleDice() {
    const open = pop.classList.toggle('show');
    diceBtn.classList.toggle('active', open);
  }
  diceBtn.addEventListener('click', toggleDice);
  pop.querySelector('#dice-close').addEventListener('click', toggleDice);

  rail.querySelector('[data-rail="short"]').addEventListener('click', () => confirmRest('short'));
  rail.querySelector('[data-rail="long"]').addEventListener('click', () => confirmRest('long'));
  function confirmRest(kind) {
    const msg = kind === 'long'
      ? 'Take a LONG REST? Restores all HP and spell slots, half your hit dice, long-rest abilities, and drops one level of exhaustion.'
      : 'Take a SHORT REST? Refreshes short-rest abilities. (Spend hit dice on the sheet to heal.)';
    if (confirm(msg)) document.dispatchEvent(new CustomEvent('gm-rest', { detail: { kind } }));
  }
})();
