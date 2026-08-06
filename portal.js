(function () {
  // Progressive enhancement: hide non-active panels only when JS runs.
  // Without JS the class is never added, so every panel stays visible and
  // all project/lesson links remain reachable in source order.
  var root = document.documentElement;
  root.classList.add('js');
  function groups(scope) {
    return Array.prototype.slice.call(
      scope.querySelectorAll('[role="tablist"]:not([data-navigation="weekly"])'));
  }
  function tabsOf(list) {
    return Array.prototype.slice.call(
      list.querySelectorAll('[role="tab"]'));
  }
  function panelsOf(scope, groupId) {
    return Array.prototype.slice.call(
      scope.querySelectorAll('[role="tabpanel"][data-group="' + groupId + '"]'));
  }
  function select(list, tab) {
    var scope = list.closest('[data-tabs-scope]') || document;
    var groupId = list.getAttribute('data-group') || '';
    tabsOf(list).forEach(function (t) {
      var on = t === tab;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      if (t.id) {
        var p = scope.querySelector('[role="tabpanel"][aria-labelledby="' + t.id + '"]');
        if (p) p.setAttribute('data-active', on ? 'true' : 'false');
      }
    });
    panelsOf(scope, groupId).forEach(function (p) {
      p.setAttribute('data-active', 'false');
    });
    if (tab.id) {
      var panel = scope.querySelector('[role="tabpanel"][aria-labelledby="' + tab.id + '"]');
      if (panel) panel.setAttribute('data-active', 'true');
    }
  }
  function fromHash(scope) {
    var hash = (location.hash || '').replace(/^#/, '');
    if (!hash) return null;
    var tab = scope.querySelector('[role="tab"][data-hash="' + hash + '"]');
    return tab || null;
  }
  function activate(scope) {
    groups(scope).forEach(function (list) {
      var first = tabsOf(list)[0];
      var target = fromHash(scope) || first;
      if (target) select(list, target);
    });
  }
  function initScope(scope) {
    groups(scope).forEach(function (list) {
      tabsOf(list).forEach(function (tab) {
        tab.addEventListener('click', function (e) {
          e.preventDefault();
          var h = tab.getAttribute('data-hash');
          if (h) { location.hash = h; }
          select(list, tab);
        });
      });
    });
    activate(scope);
  }
  document.addEventListener('DOMContentLoaded', function () {
    initScope(document);
  });
  window.addEventListener('hashchange', function () {
    activate(document);
  });
  document.addEventListener('keydown', function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
    var active = document.activeElement;
    if (!active || active.getAttribute('role') !== 'tab') return;
    var list = active.closest('[role="tablist"]');
    if (!list) return;
    if (list.getAttribute('data-navigation') === 'weekly') return;
    var tabs = tabsOf(list);
    var i = tabs.indexOf(active);
    if (i < 0) return;
    var n = e.key === 'ArrowRight' ? (i + 1) % tabs.length : (i - 1 + tabs.length) % tabs.length;
    var target = tabs[n];
    var h = target.getAttribute('data-hash');
    if (h) { location.hash = h; }
    select(list, target);
    target.focus();
    e.preventDefault();
  });
})();
+(function () {
  var root = document.documentElement;
  root.classList.add('js');
  var key = 'fyuu-tutor:pmp-certification:week';
  function tabs(list) { return Array.prototype.slice.call(list.querySelectorAll('[role="tab"]')); }
  function panel(list, tab) {
    var id = tab.getAttribute('aria-controls');
    return id ? document.getElementById(id) : null;
  }
  function pick(list, tab, persist) {
    tabs(list).forEach(function (item) {
      var on = item === tab;
      item.setAttribute('aria-selected', on ? 'true' : 'false');
      item.setAttribute('tabindex', on ? '0' : '-1');
      var target = panel(list, item);
      if (target) target.setAttribute('data-active', on ? 'true' : 'false');
    });
    if (persist) {
      var hash = tab.getAttribute('data-hash');
      if (hash) window.location.hash = hash;
      try { window.localStorage.setItem(key, tab.getAttribute('data-hash') || ''); } catch (error) {}
    }
  }
  function byHash(list, value) {
    value = (value || '').replace(/^#/, '').toLowerCase();
    return tabs(list).find(function (tab) { return tab.getAttribute('data-hash') === value; });
  }
  function initial(list) {
    var all = tabs(list);
    if (!all.length) return;
    var rawHash = (window.location.hash || '').replace(/^#/, '');
    var target = rawHash ? byHash(list, rawHash) : null;
    if (rawHash && !target) target = all[all.length - 1];
    if (!rawHash) {
      var stored = '';
      try { stored = window.localStorage.getItem(key) || ''; } catch (error) {}
      target = byHash(list, stored) || all[all.length - 1];
    }
    pick(list, target, false);
  }
  function init() {
    document.querySelectorAll('[role="tablist"][data-navigation="weekly"]').forEach(function (list) {
      tabs(list).forEach(function (tab) {
        tab.addEventListener('click', function (event) {
          event.preventDefault();
          pick(list, tab, true);
        });
      });
      initial(list);
    });
  }
  document.addEventListener('DOMContentLoaded', init);
  window.addEventListener('hashchange', function () {
    document.querySelectorAll('[role="tablist"][data-navigation="weekly"]').forEach(function (list) {
      var all = tabs(list);
      var target = byHash(list, window.location.hash);
      pick(list, target || all[all.length - 1], false);
    });
  });
  document.addEventListener('keydown', function (event) {
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    var active = document.activeElement;
    if (!active || active.getAttribute('role') !== 'tab') return;
    var list = active.closest('[role="tablist"][data-navigation="weekly"]');
    if (!list) return;
    var all = tabs(list), index = all.indexOf(active), next = index;
    if (event.key === 'ArrowRight') next = (index + 1) % all.length;
    else if (event.key === 'ArrowLeft') next = (index - 1 + all.length) % all.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = all.length - 1;
    else return;
    event.preventDefault();
    pick(list, all[next], true);
    all[next].focus();
  });
})();
