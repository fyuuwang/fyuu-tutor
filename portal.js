(function () {
  // Progressive enhancement: hide non-active panels only when JS runs.
  // Without JS the class is never added, so every panel stays visible and
  // all project/lesson links remain reachable in source order.
  var root = document.documentElement;
  root.classList.add('js');
  function groups(scope) {
    return Array.prototype.slice.call(
      scope.querySelectorAll('[role="tablist"]'));
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
