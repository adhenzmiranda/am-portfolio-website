/*
 * Survey editor (/<address>/edit/), for the researcher only.
 *
 * Google Forms-style: every field saves itself a moment after you stop typing
 * (survey/editor.py checks it with the same rules as the admin). Pages and
 * questions reorder by drag and drop (mouse) or the arrow buttons (anywhere).
 * Everything is built with DOM methods and textContent, never HTML strings.
 */
(function () {
  'use strict';

  var CFG = JSON.parse(document.getElementById('editor-config').textContent);
  var CH = CFG.choices;
  var ST = CFG.state;
  var main = document.getElementById('ed-main');
  var saveEl = document.getElementById('ed-save');
  var frame = document.getElementById('ed-frame');
  var WIDE = window.matchMedia('(min-width: 1200px)');
  var tab = readTab();
  var queue = {};          // pending field saves, keyed "model:id"
  var inFlight = 0;
  var uid = 0;
  var dragging = null;

  // ------------------------------------------------------------ small helpers

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
  function append(el, child) {
    if (child === null || child === undefined || child === false) { return; }
    if (Array.isArray(child)) { child.forEach(function (c) { append(el, c); }); return; }
    el.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  function label(list, value) {
    for (var i = 0; i < list.length; i++) { if (list[i][0] === value) { return list[i][1]; } }
    return value;
  }
  function nextId() { uid += 1; return 'ed-f' + uid; }
  function readTab() {
    try { return sessionStorage.getItem('survey-editor-tab') || 'pages'; } catch (e) { return 'pages'; }
  }
  function writeTab(value) {
    try { sessionStorage.setItem('survey-editor-tab', value); } catch (e) { /* private mode */ }
  }

  // ------------------------------------------------------------ server

  function api(path, options) {
    options = options || {};
    var init = { method: options.method || 'POST', credentials: 'same-origin', headers: { 'X-CSRFToken': CFG.csrfToken } };
    if (options.form) {
      init.body = options.form;
    } else if (init.method !== 'GET') {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(options.body || {});
    }
    return fetch(ST.links.api + path, init).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    }).catch(function () {
      return { ok: false, status: 0, data: { error: 'Could not reach the server. Check your connection.' } };
    });
  }

  function setSave(state, text) {
    saveEl.dataset.state = state;
    saveEl.textContent = text;
  }

  function isLocked(model, field) {
    return ST.locked && (model !== 'survey' || CH.lockedFields.indexOf(field) !== -1);
  }

  // Field saves are merged per item and sent 0.7 s after the last keystroke.
  function queueSave(model, id, field, value, options) {
    options = options || {};
    var key = model + ':' + id;
    var entry = queue[key] || (queue[key] = { model: model, id: id, patch: {}, timer: null, rerender: false });
    entry.patch[field] = value;
    entry.rerender = entry.rerender || !!options.rerender;
    clearTimeout(entry.timer);
    entry.timer = setTimeout(function () { flush(key); }, options.now ? 0 : 700);
    setSave('busy', 'Saving…');
  }

  function flush(key) {
    var entry = queue[key];
    if (!entry) { return Promise.resolve(); }
    delete queue[key];
    clearTimeout(entry.timer);
    inFlight += 1;
    return api(entry.model + '/' + entry.id + '/', { body: entry.patch }).then(function (res) {
      inFlight -= 1;
      Object.keys(entry.patch).forEach(function (f) { fieldError(entry.model, entry.id, f, ''); });
      if (res.ok) {
        applySaved(res.data, entry.model);
        if (res.data.redirect) { location.replace(res.data.redirect); return; }
        if (entry.rerender) { render(); }
        if (!Object.keys(queue).length && !inFlight) { setSave('ok', 'Saved'); }
        reloadPreviewSoon();
      } else {
        var errors = res.data.errors || {};
        var show = function () {
          Object.keys(errors).forEach(function (f) { fieldError(entry.model, entry.id, f, errors[f].join(' ')); });
          setSave('error', res.data.error || (Object.keys(errors).length ? 'Not saved: see the message in red.' : 'Couldn’t save.'));
        };
        // Buttons and dropdowns already show the new choice: put back what the server has.
        if (entry.rerender) { return refresh().then(show); }
        show();
      }
    });
  }

  function flushAll() {
    return Promise.all(Object.keys(queue).map(flush));
  }

  function applySaved(data, model) {
    ST.problems = data.problems;
    ST.locked = data.locked;
    if (data.status) { ST.survey.status = data.status; }
    if (data.item) { replaceItem(model, data.item); }
    updateHeader();
    var box = document.getElementById('ed-checklist');
    if (box) { box.replaceWith(checklist()); }
    // An earlier "not ready to open" message is out of date once the checklist changes.
    if (!(model === 'survey' && data.item && data.item.status === 'open')) { fieldError('survey', ST.survey.id, 'status', ''); }
  }

  function replaceItem(model, item) {
    if (model === 'survey') { ST.survey = item; return; }
    var lists = model === 'question'
      ? ST.sections.map(function (s) { return s.questions; })
      : [model === 'section' ? ST.sections : model === 'prompt' ? ST.prompts : ST.conditions];
    lists.forEach(function (list) {
      for (var i = 0; i < list.length; i++) {
        if (list[i].id === item.id) {
          if (model === 'section') { item.questions = list[i].questions; }
          list[i] = item;
        }
      }
    });
  }

  // Structural changes (add, delete, move): save pending edits, act, then redraw from the server.
  function act(path, body, options) {
    options = options || {};
    if (options.confirm && !window.confirm(options.confirm)) { return Promise.resolve(null); }
    return flushAll().then(function () {
      setSave('busy', 'Saving…');
      return api(path, { body: body || {} });
    }).then(function (res) {
      if (!res.ok) { setSave('error', res.data.error || 'Couldn’t save.'); return null; }
      if (res.data.redirect) { location.replace(res.data.redirect); return null; }
      return refresh().then(function () {
        setSave('ok', 'Saved');
        reloadPreviewSoon();
        return res.data;
      });
    });
  }

  function refresh() {
    return api('state/', { method: 'GET' }).then(function (res) {
      if (res.ok) { ST = res.data; render(); }
      else { setSave('error', res.data.error || 'Couldn’t load the latest version.'); }
    });
  }

  function focusNew(selector) {
    var el = main.querySelector(selector);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      var input = el.querySelector('input, textarea');
      if (input) { input.focus({ preventScroll: true }); input.select && input.select(); }
    }
  }

  // ------------------------------------------------------------ form controls

  function wrap(model, id, field, labelText, control, hint) {
    return h('div', { class: 'ed-field', 'data-key': model + ':' + id + ':' + field },
      labelText ? h('label', { class: 'ed-label', for: control.id, text: labelText }) : null,
      control,
      hint ? h('p', { class: 'ed-hint', text: hint }) : null,
      h('p', { class: 'ed-err', role: 'alert' }));
  }

  function fieldError(model, id, field, message) {
    var box = main.querySelector('[data-key="' + model + ':' + id + ':' + field + '"]');
    if (!box) { return; }
    box.querySelector('.ed-err').textContent = message;
    box.classList.toggle('is-invalid', !!message);
  }

  function grow(el) {
    el.style.height = 'auto';
    el.style.height = el.scrollHeight + 2 + 'px';
  }

  // Text, number or multi-line field that saves itself.
  function input(model, item, field, opts) {
    opts = opts || {};
    var el = opts.rows
      ? h('textarea', { class: 'ed-input', rows: opts.rows })
      : h('input', { class: 'ed-input' + (opts.big ? ' ed-input--big' : ''), type: opts.type || 'text',
                     inputmode: opts.number ? 'numeric' : null });
    el.id = nextId();
    el.value = item[field] === null || item[field] === undefined ? '' : item[field];
    if (opts.placeholder) { el.placeholder = opts.placeholder; }
    if (opts.maxlength) { el.maxLength = opts.maxlength; }
    el.disabled = isLocked(model, field);
    el.addEventListener(opts.onChangeOnly ? 'change' : 'input', function () {
      var value = el.value;
      if (opts.number) { value = value.trim() === '' ? null : Number(value); }
      item[field] = value;
      if (opts.rows) { grow(el); }
      if (opts.onInput) { opts.onInput(value); }
      queueSave(model, item.id, field, value, { now: !!opts.onChangeOnly });
    });
    if (opts.rows) { requestAnimationFrame(function () { grow(el); }); }
    return wrap(model, item.id, field, opts.label, el, opts.hint);
  }

  function select(model, item, field, choices, opts) {
    opts = opts || {};
    var el = h('select', { class: 'ed-input ed-select' });
    el.id = nextId();
    choices.forEach(function (c) { el.appendChild(h('option', { value: c[0], text: c[1], selected: item[field] === c[0] })); });
    el.disabled = isLocked(model, field);
    el.addEventListener('change', function () {
      item[field] = el.value;
      queueSave(model, item.id, field, el.value, { now: true, rerender: opts.rerender });
    });
    return wrap(model, item.id, field, opts.label, el, opts.hint);
  }

  function toggle(model, item, field, text, opts) {
    opts = opts || {};
    var el = h('input', { type: 'checkbox', class: 'ed-switch__input', checked: !!item[field] });
    el.id = nextId();
    el.disabled = isLocked(model, field);
    el.addEventListener('change', function () {
      item[field] = el.checked;
      queueSave(model, item.id, field, el.checked, { now: true, rerender: opts.rerender });
    });
    return h('div', { class: 'ed-field ed-field--inline', 'data-key': model + ':' + item.id + ':' + field },
      h('label', { class: 'ed-switch', for: el.id }, el, h('span', { class: 'ed-switch__track', 'aria-hidden': 'true' }), h('span', { text: text })),
      h('p', { class: 'ed-err', role: 'alert' }));
  }

  // Two or three buttons, one active (e.g. Safe / Risky, Draft / Open / Closed).
  function segmented(model, item, field, choices, opts) {
    opts = opts || {};
    var group = h('div', { class: 'ed-seg', role: 'group', 'aria-label': opts.label });
    choices.forEach(function (c) {
      var btn = h('button', { type: 'button', class: 'ed-seg__btn', 'aria-pressed': String(item[field] === c[0]), text: c[1],
                              disabled: isLocked(model, field) });
      btn.addEventListener('click', function () {
        item[field] = c[0];
        group.querySelectorAll('.ed-seg__btn').forEach(function (b) { b.setAttribute('aria-pressed', String(b === btn)); });
        queueSave(model, item.id, field, c[0], { now: true, rerender: opts.rerender });
      });
      group.appendChild(btn);
    });
    return h('div', { class: 'ed-field', 'data-key': model + ':' + item.id + ':' + field },
      opts.label ? h('span', { class: 'ed-label', text: opts.label }) : null, group,
      opts.hint ? h('p', { class: 'ed-hint', text: opts.hint }) : null,
      h('p', { class: 'ed-err', role: 'alert' }));
  }

  function button(text, onClick, opts) {
    opts = opts || {};
    return h('button', { type: 'button', class: opts.class || 'btn btn--ghost ed-btn', onclick: onClick,
                         disabled: !!opts.disabled, title: opts.title || null, 'aria-label': opts.aria || null, text: text });
  }

  function iconButton(symbol, aria, onClick, disabled) {
    return h('button', { type: 'button', class: 'ed-icon', 'aria-label': aria, title: aria, onclick: onClick,
                         disabled: !!disabled, text: symbol });
  }

  function note(text) { return h('p', { class: 'ed-note', text: text }); }

  // ------------------------------------------------------------ uploads

  function imageField(model, item, field, labelText, hint) {
    var locked = isLocked(model, field) || (ST.locked && model !== 'survey');
    var status = h('span', { class: 'ed-upload__status', role: 'status' });
    var file = h('input', { type: 'file', accept: 'image/*', class: 'ed-upload__file', disabled: locked });
    file.id = nextId();
    var preview = item[field]
      ? h('img', { class: 'ed-upload__img', src: item[field], alt: '' })
      : h('span', { class: 'ed-upload__empty', text: 'No image' });
    file.addEventListener('change', function () {
      var chosen = file.files && file.files[0];
      if (!chosen) { return; }
      if (chosen.size > CH.maxImageMb * 1024 * 1024) {
        status.textContent = 'Too big: images can be up to ' + CH.maxImageMb + ' MB.';
        file.value = '';
        return;
      }
      var form = new FormData();
      form.append('file', chosen);
      status.textContent = 'Uploading…';
      setSave('busy', 'Uploading…');
      api(model + '/' + item.id + '/upload/' + field + '/', { form: form }).then(function (res) {
        if (!res.ok) { status.textContent = res.data.error || 'Upload failed.'; setSave('error', 'Upload failed.'); return; }
        applySaved(res.data, model);
        setSave('ok', 'Saved');
        render();
        reloadPreviewSoon();
      });
    });
    var remove = item[field] && !locked ? button('Remove', function () {
      var form = new FormData();
      form.append('clear', '1');
      api(model + '/' + item.id + '/upload/' + field + '/', { form: form }).then(function (res) {
        if (res.ok) { applySaved(res.data, model); render(); reloadPreviewSoon(); }
      });
    }, { class: 'ed-link' }) : null;
    return h('div', { class: 'ed-field ed-upload' },
      h('span', { class: 'ed-label', text: labelText }),
      h('div', { class: 'ed-upload__row' }, preview,
        h('div', { class: 'ed-upload__actions' },
          h('label', { class: 'btn btn--ghost ed-btn' + (locked ? ' is-disabled' : ''), for: file.id, text: item[field] ? 'Replace' : 'Upload image' }),
          file, remove, status)),
      hint ? h('p', { class: 'ed-hint', text: hint }) : null);
  }

  // Reels go straight from the browser to Cloudinary (signed by the server), so Heroku's
  // 30 second limit never applies. Same reference format as the admin's uploader.
  function videoField(item) {
    var locked = ST.locked;
    var status = h('span', { class: 'ed-upload__status', role: 'status' });
    var bar = h('progress', { class: 'ed-upload__bar', max: '100', value: '0', hidden: true });
    var file = h('input', { type: 'file', accept: 'video/*', class: 'ed-upload__file', disabled: locked });
    file.id = nextId();
    var preview = item.video
      ? h('video', { class: 'ed-upload__video', src: item.video, controls: true, muted: true, playsinline: true, preload: 'metadata' })
      : h('span', { class: 'ed-upload__empty', text: 'No video yet' });
    file.addEventListener('change', function () {
      var chosen = file.files && file.files[0];
      if (!chosen) { return; }
      var mb = chosen.size / (1024 * 1024);
      if (mb > 100) {
        status.textContent = 'This video is ' + mb.toFixed(0) + ' MB. Cloudinary’s free plan allows up to 100 MB: compress it first (e.g. with HandBrake).';
        file.value = '';
        return;
      }
      status.textContent = 'Preparing upload…';
      setSave('busy', 'Uploading video…');
      api('sign-video/', { body: {} }).then(function (res) {
        if (!res.ok) { throw new Error(res.data.error || 'Could not start the upload.'); }
        return new Promise(function (resolve, reject) {
          var sig = res.data;
          var body = new FormData();
          Object.keys(sig.params).forEach(function (k) { body.append(k, sig.params[k]); });
          body.append('api_key', sig.api_key);
          body.append('file', chosen);
          var xhr = new XMLHttpRequest();
          xhr.open('POST', sig.upload_url);
          xhr.upload.addEventListener('progress', function (e) {
            if (!e.lengthComputable) { return; }
            var pct = Math.round(e.loaded / e.total * 100);
            bar.hidden = false;
            bar.value = pct;
            status.textContent = 'Uploading to Cloudinary… ' + pct + '%';
          });
          xhr.addEventListener('load', function () {
            var data = {};
            try { data = JSON.parse(xhr.responseText); } catch (e) { /* handled below */ }
            if (xhr.status >= 200 && xhr.status < 300 && data.public_id) { resolve(data); }
            else { reject(new Error((data.error && data.error.message) || 'Cloudinary refused the upload.')); }
          });
          xhr.addEventListener('error', function () { reject(new Error('Network error while uploading.')); });
          xhr.send(body);
        });
      }).then(function (result) {
        var ref = result.resource_type + '/' + result.type + '/v' + result.version + '/' + result.public_id + '.' + result.format + '#' + result.signature;
        return api('condition/' + item.id + '/', { body: { video: ref } });
      }).then(function (res) {
        if (!res.ok) { throw new Error(res.data.error || 'The upload could not be saved.'); }
        applySaved(res.data, 'condition');
        setSave('ok', 'Saved');
        render();
        reloadPreviewSoon();
      }).catch(function (err) {
        bar.hidden = true;
        file.value = '';
        status.textContent = err.message;
        setSave('error', 'Upload failed.');
      });
    });
    return h('div', { class: 'ed-field ed-upload' },
      h('span', { class: 'ed-label', text: 'Video' }),
      h('div', { class: 'ed-upload__row' }, preview,
        h('div', { class: 'ed-upload__actions' },
          h('label', { class: 'btn btn--ghost ed-btn' + (locked ? ' is-disabled' : ''), for: file.id, text: item.video ? 'Replace video' : 'Upload video' }),
          file, bar, status)),
      h('p', { class: 'ed-hint', text: 'Vertical (9:16) mp4 with burned-in captions, up to 100 MB. Most people watch with the sound off.' }));
  }

  // ------------------------------------------------------------ reordering

  function moveTools(kind, list, index, sectionId) {
    var ids = list.map(function (x) { return x.id; });
    function move(delta) {
      var j = index + delta;
      var t = ids[index]; ids[index] = ids[j]; ids[j] = t;
      act('reorder/', kind === 'section' ? { kind: 'section', ids: ids } : { kind: 'question', section: sectionId, ids: ids });
    }
    return [
      h('span', { class: 'ed-drag', 'aria-hidden': 'true', title: 'Drag to move', text: '⠇⠇', 'data-handle': kind,
                  draggable: ST.locked ? null : 'true' }),
      iconButton('↑', 'Move up', function () { move(-1); }, ST.locked || index === 0),
      iconButton('↓', 'Move down', function () { move(1); }, ST.locked || index === list.length - 1)
    ];
  }

  // Mouse drag and drop. Only the handle is draggable (it carries its card along),
  // so text in the fields can still be selected normally.
  function enableDrag(list, kind) {
    if (ST.locked) { return; }
    list.addEventListener('dragstart', function (e) {
      var handle = e.target.closest && e.target.closest('[data-handle="' + kind + '"]');
      var card = handle && handle.closest('[data-drag="' + kind + '"]');
      if (!card || dragging) { return; }
      dragging = { card: card, kind: kind };
      card.classList.add('is-dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', card.dataset.id);
      if (e.dataTransfer.setDragImage) { e.dataTransfer.setDragImage(card, 24, 24); }
    });
    list.addEventListener('dragover', function (e) {
      if (!dragging || dragging.kind !== kind) { return; }
      e.preventDefault();
      var cards = Array.prototype.filter.call(list.children, function (c) {
        return c.dataset.drag === kind && c !== dragging.card;
      });
      var after = cards.filter(function (c) {
        var box = c.getBoundingClientRect();
        return e.clientY < box.top + box.height / 2;
      })[0];
      if (after) { list.insertBefore(dragging.card, after); } else { list.appendChild(dragging.card); }
    });
    list.addEventListener('drop', function (e) { if (dragging) { e.preventDefault(); } });
  }

  document.addEventListener('dragend', function () {
    if (!dragging) { return; }
    var card = dragging.card;
    var kind = dragging.kind;
    dragging = null;
    card.classList.remove('is-dragging');
    var list = card.parentElement;
    var ids = Array.prototype.filter.call(list.children, function (c) { return c.dataset.drag === kind; })
      .map(function (c) { return Number(c.dataset.id); });
    act('reorder/', kind === 'section' ? { kind: 'section', ids: ids }
                                       : { kind: 'question', section: Number(list.dataset.section), ids: ids });
  });

  // ------------------------------------------------------------ Pages tab

  function pagesTab() {
    var n = ST.sections.length;
    var list = h('div', { class: 'ed-list' });
    ST.sections.forEach(function (s, i) { list.appendChild(sectionCard(s, i, n)); });
    enableDrag(list, 'section');
    var kinds = ST.sections.map(function (s) { return s.kind; });
    var addKind = h('select', { class: 'ed-input ed-select', 'aria-label': 'Type of page to add', disabled: ST.locked });
    CH.sectionKinds.forEach(function (c) {
      var once = c[0] === 'task_before' || c[0] === 'media' || c[0] === 'task_after';
      addKind.appendChild(h('option', { value: c[0], text: c[1] + (once && kinds.indexOf(c[0]) !== -1 ? ' (already added)' : ''),
                                        disabled: once && kinds.indexOf(c[0]) !== -1 }));
    });
    return [
      h('section', { class: 'ed-card ed-card--fixed' },
        h('span', { class: 'ed-kicker', text: 'Start' }),
        h('h2', { class: 'ed-card__title', text: 'Consent page' }),
        note('Information, contacts and tick boxes. Every participant sees it first.'),
        button('Edit in Settings', function () { switchTab('settings'); })),
      list,
      h('div', { class: 'ed-add' }, addKind,
        button('+ Add page', function () {
          act('section/new/', { kind: addKind.value }).then(function (data) {
            if (data && data.item) { focusNew('[data-drag="section"][data-id="' + data.item.id + '"]'); }
          });
        }, { class: 'btn btn--primary ed-btn', disabled: ST.locked })),
      h('section', { class: 'ed-card ed-card--fixed' },
        h('span', { class: 'ed-kicker', text: 'End' }),
        h('h2', { class: 'ed-card__title', text: 'Thank-you page' }),
        note('Shown after submitting, with your logo, share buttons and the site’s navbar and footer.'),
        button('Edit in Settings', function () { switchTab('settings'); }))
    ];
  }

  function sectionCard(s, i, n) {
    var card = h('section', { class: 'ed-card ed-section', 'data-drag': 'section', 'data-id': s.id },
      h('div', { class: 'ed-card__head' },
        h('div', { class: 'ed-card__meta' },
          h('span', { class: 'ed-kicker', text: 'Page ' + (i + 1) + ' of ' + n }),
          h('span', { class: 'ed-chip', text: label(CH.sectionKinds, s.kind) })),
        h('div', { class: 'ed-tools' }, moveTools('section', ST.sections, i),
          iconButton('✕', 'Delete page', function () {
            act('section/' + s.id + '/delete/', {}, { confirm: 'Delete the page "' + s.title + '"' +
              (s.questions.length ? ' and its ' + s.questions.length + ' question(s)' : '') + '?' });
          }, ST.locked))),
      input('section', s, 'title', { label: 'Page title', big: true, maxlength: 200 }),
      input('section', s, 'description', { label: 'Description (optional)', rows: 2,
        hint: 'Shown under the title. Markdown works: **bold**, - bullet points.' }),
      input('section', s, 'button_label', { label: 'Button text', maxlength: 60,
        placeholder: i === n - 1 ? 'Submit answers' : 'Next' }));

    if (s.kind === 'questions') {
      var qlist = h('div', { class: 'ed-questions', 'data-section': s.id });
      s.questions.forEach(function (q, j) { qlist.appendChild(questionCard(q, j, s)); });
      enableDrag(qlist, 'question');
      card.appendChild(qlist);
      card.appendChild(h('div', { class: 'ed-add' }, button('+ Add question', function () {
        act('question/new/', { section: s.id, kind: 'choice' }).then(function (data) {
          if (data && data.item) { focusNew('[data-drag="question"][data-id="' + data.item.id + '"]'); }
        });
      }, { class: 'btn btn--primary ed-btn', disabled: ST.locked })));
    } else if (s.kind === 'task_before' || s.kind === 'task_after') {
      card.appendChild(h('div', { class: 'ed-info' },
        note('Shows all ' + ST.prompts.length + ' prompts in a new random order for each person' +
             (s.kind === 'task_after' ? ' (a different order from the first round).' : '.')),
        button('Edit prompts', function () { switchTab('prompts'); })));
    } else if (s.kind === 'media') {
      var active = ST.conditions.filter(function (c) { return c.active; }).length;
      card.appendChild(h('div', { class: 'ed-info' },
        note('Each person sees one of the ' + active + ' active media groups, picked so the groups stay even. Back is turned off from here on.'),
        button('Edit media', function () { switchTab('media'); })));
    }
    return card;
  }

  function questionCard(q, j, section) {
    var optionKinds = CH.optionKinds;
    var others = ST.sections.filter(function (s) { return s.kind === 'questions'; });
    var move = h('select', { class: 'ed-input ed-select', disabled: ST.locked });
    move.id = nextId();
    others.forEach(function (s, idx) {
      move.appendChild(h('option', { value: String(s.id), text: 'Page ' + (ST.sections.indexOf(s) + 1) + ': ' + s.title,
                                     selected: s.id === section.id }));
    });
    move.addEventListener('change', function () {
      var target = others.filter(function (s) { return String(s.id) === move.value; })[0];
      var ids = target.questions.map(function (x) { return x.id; }).concat([q.id]);
      act('reorder/', { kind: 'question', section: target.id, ids: ids });
    });

    var details = h('details', { class: 'ed-more' }, h('summary', { text: 'More settings' }),
      input('question', q, 'code', { label: 'Column name in the CSV', maxlength: 40,
        hint: 'Letters, numbers, - and _ only. Unique in this survey.' }),
      q.kind === 'scale' ? input('question', q, 'construct', { label: 'Construct (hidden)', maxlength: 40,
        hint: 'Groups scale questions for analysis, e.g. engagement. The CSV gets a mean per construct.' }) : null,
      input('question', q, 'attention_answer', { label: 'Attention check answer', maxlength: 200,
        hint: 'Only for attention checks: the answer a careful reader gives. The CSV marks pass or fail.' }),
      wrap('question', q.id, 'section', 'Move to page', move));

    return h('article', { class: 'ed-q', 'data-drag': 'question', 'data-id': q.id },
      h('div', { class: 'ed-card__head' },
        h('span', { class: 'ed-kicker', text: 'Question ' + (j + 1) }),
        h('div', { class: 'ed-tools' }, moveTools('question', section.questions, j, section.id),
          iconButton('⧉', 'Duplicate question', function () {
            act('question/' + q.id + '/duplicate/', {});
          }, ST.locked),
          iconButton('✕', 'Delete question', function () {
            act('question/' + q.id + '/delete/', {}, { confirm: 'Delete the question "' + q.text + '"?' });
          }, ST.locked))),
      h('div', { class: 'ed-q__row' },
        input('question', q, 'text', { label: 'Question', maxlength: 300 }),
        select('question', q, 'kind', CH.questionKinds, { label: 'Type', rerender: true })),
      input('question', q, 'help_text', { label: 'Help text (optional)', maxlength: 300 }),
      optionKinds.indexOf(q.kind) !== -1 ? optionsEditor(q) : null,
      q.kind === 'number' ? h('div', { class: 'ed-grid3' },
        input('question', q, 'min_value', { label: 'Lowest allowed', type: 'number', number: true }),
        input('question', q, 'max_value', { label: 'Highest allowed', type: 'number', number: true }),
        input('question', q, 'range_message', { label: 'Message if out of range', maxlength: 200 })) : null,
      q.kind === 'scale' ? h('div', { class: 'ed-grid2' },
        input('question', q, 'scale_low_label', { label: 'Label for 1', maxlength: 60 }),
        input('question', q, 'scale_high_label', { label: 'Label for 5', maxlength: 60 })) : null,
      h('div', { class: 'ed-q__foot' }, toggle('question', q, 'required', 'Required')),
      details);
  }

  // One input per option, like Google Forms. Saved as one option per line.
  function optionsEditor(q) {
    var lines = (q.options || '').split('\n');
    if (!lines.length) { lines = ['']; }
    var box = h('div', { class: 'ed-field ed-options', 'data-key': 'question:' + q.id + ':options' });
    var locked = isLocked('question', 'options');
    function save() {
      q.options = lines.join('\n');
      queueSave('question', q.id, 'options', q.options);
    }
    function draw(focusIndex) {
      while (box.firstChild) { box.removeChild(box.firstChild); }
      box.appendChild(h('span', { class: 'ed-label', text: 'Options' }));
      lines.forEach(function (text, i) {
        var el = h('input', { class: 'ed-input', type: 'text', value: text, 'aria-label': 'Option ' + (i + 1), disabled: locked });
        el.addEventListener('input', function () { lines[i] = el.value; save(); });
        el.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') { e.preventDefault(); lines.splice(i + 1, 0, ''); save(); draw(i + 1); }
        });
        box.appendChild(h('div', { class: 'ed-option' },
          h('span', { class: 'ed-option__mark', 'aria-hidden': 'true', text: q.kind === 'checkboxes' ? '☐' : q.kind === 'dropdown' ? (i + 1) + '.' : '○' }),
          el,
          iconButton('✕', 'Remove option ' + (i + 1), function () {
            lines.splice(i, 1);
            if (!lines.length) { lines.push(''); }
            save();
            draw();
          }, locked || lines.length === 1)));
        if (focusIndex === i) { requestAnimationFrame(function () { el.focus(); }); }
      });
      box.appendChild(button('+ Add option', function () {
        lines.push('Option ' + (lines.length + 1));
        save();
        draw(lines.length - 1);
      }, { class: 'ed-link', disabled: locked }));
      box.appendChild(h('p', { class: 'ed-err', role: 'alert' }));
    }
    draw();
    return box;
  }

  // ------------------------------------------------------------ Prompts tab

  function promptsTab() {
    var mocks = CH.mocks;
    return [
      h('section', { class: 'ed-card ed-card--fixed' },
        h('h2', { class: 'ed-card__title', text: '"Would you send this?" prompts' }),
        note('Shown before and after the media, in a new random order each time. The answer key decides the score: ' +
             'for a risky prompt, "Change it first" or "Wouldn’t send" is correct; for a safe prompt, "Send as is" is correct. ' +
             'Prompts with the same pair letter are never shown next to each other.')),
      ST.prompts.map(function (p) {
        return h('section', { class: 'ed-card', 'data-prompt': p.id },
          h('div', { class: 'ed-card__head' },
            h('span', { class: 'ed-kicker', text: 'Prompt ' + p.number }),
            h('div', { class: 'ed-tools' }, iconButton('✕', 'Delete prompt', function () {
              act('prompt/' + p.id + '/delete/', {}, { confirm: 'Delete prompt ' + p.number + '?' });
            }, ST.locked))),
          h('div', { class: 'ed-grid3' },
            input('prompt', p, 'number', { label: 'Number', type: 'number', number: true,
              hint: 'Matches your dissertation tables and CSV columns.' }),
            segmented('prompt', p, 'risky', [[false, 'Safe'], [true, 'Risky']], { label: 'Answer key' }),
            input('prompt', p, 'pair_group', { label: 'Pair letter', maxlength: 20, placeholder: 'e.g. A' })),
          input('prompt', p, 'text', { label: 'Message', rows: 2 }),
          h('div', { class: 'ed-grid2' },
            imageField('prompt', p, 'screenshot', 'Attached screenshot', 'Use fictional details.'),
            select('prompt', p, 'builtin_mock', mocks, { label: 'Built-in screenshot',
              hint: 'Used when no screenshot is uploaded.' })),
          h('details', { class: 'ed-more', open: !!(p.context_image || p.context_mock) },
            h('summary', { text: 'Context above the message (optional)' }),
            input('prompt', p, 'context_label', { label: 'Label', maxlength: 120 }),
            h('div', { class: 'ed-grid2' },
              imageField('prompt', p, 'context_image', 'Context image'),
              select('prompt', p, 'context_mock', mocks, { label: 'Built-in context' }))));
      }),
      h('div', { class: 'ed-add' }, button('+ Add prompt', function () {
        act('prompt/new/', {}).then(function (data) {
          if (data && data.item) { focusNew('[data-prompt="' + data.item.id + '"]'); }
        });
      }, { class: 'btn btn--primary ed-btn', disabled: ST.locked }))
    ];
  }

  // ------------------------------------------------------------ Media tab

  function mediaTab() {
    return [
      h('section', { class: 'ed-card ed-card--fixed' },
        h('h2', { class: 'ed-card__title', text: 'Random media groups' }),
        note('Each person sees one active group, assigned so the groups stay even. Give every group the same script, ' +
             'so the format is the only difference.')),
      ST.conditions.map(function (c) {
        var media = c.kind === 'video'
          ? [videoField(c), imageField('condition', c, 'image', 'Still image while it loads (optional)')]
          : c.kind === 'image'
            ? [imageField('condition', c, 'image', 'Image', 'e.g. the infographic, 1080 x 1350.'),
               input('condition', c, 'alt_text', { label: 'Image description for screen readers', rows: 3,
                 hint: 'Usually the full script.' })]
            : [input('condition', c, 'text_body', { label: 'Post text', rows: 8,
                 hint: 'A blank line starts a new paragraph.' })];
        return h('section', { class: 'ed-card', 'data-condition': c.id },
          h('div', { class: 'ed-card__head' },
            h('div', { class: 'ed-card__meta' },
              h('span', { class: 'ed-kicker', text: c.responses + ' response' + (c.responses === 1 ? '' : 's') }),
              h('span', { class: 'ed-chip' + (c.active ? '' : ' is-off'), text: c.active ? 'Active' : 'Off' })),
            h('div', { class: 'ed-tools' }, iconButton('✕', 'Delete media group', function () {
              act('condition/' + c.id + '/delete/', {}, { confirm: 'Delete the media group "' + c.name + '"?' });
            }, ST.locked || c.responses > 0))),
          h('div', { class: 'ed-grid3' },
            input('condition', c, 'name', { label: 'Name', maxlength: 60 }),
            input('condition', c, 'key', { label: 'Id in the CSV', maxlength: 20 }),
            select('condition', c, 'kind', CH.conditionKinds, { label: 'Type', rerender: true })),
          toggle('condition', c, 'active', 'Active (people can be assigned to this group)', { rerender: true }),
          media,
          input('condition', c, 'caption', { label: 'Caption under the post (optional)', rows: 2 }));
      }),
      h('div', { class: 'ed-add' }, button('+ Add media group', function () {
        act('condition/new/', { kind: 'image' }).then(function (data) {
          if (data && data.item) { focusNew('[data-condition="' + data.item.id + '"]'); }
        });
      }, { class: 'btn btn--primary ed-btn', disabled: ST.locked }))
    ];
  }

  // ------------------------------------------------------------ Results tab

  function resultsTab() {
    var p = ST.progress;
    var tag = h('input', { class: 'ed-input', type: 'text', placeholder: 'optional tag, e.g. rak-poster', maxlength: 60 });
    tag.id = nextId();
    function qr(format) {
      var value = tag.value.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '');
      return ST.links.qr + '?format=' + format + (value ? '&src=' + encodeURIComponent(value) : '');
    }
    var png = h('a', { class: 'btn btn--ghost ed-btn', href: qr('png'), text: 'Download QR (PNG)' });
    var svg = h('a', { class: 'btn btn--ghost ed-btn', href: qr('svg'), text: 'SVG' });
    tag.addEventListener('input', function () { png.href = qr('png'); svg.href = qr('svg'); });
    var copied = h('span', { class: 'ed-upload__status', role: 'status' });

    var table = h('table', { class: 'ed-table' },
      h('thead', {}, h('tr', {}, h('th', { text: 'Group' }), h('th', { text: 'Completed' }),
        h('th', { text: 'In progress' }), h('th', { text: 'Dropped out' }))),
      h('tbody', {}, p.groups.length ? p.groups.map(function (g) {
        return h('tr', {}, h('td', { text: g.name }), h('td', { text: g.completed }), h('td', { text: g.active }), h('td', { text: g.dropped }));
      }) : h('tr', {}, h('td', { colspan: '4', text: 'No responses yet.' }))));

    return [
      h('section', { class: 'ed-card' },
        h('span', { class: 'ed-kicker', text: 'Batch "' + p.batch + '"' }),
        h('p', { class: 'ed-big' }, h('strong', { text: p.completed }), ' of ' + p.target + ' completed'),
        h('div', { class: 'ed-progress', role: 'progressbar', 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': String(p.percent) },
          h('span', { style: 'width:' + Math.min(100, p.percent) + '%' })),
        table,
        h('div', { class: 'ed-add' }, button('Refresh', function () { refresh(); }))),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Download responses' }),
        note('One row per person: answers, scores, construct means and timing. Opens in Google Sheets (File > Import) or Python.'),
        h('div', { class: 'ed-add' },
          h('a', { class: 'btn btn--primary ed-btn', href: ST.links.export + '?completed=1', text: 'CSV: completed only' }),
          h('a', { class: 'btn btn--ghost ed-btn', href: ST.links.export, text: 'CSV: everyone, including drop-outs' }))),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Share the survey' }),
        h('p', { class: 'ed-link-line' }, h('a', { href: ST.links.public, target: '_blank', rel: 'noopener', text: ST.links.public })),
        h('div', { class: 'ed-add' }, button('Copy link', function () {
          (navigator.clipboard ? navigator.clipboard.writeText(ST.links.public) : Promise.reject())
            .then(function () { copied.textContent = 'Copied.'; }, function () { copied.textContent = ST.links.public; });
        }), copied),
        wrap('qr', 0, 'src', 'QR code tag', tag, 'A tag adds ?src=tag to the link, so the CSV’s source column shows where each person came from.'),
        h('div', { class: 'ed-add' }, png, svg))
    ];
  }

  // ------------------------------------------------------------ Settings tab

  function checklist() {
    var box = h('div', { class: 'ed-checklist', id: 'ed-checklist' });
    if (!ST.problems.length) {
      box.appendChild(h('p', { class: 'ed-ok', text: 'Ready to open: everything is filled in.' }));
    } else {
      box.appendChild(h('p', { class: 'ed-label', text: 'Before it can open:' }));
      box.appendChild(h('ul', {}, ST.problems.map(function (p) { return h('li', { text: p }); })));
    }
    return box;
  }

  function settingsTab() {
    var s = ST.survey;
    return [
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Status' }),
        segmented('survey', s, 'status', CH.status.map(function (c) { return [c[0], c[1].split(':')[0]]; }), {
          label: 'Who can see it', rerender: true,
          hint: 'Draft: only you (preview). Open: collecting responses. Closed: shows your closed page.' }),
        checklist()),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Basics' }),
        input('survey', s, 'title', { label: 'Title', maxlength: 200, onInput: function (v) { document.getElementById('ed-title').textContent = v; } }),
        input('survey', s, 'slug', { label: 'Address', maxlength: 60, onChangeOnly: true,
          hint: 'adhenzmiranda.com/' + s.slug + '/ (short is better for QR codes). Saved when you leave the field; old links and QR codes stop working.' }),
        h('div', { class: 'ed-grid3' },
          input('survey', s, 'batch', { label: 'Batch', maxlength: 40, hint: 'pilot, then main' }),
          input('survey', s, 'target_responses', { label: 'Target responses', type: 'number', number: true }),
          input('survey', s, 'ethics_reference', { label: 'Ethics approval reference', maxlength: 100 }))),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Consent page' }),
        input('survey', s, 'intro_heading', { label: 'Heading', maxlength: 200 }),
        input('survey', s, 'intro_text', { label: 'Information', rows: 10, hint: 'Markdown: ### heading, - bullet point, **bold**.' }),
        input('survey', s, 'consent_statements', { label: 'Tick boxes', rows: 3, hint: 'One per line. All must be ticked to start.' }),
        input('survey', s, 'start_label', { label: 'Start button', maxlength: 60 }),
        h('div', { class: 'ed-grid2' },
          input('survey', s, 'researcher_email', { label: 'Researcher email', type: 'email' }),
          input('survey', s, 'ethics_contact', { label: 'Supervisor or ethics contact', maxlength: 200 }))),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Thank-you page' }),
        input('survey', s, 'thanks_heading', { label: 'Heading', maxlength: 200 }),
        input('survey', s, 'thanks_message', { label: 'Message', rows: 4, hint: 'Markdown.' }),
        imageField('survey', s, 'share_image', 'Share image (optional)',
          'e.g. 1080 x 1920 for stories. Keep the tips and answers off it, so friends who take it later aren’t primed.'),
        input('survey', s, 'share_text', { label: 'Text that goes with the link when shared', maxlength: 280 }),
        input('survey', s, 'already_done_message', { label: 'Message on a return visit', maxlength: 200 })),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Closed page' }),
        input('survey', s, 'closed_heading', { label: 'Heading', maxlength: 200 }),
        input('survey', s, 'closed_message', { label: 'Message', rows: 3 })),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Media posts' }),
        input('survey', s, 'post_handle', { label: 'Account name on the mock posts', maxlength: 60 })),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Version ' + s.version }),
        note('Duplicating makes an editable Draft copy (next version) with a new address. Use it when this one has responses and needs changes; then close this one and swap the addresses.'),
        h('div', { class: 'ed-add' },
          button('Duplicate as a new version', function () {
            act('duplicate-survey/', {}, { confirm: 'Make an editable copy of this survey as version ' + (s.version + 1) + '?' });
          }),
          h('a', { class: 'btn btn--ghost ed-btn', href: ST.links.admin, text: 'Open in the Django admin' })))
    ];
  }

  // ------------------------------------------------------------ page

  function updateHeader() {
    var status = document.getElementById('ed-status');
    status.textContent = label(CH.status, ST.survey.status).split(':')[0];
    status.dataset.status = ST.survey.status;
  }

  function switchTab(name) {
    tab = name;
    writeTab(name);
    render();
    window.scrollTo(0, 0);
  }

  function render() {
    var scroll = window.scrollY;
    document.querySelectorAll('.ed-tab').forEach(function (b) {
      b.setAttribute('aria-current', b.dataset.tab === tab ? 'page' : 'false');
    });
    while (main.firstChild) { main.removeChild(main.firstChild); }
    if (ST.locked) {
      main.appendChild(h('div', { class: 'ed-banner', role: 'note' },
        h('strong', { text: 'Locked: this survey has responses.' }),
        ' Pages, questions, prompts, media and the consent text can’t change, so every response answered the same survey. ' +
        'Status, batch, contacts, the closed page and the thank-you page still can. To change the rest, duplicate it as a new version in Settings.'));
    }
    var content = { pages: pagesTab, prompts: promptsTab, media: mediaTab, results: resultsTab, settings: settingsTab }[tab] || pagesTab;
    append(main, content());
    updateHeader();
    window.scrollTo(0, scroll);
  }

  // ------------------------------------------------------------ live preview

  var previewTimer = null;
  function loadPreview() {
    if (WIDE.matches && !frame.getAttribute('src')) { frame.src = ST.links.preview; }
  }
  function reloadPreviewSoon() {
    clearTimeout(previewTimer);
    previewTimer = setTimeout(function () {
      if (!frame.getAttribute('src')) { return; }
      try { frame.contentWindow.location.reload(); } catch (e) { frame.src = ST.links.preview; }
    }, 900);
  }
  document.getElementById('ed-preview-reload').addEventListener('click', reloadPreviewSoon);
  document.getElementById('ed-preview-restart').addEventListener('click', function () {
    try {
      var store = frame.contentWindow.sessionStorage;
      Object.keys(store).filter(function (k) { return k.indexOf('survey:') === 0; }).forEach(function (k) { store.removeItem(k); });
    } catch (e) { /* not loaded yet */ }
    reloadPreviewSoon();
  });
  WIDE.addEventListener('change', loadPreview);

  document.querySelectorAll('.ed-tab').forEach(function (b) {
    b.addEventListener('click', function () { switchTab(b.dataset.tab); });
  });

  window.addEventListener('beforeunload', function (e) {
    if (Object.keys(queue).length || inFlight) { e.preventDefault(); e.returnValue = ''; }
  });

  render();
  loadPreview();
})();
