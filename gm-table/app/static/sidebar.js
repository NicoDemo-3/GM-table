// Collapsible DM tools sidebar. Included only on DM-facing pages (never on the
// pure player screens). Reads window.__CID__ for campaign-scoped links, remembers
// its open/closed state, and highlights the current page.

(function () {
  if (window.self !== window.top) { document.body.classList.add("embedded"); return; }
  const cid = window.__CID__;
  if (!cid) return;

  const ITEMS = [
    ['Dashboard', '', '⌂'],
    ['Canvas', '/canvas', '🧭'],
    ['Combat', '/combat', '⚔'],
    ['Bestiary', '/bestiary', '🐉'],
    ['Compendium', '/compendium', '📚'],
    ['NPCs', '/npcs', '👤'],
    ['Roll Tables', '/tables', '🎲'],
    ['Shop', '/shop', '🏪'],
    ['Player Content', '/player-content', '🎫'],
    ['World & Time', '/world', '☀'],
    ['Map', '/map', '🗺'],
    ['Soundboard', '/sounds', '🔊'],
    ['Widget Library', '/widgets', '🧩'],
    ['Sheet Builder', '/builder', '📐'],
    ['Party Cards', '/party-cards', '🃏'],
  ];
  const EXTRA = [
    ['DM Overview', '/overview', '👁', true],
    ['Player Portal', '/play', '🎭', true],
  ];

  const here = location.pathname;
  const base = '/c/' + cid;
  const collapsed = localStorage.getItem('gmSidebar') === 'closed';

  const aside = document.createElement('aside');
  aside.className = 'dm-sidebar' + (collapsed ? ' collapsed' : '');
  const link = (label, path, icon, blank) => {
    const href = path === '' ? base : base + path;
    const active = (here === href) || (path === '' && here === base);
    return `<a class="dm-link ${active ? 'active' : ''}" href="${href}" ${blank ? 'target="_blank"' : ''}>
      <span class="ic">${icon}</span><span class="lb">${label}${blank ? ' ↗' : ''}</span></a>`;
  };

  aside.innerHTML =
    `<div class="dm-top"><button class="dm-toggle" title="Collapse">☰</button><span class="dm-title lb">DM Tools</span></div>
     <nav>${ITEMS.map((i) => link(...i)).join('')}
       <div class="dm-div"></div>
       ${EXTRA.map((i) => link(...i)).join('')}
       <a class="dm-link" href="/content" target="_blank"><span class="ic">📖</span><span class="lb">Content & Rules ↗</span></a>
       <a class="dm-link" href="/reference?c=${cid}" target="_blank"><span class="ic">📚</span><span class="lb">Reference Library ↗</span></a>
       <a class="dm-link" href="/dm-links?c=${cid}" target="_blank"><span class="ic">🔗</span><span class="lb">DM Links ↗</span></a>
       <a class="dm-link" href="/"><span class="ic">≡</span><span class="lb">All Campaigns</span></a>
     </nav>`;
  document.body.appendChild(aside);
  document.body.classList.add('has-sidebar');
  if (collapsed) document.body.classList.add('sidebar-collapsed');

  aside.querySelector('.dm-toggle').addEventListener('click', () => {
    const nowCollapsed = aside.classList.toggle('collapsed');
    document.body.classList.toggle('sidebar-collapsed', nowCollapsed);
    localStorage.setItem('gmSidebar', nowCollapsed ? 'closed' : 'open');
  });
})();
