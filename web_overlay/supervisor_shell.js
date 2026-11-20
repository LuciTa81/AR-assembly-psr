(function () {
  'use strict';
  const defaults = {theme:'dark', motion:true, highlight:true};
  function parseAppearance(raw) {
    let value;
    try { value = JSON.parse(raw); } catch { return {...defaults}; }
    if (!value || typeof value !== 'object') return {...defaults};
    return {theme:['light','dark','system'].includes(value.theme) ? value.theme : defaults.theme,
      motion:typeof value.motion === 'boolean' ? value.motion : true,
      highlight:typeof value.highlight === 'boolean' ? value.highlight : true};
  }
  function resolveAppearance(preference, dark, reduced) {
    const motion = preference.motion && !reduced;
    return {theme:preference.theme === 'system' ? dark ? 'dark' : 'light' : preference.theme,
      motion, highlight:preference.highlight && motion};
  }
  function routeFromHash(hash) {
    const route = hash.slice(1);
    return ['live','history','tracking','settings'].includes(route) ? route : 'live';
  }
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {parseAppearance, resolveAppearance, routeFromHash};
    return;
  }
  const key = 'arassembly.supervisor.appearance.v1', root = document.documentElement;
  const dark = matchMedia('(prefers-color-scheme: dark)'), reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let preference;
  try { preference = parseAppearance(localStorage.getItem(key)); } catch { preference = {...defaults}; }
  const node = id => document.getElementById(id);
  function apply() {
    const resolved = resolveAppearance(preference, dark.matches, reduced.matches);
    root.dataset.theme = resolved.theme;
    root.dataset.motion = resolved.motion ? 'on' : 'off';
    root.dataset.highlight = resolved.highlight ? 'on' : 'off';
    const toggle = node('themeToggle');
    if (!toggle) return;
    toggle.title = resolved.theme === 'dark' ? '라이트 모드로 전환' : '다크 모드로 전환';
    toggle.setAttribute('aria-label', toggle.title);
    toggle.setAttribute('aria-pressed', String(resolved.theme === 'dark'));
    document.querySelectorAll('input[name=theme]').forEach(input => {input.checked = input.value === preference.theme;});
    node('motionEnabled').checked = preference.motion;
    node('highlightEnabled').checked = preference.highlight;
    node('motionStatus').textContent = reduced.matches ? '시스템의 동작 줄이기 설정 적용 중' : resolved.motion ? '동작 효과 켜짐' : '동작 효과 꺼짐';
  }
  function save(change) {
    preference = {...preference, ...change};
    try { localStorage.setItem(key, JSON.stringify(preference)); } catch { /* Session-only preferences remain usable. */ }
    apply();
  }
  // Apply before CSS is parsed to avoid a flash of the opposite theme.
  apply();
  document.addEventListener('DOMContentLoaded', () => {
    const titles = {live:'실시간 관제',history:'작업 기록',tracking:'연결·진단',settings:'설정'};
    const tabs = [...document.querySelectorAll('[role=tab]')];
    function showView() {
      const route = routeFromHash(location.hash);
      const focused = document.activeElement;
      root.dataset.view = route;
      node('pageTitle').textContent = titles[route];
      node('returnToLive').hidden = route === 'live';
      tabs.forEach(tab => {
        const active = tab.dataset.view === route;
        tab.setAttribute('aria-selected',String(active));
        tab.tabIndex = active ? 0 : -1;
        node('view-'+tab.dataset.view).hidden = !active;
      });
      if (focused && focused !== document.body && !focused.getClientRects().length)
        node('tab-'+route).focus();
      document.title = titles[route] + ' | AR Assembly';
    }
    function go(route) {
      if (location.hash !== '#'+route) location.hash = route;
      showView();
    }
    tabs.forEach((tab,index) => {
      tab.addEventListener('click', () => go(tab.dataset.view));
      tab.addEventListener('keydown', event => {
        const next = event.key === 'ArrowRight' ? (index+1)%tabs.length : event.key === 'ArrowLeft'
          ? (index+tabs.length-1)%tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length-1 : null;
        if (next === null) return;
        event.preventDefault(); tabs[next].focus(); go(tabs[next].dataset.view);
      });
    });
    window.addEventListener('hashchange',showView);
    document.querySelector('.skip-link').addEventListener('click',event => {
      event.preventDefault(); go('live'); node('actionSurface').focus();
    });
    node('themeToggle').addEventListener('click',() => save({theme:root.dataset.theme === 'dark' ? 'light' : 'dark'}));
    document.querySelectorAll('input[name=theme]').forEach(input => input.addEventListener('change',() => save({theme:input.value})));
    node('motionEnabled').addEventListener('change',event => save({motion:event.target.checked}));
    node('highlightEnabled').addEventListener('change',event => save({highlight:event.target.checked}));
    node('settingsVideo').checked = node('videoEnabled').checked;
    node('showVideo').addEventListener('click',() => {
      node('videoEnabled').checked = true;
      node('videoEnabled').dispatchEvent(new Event('change'));
      node('videoEnabled').focus();
    });
    node('settingsVideo').addEventListener('change',event => {
      node('videoEnabled').checked = event.target.checked;
      node('videoEnabled').dispatchEvent(new Event('change'));
    });
    node('videoEnabled').addEventListener('change',() => {node('settingsVideo').checked = node('videoEnabled').checked;});
    const fullscreenDisplay = matchMedia('(display-mode: fullscreen)');
    function updateFullscreen() {
      root.dataset.fullscreen = String(Boolean(document.fullscreenElement) || fullscreenDisplay.matches);
      root.dataset.scrollbarVisible = 'false';
    }
    function updateScrollbar(event) {
      if (root.dataset.fullscreen !== 'true') return;
      // Keep the native scrollbar available while dragging; never change its width.
      if (event.buttons && root.dataset.scrollbarVisible === 'true') return;
      root.dataset.scrollbarVisible = String(event.pointerType !== 'touch' && event.clientX >= window.innerWidth - 28);
    }
    document.addEventListener('fullscreenchange',updateFullscreen);
    fullscreenDisplay.addEventListener('change',updateFullscreen);
    document.addEventListener('pointermove',updateScrollbar,{passive:true});
    document.addEventListener('pointerup',updateScrollbar,{passive:true});
    root.addEventListener('pointerleave',updateScrollbar,{passive:true});
    window.addEventListener('blur',() => {root.dataset.scrollbarVisible = 'false';});
    document.addEventListener('keydown',event => {
      if (root.dataset.fullscreen === 'true' && ['Tab','ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(event.key))
        root.dataset.scrollbarVisible = 'true';
    });
    updateFullscreen();
    document.querySelectorAll('[data-hover]').forEach(element => {
      element.addEventListener('pointermove',event => {
        if (root.dataset.highlight !== 'on' || event.pointerType === 'touch' ||
          element.matches(':disabled') || event.target.closest('[data-hover]') !== element ||
          event.target.closest('button:disabled,.feedback')) {
          element.dataset.hovering = 'false';
          return;
        }
        const rect = element.getBoundingClientRect();
        const x = event.clientX - rect.left, y = event.clientY - rect.top;
        element.style.setProperty('--hover-x',x+'px');
        element.style.setProperty('--hover-y',y+'px');
        element.dataset.hovering = 'true';
      });
      element.addEventListener('pointerleave',() => {element.dataset.hovering = 'false';});
    });
    dark.addEventListener('change',apply); reduced.addEventListener('change',apply);
    window.addEventListener('storage',event => {
      if (event.key === key || event.key === null) {preference = parseAppearance(event.newValue); apply();}
    });
    window.addEventListener('pageshow',event => {
      if (event.persisted) {apply(); showView(); node('settingsVideo').checked = node('videoEnabled').checked;}
    });
    apply(); showView();
  });
})();
