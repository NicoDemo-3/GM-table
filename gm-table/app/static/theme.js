// Light/dark theme, persisted in the browser. The no-flash initial set happens
// inline in each page's <head>; this file just handles toggling + icon state.
window.gmToggleTheme = function () {
  const cur = document.documentElement.getAttribute('data-theme') || 'light';
  const next = cur === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('gmtheme', next); } catch (e) {}
  document.querySelectorAll('[data-theme-icon]').forEach((el) => {
    el.textContent = next === 'dark' ? '☀' : '☾';
  });
};
document.addEventListener('DOMContentLoaded', () => {
  const dark = (document.documentElement.getAttribute('data-theme') === 'dark');
  document.querySelectorAll('[data-theme-icon]').forEach((el) => {
    el.textContent = dark ? '☀' : '☾';
  });
});
