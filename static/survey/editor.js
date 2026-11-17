/*
 * Survey editor (/<address>/edit/), for the researcher only. Part of Studio: it opens in
 * Studio's frame and uses Studio's editor kit (static/studio/kit.js) for saving, fields,
 * uploads and reordering.
 *
 * Google Forms-style: every field saves itself a moment after you stop typing
 * (survey/editor.py checks it with the same rules as the admin, including the content
 * lock). Pages and questions reorder by drag and drop (mouse) or the arrow buttons
 * (anywhere); questions can be dragged between pages.
 * Everything is built with DOM methods and textContent, never HTML strings.
 */
(function () {
  'use strict';

  // Everything is loaded from the API (see start-up at the bottom); nothing is read
  // back out of the page. /<address>/edit/ -> /<address>/edit/api/
  var API = location.pathname.replace(/\/edit\/?$/, '/edit/api/');
  var CH = null;           // choices for dropdowns, from the server
  var ST = null;           // the survey, from the server
  var main = document.getElementById('ed-main');
  var tab = readTab();
  var uid = 0;

  var kit = StudioKit.create({ api: API, refresh: refresh, render: render, onSaved: afterSave });
  var h = kit.h;
  var button = kit.button;
  var iconButton = kit.iconButton;
  var note = kit.note;

  // ------------------------------------------------------------ small helpers

  function append(el, child) {
    if (child === null || child === undefined || child === false) { return; }
    if (Array.isArray(child)) { child.forEach(function (c) { append(el, c); }); return; }
    el.appendChild(child);
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

  // ------------------------------------------------------------ server (through the Studio kit)

  // Once a survey has responses, everything is locked except a few survey settings.
  function isLocked(model, field) {
    return ST.locked && (model !== 'survey' || CH.lockedFields.indexOf(field) !== -1);
  }

  function path(model, id) { return model + '/' + id + '/'; }

  // What a field edits, in the kit's terms. A page's question list is kept on save, because
  // open question cards still point at those question objects.
  function tgt(model, item) {
    return { path: path(model, item.id), item: item, model: model,
             locked: function (field) { return isLocked(model, field); },
             keep: model === 'section' ? ['questions'] : null };
  }

  // After every save: the checklist, the lock and the status can all change.
  function afterSave(target, data) {
    ST.problems = data.problems;
    ST.locked = data.locked;
    if (data.status) { ST.survey.status = data.status; }
    updateHeader();
    var box = document.getElementById('ed-checklist');
    if (box) { box.replaceWith(checklist()); }
    // An earlier "not ready to open" message is out of date once the checklist changes.
    if (!(target.model === 'survey' && data.item && data.item.status === 'open')) {
      kit.fieldError(path('survey', ST.survey.id), 'status', '');
    }
  }

  function act(apiPath, body, options) { return kit.act(apiPath, body, options); }
  function flush(model, id) { return kit.flush(path(model, id)); }

  function refresh() {
    return kit.api('state/', { method: 'GET' }).then(function (res) {
      if (res.ok) {
        ST = res.data;
        CH = res.data.choices;
        render();
        return;
      }
      kit.setSave('error', res.data.error || 'Couldn’t load the latest version.');
      if (!ST) {
        kit.clear(main);
        main.appendChild(h('p', { class: 'ed-banner', text: 'The editor couldn’t load. ' + (res.data.error || 'Check your connection and reload the page.') }));
      }
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

  // ------------------------------------------------------------ form controls (the kit's, per model)

  function wrap(model, id, field, labelText, control, hint) { return kit.wrap(path(model, id), field, labelText, control, hint); }

  function input(model, item, field, opts) {
    opts = opts || {};
    return kit.input(tgt(model, item), field, {
      label: opts.label, rows: opts.rows, type: opts.type, number: opts.number, line: opts.line, lineClass: opts.lineClass,
      inputClass: opts.big ? 'ed-input--big' : null, placeholder: opts.placeholder, maxlength: opts.maxlength,
      hint: opts.hint, onInput: opts.onInput, onChangeOnly: opts.onChangeOnly });
  }

  function select(model, item, field, choices, opts) {
    opts = opts || {};
    return kit.select(tgt(model, item), field, choices, { label: opts.label, aria: opts.aria, hint: opts.hint, rerender: opts.rerender });
  }

  function toggle(model, item, field, text, opts) {
    return kit.toggle(tgt(model, item), field, text, { rerender: (opts || {}).rerender });
  }

  // Two or three buttons, one active (e.g. Safe / Risky, Draft / Open / Closed).
  function segmented(model, item, field, choices, opts) {
    opts = opts || {};
    return kit.segmented(tgt(model, item), field, choices, { label: opts.label, hint: opts.hint, rerender: opts.rerender });
  }

  // ------------------------------------------------------------ uploads

  function imageField(model, item, field, labelText, hint) {
    return kit.imageField(tgt(model, item), field, labelText, { hint: hint, maxMb: CH.maxImageMb });
  }

  // Reels go straight from the browser to Cloudinary (signed by the server), so Heroku's
  // 30 second limit never applies. The server checks Cloudinary's signature before saving.
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
      kit.setSave('busy', 'Uploading video…');
      kit.directUpload('sign-video/', chosen, function (pct) {
        bar.hidden = false;
        bar.value = pct;
        status.textContent = 'Uploading to Cloudinary… ' + pct + '%';
      }).then(function (ref) {
        return kit.api(path('condition', item.id), { body: { video: ref } });
      }).then(function (res) {
        if (!res.ok) { throw new Error(res.data.error || 'The upload could not be saved.'); }
        if (res.data.item) { Object.assign(item, res.data.item); }
        afterSave(tgt('condition', item), res.data);
        kit.setSave('ok', 'Saved');
        render();
      }).catch(function (err) {
        bar.hidden = true;
        file.value = '';
        status.textContent = err.message;
        kit.setSave('error', 'Upload failed.');
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

  // The grip: drag with a mouse (touch screens use the arrows).
  function dragHandle(kind) { return kit.dragHandle(kind, ST.locked); }

  function reorder(kind, sectionId, ids) {
    return act('reorder/', kind === 'section' ? { kind: 'section', ids: ids } : { kind: 'question', section: sectionId, ids: ids });
  }

  function arrows(kind, list, index, sectionId) {
    var ids = list.map(function (x) { return x.id; });
    return kit.arrows(ids, index, kind === 'section' ? 'page' : 'question',
                      function (next) { reorder(kind, sectionId, next); }, ST.locked);
  }

  // Pages reorder among themselves; questions can also be dragged onto another page.
  function enableDrag(list, kind) {
    kit.enableDrag(list, kind, function (ids, dropList) {
      reorder(kind, Number(dropList.dataset.section), ids);
    }, { locked: ST.locked, across: kind === 'question' });
  }

  // ------------------------------------------------------------ Pages tab (Google Forms-style cards)

  // One question card is open for editing at a time; the others show a preview.
  var activeQuestion = null;

  function findQuestion(id) {
    for (var i = 0; i < ST.sections.length; i++) {
      var qs = ST.sections[i].questions;
      for (var j = 0; j < qs.length; j++) {
        if (qs[j].id === id) { return { q: qs[j], j: j, section: ST.sections[i] }; }
      }
    }
    return null;
  }

  // Redraw one question card in place (open or closed) without redrawing the page.
  function redrawQuestion(id, focus) {
    var found = findQuestion(id);
    var el = main.querySelector('.ed-qcard[data-id="' + id + '"]');
    if (!found || !el) { return; }
    var fresh = questionCard(found.q, found.j, found.section);
    el.replaceWith(fresh);
    if (focus) {
      var first = fresh.querySelector('.ed-line');
      if (first) { first.focus({ preventScroll: true }); }
      fresh.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function openQuestion(id) {
    if (activeQuestion === id) { return; }
    var previous = activeQuestion;
    activeQuestion = id;
    // Save the card being closed first, so its preview shows the latest text.
    (previous ? flush('question', previous) : Promise.resolve()).then(function () {
      if (previous) { redrawQuestion(previous); }
      redrawQuestion(id, true);
    });
  }

  function closeQuestion() {
    var previous = activeQuestion;
    if (!previous) { return; }
    activeQuestion = null;
    flush('question', previous).then(function () {
      redrawQuestion(previous);
      var card = main.querySelector('.ed-qcard[data-id="' + previous + '"]');
      if (card) { card.focus({ preventScroll: true }); }
    });
  }

  function infoCard(kicker, title, text, buttonText, tabName) {
    return h('section', { class: 'ed-card ed-card--fixed' },
      h('span', { class: 'ed-kicker', text: kicker }),
      h('h2', { class: 'ed-card__title', text: title }),
      note(text),
      button(buttonText, function () { switchTab(tabName); }));
  }

  function pagesTab() {
    var n = ST.sections.length;
    var list = h('div', { class: 'ed-pages' });
    ST.sections.forEach(function (s, i) { list.appendChild(pageBlock(s, i, n)); });
    enableDrag(list, 'section');
    var kinds = ST.sections.map(function (s) { return s.kind; });
    var addKind = h('select', { class: 'ed-input ed-select', 'aria-label': 'Type of page to add', disabled: ST.locked });
    CH.sectionKinds.forEach(function (c) {
      var once = c[0] === 'task_before' || c[0] === 'media' || c[0] === 'task_after';
      addKind.appendChild(h('option', { value: c[0], text: c[1] + (once && kinds.indexOf(c[0]) !== -1 ? ' (already added)' : ''),
                                        disabled: once && kinds.indexOf(c[0]) !== -1 }));
    });
    return [
      infoCard('Start', 'Consent page', 'Information, contacts and tick boxes. Every participant sees it first.', 'Edit in Settings', 'settings'),
      list,
      h('div', { class: 'ed-addpage' },
        h('span', { class: 'ed-label', text: 'Add a page' }),
        h('div', { class: 'ed-add' }, addKind,
          button('+ Add page', function () {
            act('section/new/', { kind: addKind.value }).then(function (data) {
              if (data && data.item) { focusNew('.ed-page[data-id="' + data.item.id + '"]'); }
            });
          }, { class: 'btn btn--primary ed-btn', disabled: ST.locked }))),
      infoCard('End', 'Thank-you page', 'Shown after submitting, with your logo, share buttons and the site’s navbar and footer.', 'Edit in Settings', 'settings')
    ];
  }

  // A page: a header card (like a Google Forms section), then its question cards.
  function pageBlock(s, i, n) {
    var header = h('section', { class: 'ed-pagecard' },
      h('div', { class: 'ed-pagecard__top' },
        dragHandle('section'),
        h('div', { class: 'ed-tools' }, arrows('section', ST.sections, i),
          iconButton('✕', 'Delete page', function () {
            act('section/' + s.id + '/delete/', {}, { confirm: 'Delete the page "' + s.title + '"' +
              (s.questions.length ? ' and its ' + s.questions.length + ' question(s)' : '') + '?' });
          }, ST.locked))),
      input('section', s, 'title', { line: true, lineClass: 'ed-line--title', label: 'Page title', maxlength: 200 }),
      input('section', s, 'description', { line: true, rows: 1, label: 'Page description (optional)',
        hint: 'Markdown works: **bold**, - bullet points.' }),
      h('details', { class: 'ed-more' }, h('summary', { text: 'Page settings' }),
        input('section', s, 'button_label', { label: 'Button text', maxlength: 60,
          placeholder: i === n - 1 ? 'Submit answers' : 'Next', hint: 'Leave blank for the default shown.' })));

    if (s.kind === 'task_before' || s.kind === 'task_after') {
      header.appendChild(h('div', { class: 'ed-info' },
        note('Shows all ' + ST.prompts.length + ' prompts in a new random order for each person' +
             (s.kind === 'task_after' ? ' (different from the first round).' : '.')),
        button('Edit prompts', function () { switchTab('prompts'); })));
    } else if (s.kind === 'media') {
      var active = ST.conditions.filter(function (c) { return c.active; }).length;
      header.appendChild(h('div', { class: 'ed-info' },
        note('Each person sees one of the ' + active + ' active media groups, picked so the groups stay even. Back is turned off from here on.'),
        button('Edit media', function () { switchTab('media'); })));
    }

    var block = h('div', { class: 'ed-page', 'data-drag': 'section', 'data-id': s.id },
      h('div', { class: 'ed-page__tab' },
        h('span', { text: 'Page ' + (i + 1) + ' of ' + n }),
        h('span', { class: 'ed-page__kind', text: label(CH.sectionKinds, s.kind) })),
      header);

    if (s.kind === 'questions') {
      var qlist = h('div', { class: 'ed-qlist', 'data-section': s.id });
      s.questions.forEach(function (q, j) { qlist.appendChild(questionCard(q, j, s)); });
      enableDrag(qlist, 'question');
      block.appendChild(qlist);
      block.appendChild(h('button', { type: 'button', class: 'ed-addq', disabled: ST.locked, onclick: function () {
        act('question/new/', { section: s.id, kind: 'choice' }).then(function (data) {
          if (data && data.item) { activeQuestion = null; openQuestion(data.item.id); }
        });
      } }, h('span', { 'aria-hidden': 'true', text: '+' }), ' Add question'));
    }
    return block;
  }

  function questionCard(q, j, section) {
    return activeQuestion === q.id && !ST.locked ? questionEditor(q, j, section) : questionPreview(q, j);
  }

  // Closed card: what participants will see, at a glance. Click to edit.
  function questionPreview(q, j) {
    var card = h('article', { class: 'ed-qcard', 'data-drag': 'question', 'data-id': q.id, tabindex: '0',
                              role: ST.locked ? null : 'button',
                              'aria-label': (ST.locked ? 'Question ' : 'Edit question ') + (j + 1) + ': ' + (q.text || 'Untitled question') },
      dragHandle('question'),
      h('p', { class: 'ed-qcard__q' },
        h('span', { text: q.text || 'Untitled question' }),
        q.required ? h('span', { class: 'ed-req', title: 'Required', text: ' *' }) : null),
      q.help_text ? h('p', { class: 'ed-qcard__help', text: q.help_text }) : null,
      answerPreview(q),
      h('div', { class: 'ed-qcard__chips' },
        h('span', { class: 'ed-chip', text: label(CH.questionKinds, q.kind) }),
        q.construct ? h('span', { class: 'ed-chip', text: 'Construct: ' + q.construct }) : null,
        q.attention_answer ? h('span', { class: 'ed-chip ed-chip--warn', text: 'Attention check' }) : null));
    if (!ST.locked) {
      card.addEventListener('click', function (e) {
        if (!e.target.closest('[data-handle]')) { openQuestion(q.id); }
      });
      card.addEventListener('keydown', function (e) {
        if (e.target === card && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openQuestion(q.id); }
      });
    }
    return card;
  }

  function optionsOf(q) {
    return (q.options || '').split('\n').map(function (o) { return o.trim(); }).filter(Boolean);
  }

  function answerPreview(q) {
    var opts = optionsOf(q);
    if (q.kind === 'choice' || q.kind === 'checkboxes' || q.kind === 'dropdown') {
      var shown = opts.slice(0, 6);
      var list = h('ul', { class: 'ed-preview-opts' }, shown.map(function (o, i) {
        var mark = q.kind === 'checkboxes' ? '☐' : q.kind === 'dropdown' ? (i + 1) + '.' : '○';
        return h('li', {}, h('span', { class: 'ed-option__mark', 'aria-hidden': 'true', text: mark }), h('span', { text: o }));
      }));
      if (opts.length > shown.length) { list.appendChild(h('li', { class: 'ed-preview-more', text: '+ ' + (opts.length - shown.length) + ' more' })); }
      if (!opts.length) { list.appendChild(h('li', { class: 'ed-preview-more', text: 'No options yet' })); }
      return list;
    }
    if (q.kind === 'scale') {
      return h('div', { class: 'ed-preview-scale' },
        h('span', { class: 'ed-preview-scale__end', text: q.scale_low_label }),
        [1, 2, 3, 4, 5].map(function (n) { return h('span', { class: 'ed-preview-scale__n', text: n }); }),
        h('span', { class: 'ed-preview-scale__end', text: q.scale_high_label }));
    }
    var text = q.kind === 'long_text' ? 'Long answer text' : q.kind === 'number'
      ? 'Number' + (q.min_value !== null && q.max_value !== null ? ' (' + q.min_value + ' to ' + q.max_value + ')' : '')
      : 'Short answer text';
    return h('p', { class: 'ed-preview-line' + (q.kind === 'long_text' ? ' ed-preview-line--long' : ''), text: text });
  }

  // Open card: edit everything in place, with a toolbar at the bottom.
  function questionEditor(q, j, section) {
    var others = ST.sections.filter(function (s) { return s.kind === 'questions'; });
    var move = h('select', { class: 'ed-input ed-select' });
    move.id = nextId();
    others.forEach(function (s) {
      move.appendChild(h('option', { value: String(s.id), text: 'Page ' + (ST.sections.indexOf(s) + 1) + ': ' + s.title,
                                     selected: s.id === section.id }));
    });
    move.addEventListener('change', function () {
      var target = others.filter(function (s) { return String(s.id) === move.value; })[0];
      var ids = target.questions.map(function (x) { return x.id; }).concat([q.id]);
      act('reorder/', { kind: 'question', section: target.id, ids: ids });
    });

    var more = h('details', { class: 'ed-more ed-qcard__more' }, h('summary', { text: 'More settings' }),
      input('question', q, 'code', { label: 'Column name in the CSV', maxlength: 40,
        hint: 'Letters, numbers, - and _ only. Unique in this survey.' }),
      q.kind === 'scale' ? input('question', q, 'construct', { label: 'Construct (hidden from participants)', maxlength: 40,
        hint: 'Groups scale questions for analysis, e.g. engagement. The CSV gets a mean per construct.' }) : null,
      input('question', q, 'attention_answer', { label: 'Attention check answer', maxlength: 200,
        hint: 'Only for attention checks: the answer a careful reader gives. The CSV marks pass or fail.' }),
      wrap('question', q.id, 'section', 'Move to page', move));

    var card = h('article', { class: 'ed-qcard is-active', 'data-drag': 'question', 'data-id': q.id },
      dragHandle('question'),
      h('div', { class: 'ed-qcard__main' },
        input('question', q, 'text', { line: true, lineClass: 'ed-line--q', label: 'Question', maxlength: 300 }),
        select('question', q, 'kind', CH.questionKinds, { aria: 'Question type', rerender: true })),
      input('question', q, 'help_text', { line: true, label: 'Description (optional)', maxlength: 300 }),
      h('div', { class: 'ed-qcard__answer' },
        CH.optionKinds.indexOf(q.kind) !== -1 ? optionsEditor(q) : null,
        q.kind === 'number' ? h('div', { class: 'ed-grid3' },
          input('question', q, 'min_value', { label: 'Lowest allowed', type: 'number', number: true }),
          input('question', q, 'max_value', { label: 'Highest allowed', type: 'number', number: true }),
          input('question', q, 'range_message', { label: 'Message if out of range', maxlength: 200 })) : null,
        q.kind === 'scale' ? h('div', { class: 'ed-grid2' },
          input('question', q, 'scale_low_label', { label: 'Label for 1', maxlength: 60 }),
          input('question', q, 'scale_high_label', { label: 'Label for 5', maxlength: 60 })) : null,
        q.kind === 'short_text' || q.kind === 'long_text'
          ? h('p', { class: 'ed-preview-line' + (q.kind === 'long_text' ? ' ed-preview-line--long' : ''),
                     text: q.kind === 'long_text' ? 'Long answer text' : 'Short answer text' }) : null),
      h('div', { class: 'ed-qcard__bar' },
        h('div', { class: 'ed-tools' }, arrows('question', section.questions, j, section.id)),
        h('div', { class: 'ed-tools' },
          iconButton('⧉', 'Duplicate question', function () {
            act('question/' + q.id + '/duplicate/', {}).then(function (data) {
              if (data && data.item) { activeQuestion = null; openQuestion(data.item.id); }
            });
          }),
          iconButton('✕', 'Delete question', function () {
            act('question/' + q.id + '/delete/', {}, { confirm: 'Delete the question "' + (q.text || 'Untitled question') + '"?' });
          }),
          h('span', { class: 'ed-divider', 'aria-hidden': 'true' }),
          toggle('question', q, 'required', 'Required', { rerender: false }),
          button('Done', closeQuestion, { class: 'ed-link ed-done' }))),
      more);
    card.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.preventDefault(); closeQuestion(); }
    });
    return card;
  }

  // One line per option, like Google Forms. Saved as one option per line; Enter adds the next.
  function optionsEditor(q) {
    var lines = (q.options || '').split('\n');
    if (!lines.length) { lines = ['']; }
    var box = h('div', { class: 'ed-field ed-options', 'data-key': path('question', q.id) + ':options' });
    function save() {
      q.options = lines.join('\n');
      kit.queueSave(tgt('question', q), 'options', q.options);
    }
    function mark(i) {
      return h('span', { class: 'ed-option__mark', 'aria-hidden': 'true',
                         text: q.kind === 'checkboxes' ? '☐' : q.kind === 'dropdown' ? (i + 1) + '.' : '○' });
    }
    function draw(focusIndex) {
      while (box.firstChild) { box.removeChild(box.firstChild); }
      lines.forEach(function (text, i) {
        var el = h('input', { class: 'ed-line', type: 'text', value: text, 'aria-label': 'Option ' + (i + 1), placeholder: 'Option ' + (i + 1) });
        el.addEventListener('input', function () { lines[i] = el.value; save(); });
        el.addEventListener('keydown', function (e) {
          if (e.key === 'Enter') { e.preventDefault(); lines.splice(i + 1, 0, ''); save(); draw(i + 1); }
        });
        box.appendChild(h('div', { class: 'ed-option' }, mark(i), el,
          iconButton('✕', 'Remove option ' + (i + 1), function () {
            lines.splice(i, 1);
            if (!lines.length) { lines.push(''); }
            save();
            draw();
          }, lines.length === 1)));
        if (focusIndex === i) { requestAnimationFrame(function () { el.focus(); }); }
      });
      box.appendChild(h('div', { class: 'ed-option ed-option--add' }, mark(lines.length),
        button('Add option', function () {
          lines.push('Option ' + (lines.length + 1));
          save();
          draw(lines.length - 1);
        }, { class: 'ed-link' })));
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
    // A plain form: the browser sends ?src=...&format=..., and the server cleans the tag.
    var tag = h('input', { class: 'ed-input', type: 'text', name: 'src', placeholder: 'optional tag, e.g. rak-poster',
                           maxlength: 60, pattern: '[A-Za-z0-9_-]*' });
    tag.id = nextId();
    var qrForm = h('form', { method: 'get', action: ST.links.qr },
      wrap('qr', 0, 'src', 'QR code tag', tag, 'A tag adds ?src=tag to the link, so the CSV’s source column shows where each person came from.'),
      h('div', { class: 'ed-add' },
        h('button', { type: 'submit', name: 'format', value: 'png', class: 'btn btn--ghost ed-btn', text: 'Download QR (PNG)' }),
        h('button', { type: 'submit', name: 'format', value: 'svg', class: 'btn btn--ghost ed-btn', text: 'SVG' })));
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
      reviewCard(),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Share the survey' }),
        h('p', { class: 'ed-link-line' }, h('a', { href: ST.links.public, target: '_blank', rel: 'noopener', text: ST.links.public })),
        h('div', { class: 'ed-add' }, button('Copy link', function () {
          (navigator.clipboard ? navigator.clipboard.writeText(ST.links.public) : Promise.reject())
            .then(function () { copied.textContent = 'Copied.'; }, function () { copied.textContent = ST.links.public; });
        }), copied),
        qrForm)
    ];
  }

  // Review link for a supervisor: the whole survey, no login, nothing saved, any status.
  function reviewCard() {
    var status = h('span', { class: 'ed-upload__status', role: 'status' });
    return h('section', { class: 'ed-card' },
      h('h2', { class: 'ed-card__title', text: 'Review link (for your supervisor)' }),
      note('Anyone with this link can try the whole survey, even while it is a draft. No login is needed and nothing is saved, ' +
           'so it never mixes into your data. Only share it with people reviewing the survey.'),
      h('p', { class: 'ed-link-line' }, h('a', { href: ST.links.review, target: '_blank', rel: 'noopener', text: ST.links.review })),
      h('div', { class: 'ed-add' }, button('Copy review link', function () {
        (navigator.clipboard ? navigator.clipboard.writeText(ST.links.review) : Promise.reject())
          .then(function () { status.textContent = 'Copied.'; }, function () { status.textContent = ST.links.review; });
      }, { class: 'btn btn--primary ed-btn' }), status));
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
        input('survey', s, 'title', { label: 'Title', maxlength: 200, onInput: function (v) { document.getElementById('st-title').textContent = v; } }),
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

  var TABS = [['pages', 'Pages'], ['prompts', 'Prompts'], ['media', 'Media'], ['results', 'Results'], ['settings', 'Settings']];

  function switchTab(name) {
    kit.flushAll().then(function () {
      tab = name;
      writeTab(name);
      render();
      window.scrollTo(0, 0);
    });
  }

  function render() {
    var scroll = window.scrollY;
    var preview = document.getElementById('st-preview');
    preview.href = ST.links.preview;
    preview.hidden = false;
    kit.clear(main);
    main.appendChild(h('nav', { class: 'st-subtabs', 'aria-label': 'Survey editor sections' }, TABS.map(function (x) {
      return h('button', { type: 'button', class: 'st-subtab', 'aria-current': x[0] === tab ? 'page' : 'false', text: x[1],
                           onclick: function () { switchTab(x[0]); } });
    })));
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

  refresh();   // leaving with unsaved changes or a running upload is warned about by the kit
})();
