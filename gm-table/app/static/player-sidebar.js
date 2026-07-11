// Player sidebar — slim NAVIGATION only. All the actual content (rules, pushed
// items, notes) lives on its own full page at /c/<cid>/guide. This keeps the
// sidebar simple and avoids cramming/overflow. Top item is a one-tap link back
// to the character the player picked (remembered per browser).

(function () {
  if (window.self !== window.top) return;               // not inside an embedded iframe
  const cid = window.__CID__ || window.__PLAYER_CID__;
  if (!cid) return;

  const esc = s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  // remember this player's character (set on the sheet page) so "My Character" works anywhere
  const charKey = 'playerChar:' + cid;
  if (window.__CHAR__ && window.__CHAR__.id) {
    localStorage.setItem(charKey, JSON.stringify({
      id: window.__CHAR__.id,
      name: (window.__CHAR__.definition && window.__CHAR__.definition.name) || 'My Character'
    }));
  }
  let myChar = null;
  try { myChar = JSON.parse(localStorage.getItem(charKey) || 'null'); } catch (e) {}

  const collapsed = localStorage.getItem('playerSidebar') === 'closed';

  const links = [];
  if (myChar) links.push(`<a class="dm-link ps-char" href="/sheet/${esc(myChar.id)}"><span class="ic">🧝</span><span class="lb">My Character</span></a>`);
  links.push(`<a class="dm-link" href="/c/${esc(cid)}/play"><span class="ic">🎭</span><span class="lb">The Party</span></a>`);
  links.push(`<a class="dm-link" href="/c/${esc(cid)}/guide"><span class="ic">📖</span><span class="lb">Player Guide</span></a>`);

  const aside = document.createElement('aside');
  aside.className = 'dm-sidebar' + (collapsed ? ' collapsed' : '');
  aside.innerHTML = `
    <div class="dm-top">
      <button class="dm-toggle" title="Collapse">☰</button>
      <span class="dm-title lb">Player</span>
    </div>
    <nav>${links.join('')}</nav>`;
  document.body.appendChild(aside);
  document.body.classList.add('has-sidebar');
  if (collapsed) document.body.classList.add('sidebar-collapsed');

  // mark the active link
  aside.querySelectorAll('.dm-link').forEach(a => {
    if (a.getAttribute('href') === location.pathname) a.classList.add('active');
  });

  aside.querySelector('.dm-toggle').addEventListener('click', () => {
    const now = aside.classList.toggle('collapsed');
    document.body.classList.toggle('sidebar-collapsed', now);
    localStorage.setItem('playerSidebar', now ? 'closed' : 'open');
  });
})();
