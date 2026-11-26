(function () {
  'use strict';

  var MONTHS = ['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
  var JKEY = 'pult_journal_v1';
  var state = { data: null, tab: 0, sheet: null, sheetDir: 'in', filter: 'all' };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function esc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function ic(name, size) {
    return '<svg class="ic" width="' + (size || 20) + '" height="' + (size || 20) +
      '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || '') + '</svg>';
  }
  function bridge(method) {
    var args = Array.prototype.slice.call(arguments, 1);
    try {
      if (window.Android && typeof Android[method] === 'function') {
        Android[method].apply(Android, args);
        return true;
      }
    } catch (e) {}
    return false;
  }
  function nowHM() {
    var d = new Date();
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }
  function todayLabel() {
    var d = new Date();
    return 'Сегодня · ' + d.getDate() + ' ' + MONTHS[d.getMonth()];
  }
  function typeIcon(d) {
    if (d.gate) return 'DoorClosed';
    if (d.type === 'barrier') return 'Fence';
    if (d.type === 'relay') return 'Power';
    return 'DoorClosed';
  }
  function kindClass(kind) {
    if (kind === 'OPEN' || kind === 'ON' || kind === 'READY') return 'ok';
    if (kind === 'MOVING') return 'warn';
    if (kind === 'OFFLINE') return 'danger';
    return 'quiet';
  }
  function statusOf(d) { return d.status || 'Проверка'; }
  function actionOf(d) { return d.action || 'Открыть'; }
  function isOnline(d) { return !!d.online; }
  function pastAction(label) {
    var map = {'Открыть':'Открыто','Закрыть':'Закрыто','Включить':'Включено','Выключить':'Выключено',
      'Стоп':'Остановлено','Нажать':'Нажато','Запустить':'Запущено'};
    return map[label] || label;
  }
  function sourceOf(d) { return d.sourceName || 'Источник'; }
  function addressOf(d) { return d.address || '—'; }
  function deviceById(id) {
    if (!state.data || !state.data.devices) return null;
    for (var i = 0; i < state.data.devices.length; i++) {
      if (state.data.devices[i].id === id) return state.data.devices[i];
    }
    return null;
  }
  function devices() { return state.data && state.data.devices ? state.data.devices : []; }

  function readJournal() {
    try {
      var raw = localStorage.getItem(JKEY);
      var list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (e) { return []; }
  }
  function writeJournal(list) {
    try { localStorage.setItem(JKEY, JSON.stringify(list.slice(0, 100))); } catch (e) {}
  }
  function logEvent(id, name, text, kind) {
    var list = readJournal();
    list.unshift({ t: Date.now(), id: id, name: name, text: text, kind: kind || 'ok' });
    writeJournal(list);
    if (state.tab === 1) renderScreen();
    if (state.sheet) renderSheet();
  }
  function journalFor(id) {
    return readJournal().filter(function (e) { return e.id === id; });
  }
  function lastEventFor(id) {
    var list = journalFor(id);
    return list.length ? list[0] : null;
  }
  function eventTime(t) {
    var d = new Date(t);
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }

  function conn() {
    var ds = devices();
    if (!state.data) return { text: 'проверка', danger: false };
    if (!ds.length) return { text: 'нет точек', danger: true };
    var online = ds.filter(function (d) { return isOnline(d); }).length;
    return online ? { text: 'на связи', danger: false } : { text: 'нет связи', danger: true };
  }

  function renderHeader() {
    var c = conn();
    var journal = state.tab === 1;
    var eyebrow = journal ? 'История проходов' : 'Система доступа';
    var title = journal ? 'Журнал' : 'Точки проезда';
    var meta = journal ? todayLabel() : 'Мост Gate-IP';
    $('#head').innerHTML =
      '<div class="headrow"><div>' +
        '<div class="eyebrow">' + esc(eyebrow) + '</div>' +
        '<h2 class="title">' + esc(title) + '</h2>' +
      '</div>' +
      '<span class="conn' + (c.danger ? ' danger' : '') + '" onclick="openRefresh()"><span class="conn-dot"></span>' + esc(c.text) + '</span></div>' +
      '<div class="headmeta"><span>' + esc(meta) + '</span><span class="mono" id="clock">' + nowHM() + '</span></div>';
  }

  function renderTabs() {
    var items = [
      ['Точки', 'LayoutGrid', 0],
      ['Журнал', 'list', 1],
      ['Настройки', 'Settings', 2]
    ];
    var html = '';
    for (var i = 0; i < items.length; i++) {
      var it = items[i];
      html += '<button class="tab' + (state.tab === it[2] ? ' on' : '') + '" type="button" onclick="switchTab(' + it[2] + ')">' +
        ic(it[1], 20) + '<span>' + it[0] + '</span></button>';
    }
    $('#tabs').innerHTML = html;
  }

  function render() {
    renderHeader();
    renderTabs();
    renderScreen();
    if (state.sheet) renderSheet(); else $('#sheetRoot').innerHTML = '';
  }

  function renderScreen() {
    if (!state.data) {
      $('#screen').innerHTML = '<div class="empty"><b>Загрузка…</b><span>Получаем точки и статусы.</span></div>';
      return;
    }
    if (state.tab === 1) renderJournal(); else renderMain();
  }

  function pickHero() {
    var ds = devices().filter(function (d) { return d.configured && !d.gate; });
    var i;
    for (i = 0; i < ds.length; i++) if (ds[i].favorite && ds[i].type === 'barrier') return ds[i];
    for (i = 0; i < ds.length; i++) if (ds[i].favorite) return ds[i];
    for (i = 0; i < ds.length; i++) if (ds[i].type === 'barrier') return ds[i];
    return ds.length ? ds[0] : null;
  }

  function heroHtml(d) {
    var cls = kindClass(d.kind);
    var last = lastEventFor(d.id);
    var meta = d.sub || sourceOf(d);
    if (last) meta = 'Последнее — ' + eventTime(last.t) + ', ' + last.text.toLowerCase();
    return '<section class="hero">' +
      '<div class="hero-top"><span class="type">' + ic(typeIcon(d), 18) + '<span>' + esc(d.typeLabel || '') + '</span></span>' +
        '<span class="pill' + (cls === 'quiet' ? '' : ' ' + cls) + '" data-pill-for="' + esc(d.id) + '">' +
          '<span class="pill-dot"></span><span data-status-for="' + esc(d.id) + '">' + esc(statusOf(d)) + '</span></span></div>' +
      '<h3 class="hero-name">' + esc(d.name) + '</h3>' +
      '<p class="meta">' + esc(meta) + '</p>' +
      '<button class="action primary"' + (isOnline(d) ? '' : ' disabled') + ' type="button" onclick="doAction(\'' + esc(d.id) + '\')">' +
        ic(typeIcon(d), 18) + '<span class="action-label" data-action-for="' + esc(d.id) + '">' + esc(actionOf(d)) + '</span></button>' +
      '</section>';
  }

  function rowHtml(d) {
    var cls = kindClass(d.kind);
    return '<button class="row" type="button" onclick="openSheet(\'' + esc(d.id) + '\')">' +
      '<span class="row-ic">' + ic(typeIcon(d), 20) + '</span>' +
      '<span class="row-main"><span class="row-name">' + esc(d.name) + '</span>' +
        '<span class="row-sub">' + esc(d.sub || sourceOf(d)) + '</span></span>' +
      '<span class="state ' + cls + '" data-status-for="' + esc(d.id) + '">' + esc(statusOf(d)) + '</span>' +
      '<span class="chev">' + ic('ChevronRight', 16) + '</span></button>';
  }

  function renderMain() {
    var ds = devices();
    if (!ds.length) {
      $('#screen').innerHTML = '<div class="empty"><b>Нет точек</b><span>Добавьте шлагбаум, калитку или дверь в настройках.</span>' +
        '<button class="linkbtn" type="button" onclick="openSettings()">Открыть настройки</button></div>';
      return;
    }
    var hero = pickHero();
    var rest = ds.filter(function (d) { return !hero || d.id !== hero.id; });
    var html = hero ? heroHtml(hero) : '';
    if (rest.length) {
      html += '<div class="section"><span class="eyebrow">' + (hero ? 'Ещё точки' : 'Точки') + '</span>' +
        '<span class="mono count">' + ('0' + rest.length).slice(-2) + '</span></div>' +
        '<div class="list">' + rest.map(rowHtml).join('') + '</div>';
    }
    $('#screen').innerHTML = html;
  }

  function sheetHtml(d) {
    var cls = kindClass(d.kind);
    var last = lastEventFor(d.id);
    var meta = last ? 'Последнее — ' + eventTime(last.t) + ', ' + last.text.toLowerCase() : 'Событий пока нет';
    var eyebrow = d.gate ? 'Проходная · Gate-IP' : ((d.typeLabel || '') + ' · ' + sourceOf(d));
    var dirs = [];
    if (d.dirIn) dirs.push('in');
    if (d.dirOut) dirs.push('out');
    var dir = state.sheetDir;
    if (dirs.indexOf(dir) < 0) dir = dirs[0] || '';
    var html = '<div class="scrim" onclick="closeSheet()"></div><aside class="sheet">' +
      '<div class="grab" onclick="closeSheet()"></div>' +
      '<div class="sheet-head"><div><div class="eyebrow">' + esc(eyebrow) + '</div><h3>' + esc(d.name) + '</h3></div>' +
        '<span class="sheet-time mono">' + nowHM() + '</span></div>' +
      '<div class="bigstate"><span class="state-dot ' + cls + '"></span><span class="bigstate-word">' + esc(statusOf(d)) + '</span></div>' +
      '<p class="meta">' + esc(meta) + '</p>';
    if (d.gate && dirs.length) {
      html += '<div class="seg">';
      if (d.dirIn) html += '<button class="' + (dir === 'in' ? 'on' : '') + '" type="button" onclick="selectDir(\'in\')">Вход</button>';
      if (d.dirOut) html += '<button class="' + (dir === 'out' ? 'on' : '') + '" type="button" onclick="selectDir(\'out\')">Выход</button>';
      html += '</div>';
    }
    var label, action;
    if (d.gate) {
      if (dirs.length) {
        label = 'Открыть ' + (dir === 'out' ? 'выход' : 'вход');
        action = 'sheetOpenDir(\'' + esc(d.id) + '\',\'' + dir + '\')';
      } else {
        label = 'Настроить';
        action = 'editDevice(\'' + esc(d.id) + '\')';
      }
    } else if (!d.configured) {
      label = 'Настроить';
      action = 'editDevice(\'' + esc(d.id) + '\')';
    } else {
      label = actionOf(d);
      action = 'doAction(\'' + esc(d.id) + '\')';
    }
    var disabled = '';
    if (d.configured && !isOnline(d)) {
      if (!d.gate || dirs.length) disabled = ' disabled';
    }
    html += '<button class="action primary big"' + disabled + ' type="button" onclick="' + action + '">' +
      ic('DoorOpen', 18) + '<span class="action-label">' + esc(label) + '</span></button>' +
      '<div class="source">' +
        '<div class="srow"><span class="slabel">Источник</span><span class="sval">' + esc(sourceOf(d)) + '</span></div>' +
        '<div class="srow"><span class="slabel">Связь</span><span class="sval ' + (isOnline(d) ? 'ok' : 'danger') + '">' + (isOnline(d) ? 'На связи' : 'Нет связи') + '</span></div>' +
        '<div class="srow"><span class="slabel">Адрес</span><span class="sval mono">' + esc(addressOf(d)) + '</span></div>' +
      '</div>';
    var evs = journalFor(d.id).slice(0, 3);
    html += '<div class="sheet-sec"><span class="eyebrow">Последние события</span><span class="mono count">' + evs.length + '</span></div>';
    if (evs.length) {
      html += '<div class="mini-events">' + evs.map(function (e) {
        return '<div class="mev"><span class="mono">' + eventTime(e.t) + '</span><span class="' + (e.kind === 'danger' ? 'danger' : '') + '">' + esc(e.text) + '</span></div>';
      }).join('') + '</div>';
    } else {
      html += '<div class="mev"><span class="mono">—</span><span>Событий пока нет</span></div>';
    }
    html += '<button class="linkrow" type="button" onclick="editDevice(\'' + esc(d.id) + '\')">Настройки устройства ' + ic('ChevronRight', 16) + '</button>' +
      '</aside>';
    return html;
  }

  function renderSheet() {
    if (!state.sheet) { $('#sheetRoot').innerHTML = ''; return; }
    var d = deviceById(state.sheet);
    if (!d) { state.sheet = null; $('#sheetRoot').innerHTML = ''; return; }
    $('#sheetRoot').innerHTML = sheetHtml(d);
  }

  function renderJournal() {
    var list = readJournal();
    if (state.filter === 'open') {
      list = list.filter(function (e) { return e.kind === 'ok' || e.kind === 'quiet'; });
    } else if (state.filter === 'error') {
      list = list.filter(function (e) { return e.kind === 'danger' || e.kind === 'warn'; });
    }
    var html = '<div class="filters">' +
      '<button class="filter' + (state.filter === 'all' ? ' on' : '') + '" type="button" onclick="setFilter(\'all\')">Все</button>' +
      '<button class="filter' + (state.filter === 'open' ? ' on' : '') + '" type="button" onclick="setFilter(\'open\')">Открытия</button>' +
      '<button class="filter' + (state.filter === 'error' ? ' on' : '') + '" type="button" onclick="setFilter(\'error\')">Ошибки</button></div>';
    if (!list.length) {
      html += '<div class="empty"><b>Пока нет событий</b><span>Откройте точку — событие появится здесь.</span></div>';
    } else {
      html += '<div class="events">' + list.map(function (e) {
        return '<div class="event"><span class="ev-time mono">' + eventTime(e.t) + '</span>' +
          '<span class="ev-dot ' + kindClass(e.kind) + '"></span>' +
          '<span class="ev-main"><span class="ev-title">' + esc(e.name) + '</span>' +
          '<span class="ev-sub ' + (e.kind === 'danger' ? 'danger' : '') + '">' + esc(e.text) + '</span></span></div>';
      }).join('') + '</div>';
    }
    $('#screen').innerHTML = html;
  }

  function updateDom() {
    var ds = devices();
    for (var i = 0; i < ds.length; i++) {
      var d = ds[i], cls = kindClass(d.kind), text = statusOf(d);
      var nodes = document.querySelectorAll('[data-status-for="' + d.id + '"]');
      for (var j = 0; j < nodes.length; j++) {
        var node = nodes[j];
        node.textContent = text;
        var pill = node.closest ? node.closest('.pill') : null;
        var st = node.closest ? node.closest('.state') : null;
        if (pill) pill.className = 'pill' + (cls === 'quiet' ? '' : ' ' + cls);
        else if (st) st.className = 'state ' + cls;
      }
      var acts = document.querySelectorAll('[data-action-for="' + d.id + '"]');
      for (var k = 0; k < acts.length; k++) acts[k].textContent = actionOf(d);
    }
    if (state.sheet) renderSheet();
  }

  function updateClock() {
    var el = document.getElementById('clock');
    if (el) el.textContent = nowHM();
  }

  window.pultData = function (data) {
    state.data = data || { devices: [] };
    var theme = state.data.theme === 'light' ? 'light' : 'dark';
    document.getElementById('app').dataset.theme = theme;
    render();
  };

  window.pultState = function (data) {
    if (!state.data || !data || !data.devices) return;
    var prev = {};
    for (var i = 0; i < state.data.devices.length; i++) prev[state.data.devices[i].id] = state.data.devices[i];
    var changed = false;
    for (var j = 0; j < data.devices.length; j++) {
      var u = data.devices[j], d = prev[u.id];
      if (!d) continue;
      var was = isOnline(d);
      d.status = u.status;
      d.kind = u.kind;
      d.action = u.action;
      d.online = u.online;
      if (was && !u.online) { logEvent(d.id, d.name, 'Нет связи', 'danger'); changed = true; }
      else if (!was && u.online && u.kind !== 'UNKNOWN') { logEvent(d.id, d.name, 'На связи', 'ok'); changed = true; }
    }
    renderHeader();
    updateDom();
    if (changed && state.tab === 1) renderScreen();
  };

  window.switchTab = function (tab) {
    if (tab === 2) { openSettings(); return; }
    state.tab = tab;
    state.sheet = null;
    $('#sheetRoot').innerHTML = '';
    render();
  };
  window.setFilter = function (f) { state.filter = f; renderScreen(); };
  window.openSheet = function (id) {
    state.sheet = id;
    var d = deviceById(id);
    if (d) {
      state.sheetDir = d.dirIn ? 'in' : (d.dirOut ? 'out' : '');
    }
    renderSheet();
  };
  window.closeSheet = function () { state.sheet = null; $('#sheetRoot').innerHTML = ''; };
  window.selectDir = function (dir) { state.sheetDir = dir; renderSheet(); };
  window.doAction = function (id) {
    var d = deviceById(id);
    if (!d) return;
    if (!d.configured) { editDevice(id); return; }
    if (d.gate) { openSheet(id); return; }
    if (!isOnline(d)) return;
    logEvent(id, d.name, pastAction(actionOf(d)) + ' · с приложения', 'ok');
    bridge('open', id);
  };
  window.sheetOpenDir = function (id, dir) {
    var d = deviceById(id);
    if (!d) return;
    var word = dir === 'out' ? 'Выход' : 'Вход';
    logEvent(id, d.name, word + ' · с приложения', 'ok');
    bridge('openDir', id, dir);
  };
  window.editDevice = function (id) { closeSheet(); bridge('edit', id); };
  window.openSettings = function () { bridge('settings'); };
  window.openRefresh = function () { bridge('refresh'); };

  document.addEventListener('DOMContentLoaded', function () {
    render();
    setInterval(updateClock, 20000);
    bridge('ready');
  });
})();
