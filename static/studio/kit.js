/*
 * Studio editor kit: the building blocks every builder page uses.
 *
 *   var kit = StudioKit.create({ api: '/studio/api/', onSaved: fn, refresh: fn });
 *
 * - kit.h(tag, props, ...children)   DOM building with textContent, never HTML strings
 * - kit.api(path, {method, body|form}) fetch with the CSRF cookie, JSON in and out
 * - kit.input / select / toggle / segmented / chips / imageField   fields that save themselves
 * - kit.act(path, body, {confirm})    structural changes (add, delete, move), then refresh
 * - kit.dragHandle / arrows / enableDrag   reordering by mouse or buttons
 *
 * A "target" names what a field edits: { path: 'projects/5/', item: obj, locked: false }.
 * Field edits are merged per target and saved 0.7 s after the last keystroke.
 * Loaded before each page script; see docs/STUDIO_ARCHITECTURE.md.
 */
(function () {
  'use strict';

  function append(el, child) {
    if (child === null || child === undefined || child === false) { return; }
    if (Array.isArray(child)) { child.forEach(function (c) { append(el, c); }); return; }
    el.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }

  function h(tag, props) {
    var el = document.createElement(tag);
    Object.keys(props || {}).forEach(function (key) {
      var value = props[key];
      if (value === null || value === undefined || value === false) { return; }
      if (key === 'class') { el.className = value; }
      else if (key === 'text') { el.textContent = value; }
      else if (key.slice(0, 2) === 'on') { el.addEventListener(key.slice(2), value); }
      else if (key === 'value' || key === 'checked' || key === 'disabled' || key === 'selected') { el[key] = value; }
      else { el.setAttribute(key, value === true ? '' : value); }
    });
    for (var i = 2; i < arguments.length; i++) { append(el, arguments[i]); }
    return el;
  }

  function clear(el) { while (el.firstChild) { el.removeChild(el.firstChild); } }

  function csrfToken() {
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : '';
  }

  var uid = 0;
  function nextId() { uid += 1; return 'st-f' + uid; }

  function create(opts) {
    var API = opts.api;
    var saveEl = document.getElementById('ed-save');
    var queue = {};
    var inFlight = 0;
    var dragging = null;

    function setSave(state, text) {
      if (!saveEl) { return; }
      saveEl.dataset.state = state;
      saveEl.textContent = text;
    }

    function api(path, o) {
      o = o || {};
      var init = { method: o.method || 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': csrfToken() } };
      if (o.form) { init.body = o.form; }
      else if (init.method !== 'GET') { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(o.body || {}); }
      return fetch(API + path, init).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) { return { ok: res.ok, status: res.status, data: data }; });
      }).catch(function () { return { ok: false, status: 0, data: { error: 'Could not reach the server. Check your connection.' } }; });
    }

    // ---- autosave

    function fieldError(path, field, message) {
      var box = document.querySelector('[data-key="' + CSS.escape(path + ':' + field) + '"]');
      if (!box) { return; }
      var err = box.querySelector('.ed-err');
      if (err) { err.textContent = message; }
      box.classList.toggle('is-invalid', !!message);
    }

    function queueSave(target, field, value, o) {
      o = o || {};
      var path = target.path;
      var entry = queue[path] || (queue[path] = { path: path, target: target, patch: {}, timer: null, rerender: false });
      entry.patch[field] = value;
      entry.rerender = entry.rerender || !!o.rerender;
      clearTimeout(entry.timer);
      entry.timer = setTimeout(function () { flush(path); }, o.now ? 0 : 700);
      setSave('busy', 'Saving…');
    }

    function flush(path) {
      var entry = queue[path];
      if (!entry) { return Promise.resolve(); }
      delete queue[path];
      clearTimeout(entry.timer);
      inFlight += 1;
      return api(path, { body: entry.patch }).then(function (res) {
        inFlight -= 1;
        Object.keys(entry.patch).forEach(function (f) { fieldError(path, f, ''); });
        if (res.ok) {
          if (res.data.item) { Object.assign(entry.target.item, res.data.item); }
          if (opts.onSaved) { opts.onSaved(entry.target, res.data); }
          if (!Object.keys(queue).length && !inFlight) { setSave('ok', 'Saved'); }
          if (entry.rerender && opts.render) { opts.render(); }
        } else {
          var errors = res.data.errors || {};
          var show = function () {
            Object.keys(errors).forEach(function (f) { fieldError(path, f, errors[f].join(' ')); });
            setSave('error', res.data.error || (Object.keys(errors).length ? 'Not saved: see the message in red.' : 'Couldn’t save.'));
          };
          if (entry.rerender && opts.refresh) { return opts.refresh().then(show); }
          show();
        }
      });
    }

    function flushAll() { return Promise.all(Object.keys(queue).map(flush)); }

    // Structural change: save pending edits, call the API, then reload the page's data.
    function act(path, body, o) {
      o = o || {};
      if (o.confirm && !window.confirm(o.confirm)) { return Promise.resolve(null); }
      return flushAll().then(function () {
        setSave('busy', 'Saving…');
        return api(path, o.form ? { form: o.form } : { body: body || {} });
      }).then(function (res) {
        if (!res.ok) {
          setSave('error', res.data.error || (res.data.errors ? Object.values(res.data.errors)[0].join(' ') : 'Couldn’t save.'));
          return null;
        }
        if (res.data.redirect) { location.assign(res.data.redirect); return null; }
        return (opts.refresh ? opts.refresh() : Promise.resolve()).then(function () { setSave('ok', 'Saved'); return res.data; });
      });
    }

    window.addEventListener('beforeunload', function (e) {
      if (Object.keys(queue).length || inFlight) { e.preventDefault(); e.returnValue = ''; }
    });

    // ---- fields

    function wrap(path, field, labelText, control, hint) {
      return h('div', { class: 'ed-field', 'data-key': path + ':' + field },
        labelText ? h('label', { class: 'ed-label', for: control.id, text: labelText }) : null,
        control,
        hint ? h('p', { class: 'ed-hint', text: hint }) : null,
        h('p', { class: 'ed-err', role: 'alert' }));
    }

    function grow(el) { el.style.height = 'auto'; el.style.height = el.scrollHeight + 2 + 'px'; }

    // Text, number or textarea. o: label, rows, type, number, line, lineClass, placeholder, maxlength, hint, onInput, onChangeOnly, grow (default true for rows)
    function input(t, field, o) {
      o = o || {};
      var cls = o.line ? 'ed-line' + (o.lineClass ? ' ' + o.lineClass : '') : 'ed-input' + (o.inputClass ? ' ' + o.inputClass : '');
      var el = o.rows ? h('textarea', { class: cls, rows: o.rows })
                      : h('input', { class: cls, type: o.type || 'text', inputmode: o.number ? 'numeric' : null });
      el.id = nextId();
      el.value = t.item[field] === null || t.item[field] === undefined ? '' : t.item[field];
      if (o.line) { el.setAttribute('aria-label', o.label); el.placeholder = o.placeholder || o.label; }
      else if (o.placeholder) { el.placeholder = o.placeholder; }
      if (o.maxlength) { el.maxLength = o.maxlength; }
      el.disabled = !!t.locked;
      var autoGrow = o.rows && o.grow !== false;
      el.addEventListener(o.onChangeOnly ? 'change' : 'input', function () {
        var value = el.value;
        if (o.number) { value = value.trim() === '' ? null : Number(value); }
        t.item[field] = value;
        if (autoGrow) { grow(el); }
        if (o.onInput) { o.onInput(value); }
        queueSave(t, field, value, { now: !!o.onChangeOnly });
      });
      if (autoGrow) { requestAnimationFrame(function () { grow(el); }); }
      var box = wrap(t.path, field, o.line ? null : o.label, el, o.hint);
      box.control = el;
      return box;
    }

    function select(t, field, choices, o) {
      o = o || {};
      var el = h('select', { class: 'ed-input ed-select', 'aria-label': o.aria || null, disabled: !!t.locked });
      el.id = nextId();
      (o.empty ? [[o.emptyValue === undefined ? '' : o.emptyValue, o.empty]] : []).concat(choices).forEach(function (c) {
        el.appendChild(h('option', { value: String(c[0]), text: c[1], selected: String(t.item[field]) === String(c[0]) }));
      });
      el.addEventListener('change', function () {
        var value = o.toValue ? o.toValue(el.value) : el.value;
        t.item[field] = value;
        queueSave(t, field, value, { now: true, rerender: o.rerender });
      });
      return wrap(t.path, field, o.label, el, o.hint);
    }

    function toggle(t, field, text, o) {
      o = o || {};
      var el = h('input', { type: 'checkbox', class: 'ed-switch__input', checked: !!t.item[field], disabled: !!t.locked });
      el.id = nextId();
      el.addEventListener('change', function () {
        t.item[field] = el.checked;
        queueSave(t, field, el.checked, { now: true, rerender: o.rerender });
      });
      return h('div', { class: 'ed-field ed-field--inline', 'data-key': t.path + ':' + field },
        h('label', { class: 'ed-switch', for: el.id }, el, h('span', { class: 'ed-switch__track', 'aria-hidden': 'true' }), h('span', { text: text })),
        o.hint ? h('p', { class: 'ed-hint', text: o.hint }) : null,
        h('p', { class: 'ed-err', role: 'alert' }));
    }

    function segmented(t, field, choices, o) {
      o = o || {};
      var group = h('div', { class: 'ed-seg', role: 'group', 'aria-label': o.label });
      choices.forEach(function (c) {
        var btn = h('button', { type: 'button', class: 'ed-seg__btn', 'aria-pressed': String(t.item[field] === c[0]), text: c[1], disabled: !!t.locked });
        btn.addEventListener('click', function () {
          t.item[field] = c[0];
          group.querySelectorAll('.ed-seg__btn').forEach(function (b) { b.setAttribute('aria-pressed', String(b === btn)); });
          queueSave(t, field, c[0], { now: true, rerender: o.rerender });
        });
        group.appendChild(btn);
      });
      return h('div', { class: 'ed-field', 'data-key': t.path + ':' + field },
        o.label ? h('span', { class: 'ed-label', text: o.label }) : null, group,
        o.hint ? h('p', { class: 'ed-hint', text: o.hint }) : null,
        h('p', { class: 'ed-err', role: 'alert' }));
    }

    // Multi-select chips, optionally grouped: groups = [[groupName, [[value, label], ...]], ...]
    function chips(t, field, groups, o) {
      o = o || {};
      var selected = (t.item[field] || []).slice();
      var box = h('div', { class: 'ed-field st-chips', 'data-key': t.path + ':' + field },
        o.label ? h('span', { class: 'ed-label', text: o.label }) : null);
      groups.forEach(function (g) {
        var row = h('div', { class: 'st-chips__row' });
        g[1].forEach(function (c) {
          var on = selected.indexOf(c[0]) !== -1;
          var btn = h('button', { type: 'button', class: 'st-chip', 'aria-pressed': String(on), text: c[1], disabled: !!t.locked });
          btn.addEventListener('click', function () {
            var i = selected.indexOf(c[0]);
            if (i === -1) { selected.push(c[0]); } else { selected.splice(i, 1); }
            btn.setAttribute('aria-pressed', String(i === -1));
            t.item[field] = selected.slice();
            queueSave(t, field, selected.slice(), { now: false });
          });
          row.appendChild(btn);
        });
        box.appendChild(h('div', { class: 'st-chips__group' }, g[0] ? h('span', { class: 'st-chips__name', text: g[0] }) : null, row));
      });
      box.appendChild(h('p', { class: 'ed-err', role: 'alert' }));
      return box;
    }

    function button(text, onClick, o) {
      o = o || {};
      return h('button', { type: 'button', class: o.class || 'btn btn--ghost ed-btn', onclick: onClick, disabled: !!o.disabled,
                           title: o.title || null, 'aria-label': o.aria || null, text: text });
    }

    function iconButton(symbol, aria, onClick, disabled) {
      return h('button', { type: 'button', class: 'ed-icon', 'aria-label': aria, title: aria, onclick: onClick, disabled: !!disabled, text: symbol });
    }

    function note(text) { return h('p', { class: 'ed-note', text: text }); }

    // Image through the server (10 MB or less): POST <path>upload/<field>/
    function imageField(t, field, labelText, o) {
      o = o || {};
      var status = h('span', { class: 'ed-upload__status', role: 'status' });
      var file = h('input', { type: 'file', accept: 'image/*', class: 'ed-upload__file', disabled: !!t.locked });
      file.id = nextId();
      var preview = t.item[field]
        ? h('img', { class: 'ed-upload__img' + (o.wide ? ' st-img--wide' : ''), src: t.item[field], alt: '' })
        : h('span', { class: 'ed-upload__empty' + (o.wide ? ' st-img--wide' : ''), text: 'No image' });
      function send(form) {
        status.textContent = form.has('clear') ? 'Removing…' : 'Uploading…';
        setSave('busy', 'Uploading…');
        return api(t.path + 'upload/' + field + '/', { form: form }).then(function (res) {
          if (!res.ok) { status.textContent = res.data.error || 'Upload failed.'; setSave('error', 'Upload failed.'); return; }
          if (res.data.item) { Object.assign(t.item, res.data.item); }
          setSave('ok', 'Saved');
          if (opts.render) { opts.render(); }
        });
      }
      file.addEventListener('change', function () {
        var chosen = file.files && file.files[0];
        if (!chosen) { return; }
        if (chosen.size > (o.maxMb || 10) * 1024 * 1024) { status.textContent = 'Too big: images can be up to ' + (o.maxMb || 10) + ' MB.'; file.value = ''; return; }
        var form = new FormData();
        form.append('file', chosen);
        send(form);
      });
      var remove = t.item[field] && !t.locked ? button('Remove', function () {
        var form = new FormData();
        form.append('clear', '1');
        send(form);
      }, { class: 'ed-link' }) : null;
      return h('div', { class: 'ed-field ed-upload' },
        labelText ? h('span', { class: 'ed-label', text: labelText }) : null,
        h('div', { class: 'ed-upload__row' }, preview,
          h('div', { class: 'ed-upload__actions' },
            h('label', { class: 'btn btn--ghost ed-btn' + (t.locked ? ' is-disabled' : ''), for: file.id, text: t.item[field] ? 'Replace' : 'Upload image' }),
            file, remove, status)),
        o.hint ? h('p', { class: 'ed-hint', text: o.hint }) : null);
    }

    // ---- reordering

    function dragHandle(kind, locked) {
      return h('span', { class: 'ed-handle', 'aria-hidden': 'true', title: 'Drag to move', 'data-handle': kind,
                         draggable: locked ? null : 'true', text: '⠇⠇⠇' });
    }

    // onMove(newIds) is called with the list's ids in their new order.
    function arrows(ids, index, noun, onMove, locked) {
      function move(delta) {
        var next = ids.slice();
        var j = index + delta;
        var tmp = next[index]; next[index] = next[j]; next[j] = tmp;
        onMove(next);
      }
      return [
        iconButton('↑', 'Move ' + noun + ' up', function () { move(-1); }, locked || index === 0),
        iconButton('↓', 'Move ' + noun + ' down', function () { move(1); }, locked || index === ids.length - 1)
      ];
    }

    // Children marked data-drag="<kind>" data-id="<id>" can be dragged by their [data-handle="<kind>"].
    function enableDrag(list, kind, onDrop) {
      list.addEventListener('dragstart', function (e) {
        var handle = e.target.closest && e.target.closest('[data-handle="' + kind + '"]');
        var card = handle && handle.closest('[data-drag="' + kind + '"]');
        if (!card || dragging) { return; }
        dragging = { card: card, kind: kind, list: list, onDrop: onDrop };
        card.classList.add('is-dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', card.dataset.id);
        if (e.dataTransfer.setDragImage) { e.dataTransfer.setDragImage(card, 24, 24); }
      });
      list.addEventListener('dragover', function (e) {
        if (!dragging || dragging.kind !== kind || dragging.list !== list) { return; }
        e.preventDefault();
        var cards = Array.prototype.filter.call(list.children, function (c) { return c.dataset.drag === kind && c !== dragging.card; });
        var after = cards.filter(function (c) { var b = c.getBoundingClientRect(); return e.clientY < b.top + b.height / 2; })[0];
        if (after) { list.insertBefore(dragging.card, after); } else { list.appendChild(dragging.card); }
      });
      list.addEventListener('drop', function (e) { if (dragging) { e.preventDefault(); } });
    }

    document.addEventListener('dragend', function () {
      if (!dragging) { return; }
      var d = dragging;
      dragging = null;
      d.card.classList.remove('is-dragging');
      var ids = Array.prototype.filter.call(d.list.children, function (c) { return c.dataset.drag === d.kind; })
        .map(function (c) { return Number(c.dataset.id); });
      d.onDrop(ids);
    });

    return {
      h: h, clear: clear, api: api, setSave: setSave, queueSave: queueSave, flush: flush, flushAll: flushAll, act: act,
      input: input, select: select, toggle: toggle, segmented: segmented, chips: chips, imageField: imageField,
      button: button, iconButton: iconButton, note: note, wrap: wrap, grow: grow, fieldError: fieldError,
      dragHandle: dragHandle, arrows: arrows, enableDrag: enableDrag
    };
  }

  window.StudioKit = { create: create, h: h };
})();
