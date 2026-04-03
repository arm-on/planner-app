(function () {
  var STORAGE_KEY = 'planner_theme';

  function getSavedTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function saveTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {}
  }

  function applyTheme(theme) {
    var root = document.documentElement;
    if (theme === 'dark') {
      root.setAttribute('data-theme', 'dark');
    } else {
      root.removeAttribute('data-theme');
    }
    syncToggleIcons(theme);
  }

  function currentTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  }

  function toggleTheme() {
    var next = currentTheme() === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    saveTheme(next);
  }

  function syncToggleIcons(theme) {
    document.querySelectorAll('[data-theme-toggle] i').forEach(function (icon) {
      icon.className = theme === 'dark' ? 'bi bi-sun' : 'bi bi-moon-stars';
    });
  }

  function ensureToggleButton() {
    var existing = document.querySelector('[data-theme-toggle]');
    if (existing) return;

    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'theme-fab';
    btn.setAttribute('data-theme-toggle', 'true');
    btn.setAttribute('title', 'Toggle theme');
    btn.innerHTML = '<i class="bi bi-moon-stars"></i>';
    document.body.appendChild(btn);
  }

  function bindToggles() {
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', toggleTheme);
    });
  }

  function initTheme() {
    var saved = getSavedTheme();
    if (saved) {
      applyTheme(saved);
    } else {
      applyTheme('light');
    }

    ensureToggleButton();
    bindToggles();
    syncToggleIcons(currentTheme());
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }
})();
