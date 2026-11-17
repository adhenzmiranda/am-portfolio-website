/*
 * Studio About page (/studio/about/): the Experience and Education lists on /about/.
 * Experience entries are Google Forms-style cards (click to open); Education entries are short,
 * so they're always open. New entries start hidden at the top; switch them on when they're ready.
 * Saves through /studio/api/about/ (see studio/api.py).
 */
(function () {
  'use strict';
  var main = document.getElementById('ed-main');
  var previewLink = document.getElementById('st-preview');
  var ST = null;
  var openId = null;   // the Experience card being edited

  var kit = StudioKit.create({ api: '/studio/api/', refresh: refresh, render: render });
  var h = kit.h;

  function path(kind, id) { return 'about/' + kind + '/' + (id ? id + '/' : ''); }

  function refresh() {
    return kit.api('about/', { method: 'GET' }).then(function (res) {
      if (res.ok) { ST = res.data; render(); return; }
      kit.setSave('error', res.data.error || 'Couldn’t load the About page.');
      if (!ST) {
        kit.clear(main);
        main.appendChild(h('p', { class: 'ed-banner', text: res.data.error || 'Couldn’t load the About page.' }));
      }
    });
  }

  function reorder(kind) { return function (ids) { kit.act(path(kind) + 'reorder/', { ids: ids }); }; }

  function hiddenChip(item) { return item.visible ? null : h('span', { class: 'ed-chip ed-chip--warn', text: 'Hidden' }); }

  function visibleSwitch(t) {
    return kit.toggle(t, 'visible', 'Shown on the About page', { rerender: true });
  }

  function deleteButton(kind, item, name) {
    return kit.iconButton('✕', 'Delete ' + (kind === 'experience' ? 'role' : 'entry'), function () {
      kit.act(path(kind, item.id) + 'delete/', {}, { confirm: 'Delete "' + name + '"? To keep it but take it off the page, switch it to hidden instead.' });
    });
  }

  // ------------------------------------------------------------ Experience

  function lines(text) { return (text || '').split('\n').filter(function (l) { return l.trim(); }).length; }

  function experiencePreview(e, i) {
    var el = h('article', { class: 'ed-qcard' + (e.visible ? '' : ' st-is-hidden'), 'data-drag': 'experience', 'data-id': e.id,
                            tabindex: '0', role: 'button', 'aria-label': 'Edit role ' + (i + 1) + ': ' + e.role },
      kit.dragHandle('experience'),
      h('span', { class: 'ed-kicker', text: e.dates }),
      h('p', { class: 'ed-qcard__q', text: e.role }),
      h('p', { class: 'ed-qcard__help', text: e.organisation + ' · ' + e.location }),
      h('div', { class: 'ed-qcard__chips' },
        h('span', { class: 'ed-chip', text: lines(e.highlights_raw) + (lines(e.highlights_raw) === 1 ? ' highlight' : ' highlights') }),
        hiddenChip(e)));
    el.addEventListener('click', function (ev) { if (!ev.target.closest('[data-handle]')) { open(e.id); } });
    el.addEventListener('keydown', function (ev) {
      if (ev.target === el && (ev.key === 'Enter' || ev.key === ' ')) { ev.preventDefault(); open(e.id); }
    });
    return el;
  }

  function experienceEditor(e, i, ids) {
    var t = { path: path('experience', e.id), item: e };
    var el = h('article', { class: 'ed-qcard is-active', 'data-drag': 'experience', 'data-id': e.id },
      kit.dragHandle('experience'),
      kit.input(t, 'role', { line: true, lineClass: 'ed-line--q', label: 'Role', maxlength: 200 }),
      h('div', { class: 'ed-grid3' },
        kit.input(t, 'organisation', { label: 'Organisation', maxlength: 200 }),
        kit.input(t, 'location', { label: 'Location', maxlength: 200, placeholder: 'Business Bay, Dubai' }),
        kit.input(t, 'dates', { label: 'Dates (shown as typed)', maxlength: 100, placeholder: 'Sep 2026 - Present' })),
      kit.input(t, 'highlights_raw', { label: 'Highlights (one per line, each becomes a bullet point)', rows: 4 }),
      h('div', { class: 'ed-qcard__bar' },
        h('div', { class: 'ed-tools' }, visibleSwitch(t)),
        h('div', { class: 'ed-tools' },
          kit.arrows(ids, i, 'role', reorder('experience')),
          deleteButton('experience', e, e.role),
          h('span', { class: 'ed-divider', 'aria-hidden': 'true' }),
          kit.button('Done', function () { open(null); }, { class: 'ed-link ed-done' }))));
    el.addEventListener('keydown', function (ev) { if (ev.key === 'Escape') { ev.preventDefault(); open(null); } });
    return el;
  }

  function open(id) {
    var prev = openId;
    openId = id;
    (prev ? kit.flush(path('experience', prev)) : Promise.resolve()).then(function () {
      render();
      var card = '.ed-qcard[data-drag="experience"][data-id="';
      var target = id ? main.querySelector(card + id + '"] .ed-line') : (prev ? main.querySelector(card + prev + '"]') : null);
      if (target) { target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    });
  }

  function experienceSection() {
    var ids = ST.experience.map(function (e) { return e.id; });
    var list = h('div', { class: 'ed-qlist' });
    ST.experience.forEach(function (e, i) { list.appendChild(openId === e.id ? experienceEditor(e, i, ids) : experiencePreview(e, i)); });
    if (!ST.experience.length) { list.appendChild(kit.note('No roles yet. The Experience section is left off the page until there’s one to show.')); }
    kit.enableDrag(list, 'experience', reorder('experience'));
    return h('section', { class: 'st-media-section', 'aria-label': 'Experience' },
      h('div', { class: 'ed-card ed-card--fixed' },
        h('div', { class: 'st-media__head' },
          h('h2', { class: 'ed-card__title', text: 'Experience' }),
          h('span', { class: 'ed-chip', text: ST.experience.length + (ST.experience.length === 1 ? ' role' : ' roles') })),
        kit.note('Shown first on the About page, in this order. Click a role to edit it; drag ⠇ or use the arrows to reorder.')),
      list,
      h('button', { type: 'button', class: 'ed-addq', onclick: function () {
        kit.act(path('experience') + 'new/', {}).then(function (data) { if (data && data.item) { open(data.item.id); } });
      } }, h('span', { 'aria-hidden': 'true', text: '+' }), ' Add a role'));
  }

  // ------------------------------------------------------------ Education

  function educationCard(e, i, ids) {
    var t = { path: path('education', e.id), item: e };
    return h('article', { class: 'ed-card st-media' + (e.visible ? '' : ' st-is-hidden'), 'data-drag': 'education', 'data-id': e.id },
      kit.dragHandle('education'),
      h('div', { class: 'st-edu' },
        kit.input(t, 'title', { label: 'Title (shown in bold)', maxlength: 200, placeholder: 'MSc in Cybersecurity' }),
        kit.input(t, 'details', { label: 'Details (optional)', maxlength: 300, placeholder: 'Bath Spa University, expected Jan 2027' })),
      h('div', { class: 'st-media__tools' },
        visibleSwitch(t),
        h('span', { class: 'st-media__spacer' }),
        kit.arrows(ids, i, 'entry', reorder('education')),
        deleteButton('education', e, e.title)));
  }

  function educationSection() {
    var ids = ST.education.map(function (e) { return e.id; });
    var list = h('div', { class: 'ed-qlist' });
    ST.education.forEach(function (e, i) { list.appendChild(educationCard(e, i, ids)); });
    if (!ST.education.length) { list.appendChild(kit.note('No entries yet. The Education section is left off the page until there’s one to show.')); }
    kit.enableDrag(list, 'education', reorder('education'));
    return h('section', { class: 'st-media-section', 'aria-label': 'Education' },
      h('div', { class: 'ed-card ed-card--fixed' },
        h('div', { class: 'st-media__head' },
          h('h2', { class: 'ed-card__title', text: 'Education' }),
          h('span', { class: 'ed-chip', text: ST.education.length + (ST.education.length === 1 ? ' entry' : ' entries') })),
        kit.note('Shown after Experience, in this order.')),
      list,
      h('button', { type: 'button', class: 'ed-addq', onclick: function () {
        kit.act(path('education') + 'new/', {}).then(function (data) {
          var input = data && data.item && main.querySelector('[data-id="' + data.item.id + '"] input');
          if (input) { input.focus(); input.select(); }
        });
      } }, h('span', { 'aria-hidden': 'true', text: '+' }), ' Add an entry'));
  }

  // ------------------------------------------------------------ page

  function render() {
    var scroll = window.scrollY;
    previewLink.href = ST.links.public;
    previewLink.hidden = false;
    kit.clear(main);
    main.appendChild(h('section', { class: 'st-hero' },
      h('h1', { class: 'st-h1', text: 'About page' }),
      kit.note('Your Experience and Education. Changes save themselves and go live straight away. New entries start hidden, so switch them on when they’re ready.')));
    main.appendChild(experienceSection());
    main.appendChild(educationSection());
    window.scrollTo(0, scroll);
  }

  refresh();
})();
