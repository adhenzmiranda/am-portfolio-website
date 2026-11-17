/*
 * Studio project editor (/studio/projects/<id>/).
 * Tabs follow the project's type:
 *   Portfolio:  Details · Write · Media
 *   Blog post:  Details · Write · Chapters · Media
 * Everything saves itself through /studio/api/projects/<id>/ (see studio/api.py).
 */
(function () {
  'use strict';
  var match = location.pathname.match(/\/studio\/projects\/(\d+)\//);
  var BASE = 'projects/' + (match ? Number(match[1]) : 0) + '/';
  var main = document.getElementById('ed-main');
  var titleEl = document.getElementById('st-title');
  var previewLink = document.getElementById('st-preview');
  var ST = null;
  var CH = null;
  var tab = readTab();
  var activeCard = null;
  var showPreview = false;   // phones: Write / Preview toggle

  var kit = StudioKit.create({ api: '/studio/api/', refresh: refresh, render: render, onSaved: onSaved });
  var h = kit.h;

  function readTab() { try { return sessionStorage.getItem('studio-project-tab') || 'details'; } catch (e) { return 'details'; } }
  function writeTab(v) { try { sessionStorage.setItem('studio-project-tab', v); } catch (e) { /* private mode */ } }

  function refresh() {
    return kit.api(BASE, { method: 'GET' }).then(function (res) {
      if (res.ok) { ST = res.data; CH = ST.choices; render(); return; }
      kit.setSave('error', res.data.error || 'Couldn’t load the project.');
      if (!ST) {
        kit.clear(main);
        main.appendChild(h('p', { class: 'ed-banner', text: res.data.error || 'Couldn’t load this project.' }));
      }
    });
  }

  function onSaved(target) {
    if (target.path === BASE) { titleEl.textContent = ST.project.name; }
  }

  function isBlog() { return ST.project.display_mode === 'blogpost'; }

  function tabs() {
    return [['details', 'Details'], ['write', 'Write']]
      .concat(isBlog() ? [['chapters', 'Chapters']] : [])
      .concat([['media', 'Media']]);
  }

  // ------------------------------------------------------------ Details

  function newCategory(t) {
    var name = h('input', { class: 'ed-input', type: 'text', maxlength: 50, placeholder: 'New category', 'aria-label': 'New category name' });
    var add = kit.button('Add', function () {
      if (!name.value.trim()) { return; }
      kit.api('categories/new/', { body: { name: name.value } }).then(function (res) {
        if (!res.ok) { kit.setSave('error', res.data.error || 'Couldn’t add the category.'); return; }
        CH.categories = res.data.categories;
        t.item.category = res.data.category[0];
        kit.queueSave(t, 'category', res.data.category[0], { now: true, rerender: true });
      });
    });
    name.addEventListener('keydown', function (e) { if (e.key === 'Enter') { add.click(); } });
    return h('div', { class: 'ed-field' }, h('span', { class: 'ed-label', text: 'Or add a category' }), h('div', { class: 'st-inline' }, name, add));
  }

  function detailsTab() {
    var p = ST.project;
    var t = { path: BASE, item: p };
    var cats = CH.categories.map(function (c) { return [String(c[0]), c[1]]; });
    return [
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Project' }),
        kit.input(t, 'name', { label: 'Name', maxlength: 255, inputClass: 'ed-input--big',
                               onInput: function (v) { titleEl.textContent = v; } }),
        h('div', { class: 'ed-grid3' },
          kit.input(t, 'year', { label: 'Year', type: 'number', number: true }),
          kit.select(t, 'category', cats, { label: 'Category', empty: 'No category', emptyValue: '',
                                            toValue: function (v) { return v === '' ? null : Number(v); } }),
          newCategory(t)),
        kit.toggle(t, 'featured', 'Featured on the home page'),
        kit.segmented(t, 'display_mode', CH.modes, { label: 'Type', rerender: true,
          hint: isBlog() ? 'Blog post: the description is the article intro, followed by Chapters. Photos are placed inside the text.'
                         : 'Portfolio: the description sits beside the cover image, followed by Videos, Photos and Embeds.' })),
      isBlog() ? null : h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Technologies' }),
        kit.note('Shown on the project page. Tap to add or remove.'),
        kit.chips(t, 'technologies', CH.technologies)),
      h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Cover image' }),
        kit.imageField(t, 'thumbnail_image', null, { wide: true, maxMb: CH.maxImageMb,
          hint: 'Shown on project cards and beside the description. Cropped to 16:9 (600 × 338).' })),
      h('section', { class: 'ed-card st-danger' },
        h('h2', { class: 'ed-card__title', text: 'Delete project' }),
        kit.note('Removes the project and its photos, videos, embeds and chapters from the site. This can’t be undone.'),
        kit.button('Delete this project', function () {
          kit.act(BASE + 'delete/', {}, { confirm: 'Delete "' + p.name + '"? This can’t be undone.' });
        }))
    ];
  }

  // ------------------------------------------------------------ Write (markdown + preview)

  function writeTabView() {
    var p = ST.project;
    var t = { path: BASE, item: p };
    var ta = h('textarea', { class: 'ed-input st-md', rows: 20, 'aria-label': 'Description (markdown)', spellcheck: 'true' });
    ta.value = p.description || '';
    var preview = h('div', { class: 'prose st-preview' });
    var timer = null;

    function renderPreview() {
      kit.api('preview/', { body: { markdown: ta.value } }).then(function (res) {
        if (!res.ok) { return; }
        if (!res.data.html) { kit.clear(preview); preview.appendChild(kit.note('Nothing to preview yet.')); return; }
        preview.innerHTML = res.data.html;   // rendered and sanitised by the server (markdownify + bleach)
      });
    }
    function changed() {
      p.description = ta.value;
      kit.queueSave(t, 'description', ta.value);
      clearTimeout(timer);
      timer = setTimeout(renderPreview, 450);
    }
    ta.addEventListener('input', changed);

    function fire() { ta.focus(); changed(); }
    function wrapSel(before, after, placeholder) {
      var s = ta.selectionStart, e = ta.selectionEnd;
      var sel = ta.value.slice(s, e) || placeholder;
      ta.setRangeText(before + sel + after, s, e, 'end');
      ta.setSelectionRange(s + before.length, s + before.length + sel.length);
      fire();
    }
    function prefixLines(prefix, numbered) {
      var v = ta.value;
      var s = v.lastIndexOf('\n', ta.selectionStart - 1) + 1;
      var e = v.indexOf('\n', ta.selectionEnd);
      if (e === -1) { e = v.length; }
      var lines = v.slice(s, e).split('\n').map(function (line, i) { return (numbered ? (i + 1) + '. ' : prefix) + line; });
      ta.setRangeText(lines.join('\n'), s, e, 'select');
      fire();
    }
    function insert(text) {
      ta.setRangeText(text, ta.selectionStart, ta.selectionEnd, 'end');
      fire();
    }

    var picker = h('div', { class: 'st-picker', hidden: true });
    if (ST.photos.length) {
      ST.photos.forEach(function (ph) {
        picker.appendChild(h('button', { type: 'button', class: 'st-picker__item', title: ph.caption || 'Insert this photo',
          onclick: function () {
            insert('\n\n![' + (ph.caption || p.name) + '](' + ph.url + ')\n\n');
            picker.hidden = true;
          } }, h('img', { src: ph.url, alt: ph.caption || '' })));
      });
    } else {
      picker.appendChild(kit.note('This project has no photos yet. Add some in the Media tab, then insert them here.'));
    }

    function tool(label, aria, fn) { return h('button', { type: 'button', class: 'st-tool', 'aria-label': aria, title: aria, onclick: fn, text: label }); }
    var toolbar = h('div', { class: 'st-toolbar', role: 'toolbar', 'aria-label': 'Formatting' },
      tool('H2', 'Heading', function () { prefixLines('## '); }),
      tool('H3', 'Subheading', function () { prefixLines('### '); }),
      tool('B', 'Bold', function () { wrapSel('**', '**', 'bold text'); }),
      tool('I', 'Italic', function () { wrapSel('_', '_', 'italic text'); }),
      tool('Link', 'Link', function () { wrapSel('[', '](https://)', 'link text'); }),
      tool('• List', 'Bulleted list', function () { prefixLines('- '); }),
      tool('1. List', 'Numbered list', function () { prefixLines('', true); }),
      tool('“ Quote', 'Quote', function () { prefixLines('> '); }),
      tool('Image', 'Insert a photo', function () { picker.hidden = !picker.hidden; }));

    var mobileToggle = h('div', { class: 'ed-seg st-write__toggle', role: 'group', 'aria-label': 'Show' },
      h('button', { type: 'button', class: 'ed-seg__btn', 'aria-pressed': String(!showPreview), text: 'Write',
                    onclick: function () { showPreview = false; box.classList.remove('show-preview'); this.setAttribute('aria-pressed', 'true'); this.nextSibling.setAttribute('aria-pressed', 'false'); } }),
      h('button', { type: 'button', class: 'ed-seg__btn', 'aria-pressed': String(showPreview), text: 'Preview',
                    onclick: function () { showPreview = true; box.classList.add('show-preview'); this.setAttribute('aria-pressed', 'true'); this.previousSibling.setAttribute('aria-pressed', 'false'); } }));

    var editorField = kit.wrap(BASE, 'description', null, ta, null);
    var box = h('section', { class: 'ed-card st-write' + (showPreview ? ' show-preview' : '') },
      h('div', { class: 'st-write__head' },
        h('h2', { class: 'ed-card__title', text: isBlog() ? 'Article intro' : 'Description' }),
        mobileToggle),
      kit.note(isBlog()
        ? 'The start of the article, shown beside the cover image. The rest goes in Chapters.'
        : 'Shown beside the cover image, above Videos, Photos and Embeds.'),
      h('div', { class: 'st-write__cols' },
        h('div', { class: 'st-write__editor' }, toolbar, picker, editorField,
          h('p', { class: 'ed-hint', text: 'Markdown: ## heading, **bold**, _italic_, [link](https://...), - list, ![caption](image link).' })),
        h('div', { class: 'st-write__preview' }, h('span', { class: 'ed-label', text: 'Preview (as on the live page)' }), preview)));
    renderPreview();
    return [box];
  }

  // ------------------------------------------------------------ Chapters (Blog post cards)

  function cardTarget(c) { return { path: BASE + 'cards/' + c.id + '/', item: c }; }
  function reorderCards(ids) { kit.act(BASE + 'cards/reorder/', { ids: ids }); }

  function chapterPreview(c, i) {
    var el = h('article', { class: 'ed-qcard', 'data-drag': 'chapter', 'data-id': c.id, tabindex: '0', role: 'button',
                            'aria-label': 'Edit chapter ' + (i + 1) + ': ' + c.title },
      kit.dragHandle('chapter'),
      h('div', { class: 'st-chapter' },
        c.image ? h('img', { class: 'st-chapter__img', src: c.image, alt: '' }) : null,
        h('div', {},
          h('span', { class: 'ed-kicker', text: 'Chapter ' + (i + 1) }),
          h('p', { class: 'ed-qcard__q', text: c.title }),
          h('p', { class: 'ed-qcard__help', text: c.teaser }),
          h('div', { class: 'ed-qcard__chips' },
            h('span', { class: 'ed-chip', text: (c.body || '').split(/\s+/).filter(Boolean).length + ' words' }),
            (c.takeaways_raw || '').trim() ? h('span', { class: 'ed-chip', text: c.takeaways_raw.split('\n').filter(function (l) { return l.trim(); }).length + ' takeaways' }) : null))));
    el.addEventListener('click', function (e) { if (!e.target.closest('[data-handle]')) { openCard(c.id); } });
    el.addEventListener('keydown', function (e) { if (e.target === el && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openCard(c.id); } });
    return el;
  }

  function chapterEditor(c, i, ids) {
    var t = cardTarget(c);
    var el = h('article', { class: 'ed-qcard is-active', 'data-drag': 'chapter', 'data-id': c.id },
      kit.dragHandle('chapter'),
      h('span', { class: 'ed-kicker', text: 'Chapter ' + (i + 1) }),
      kit.input(t, 'title', { line: true, lineClass: 'ed-line--q', label: 'Chapter title', maxlength: 100 }),
      kit.input(t, 'teaser', { line: true, label: 'One-line summary (shown on the collapsed chapter)', maxlength: 200 }),
      kit.input(t, 'body', { label: 'Chapter text (markdown)', rows: 8, inputClass: 'st-md' }),
      kit.input(t, 'takeaways_raw', { label: 'Key takeaways (one per line, optional)', rows: 3 }),
      kit.imageField(t, 'image', 'Chapter image (optional)', { wide: true, maxMb: CH.maxImageMb }),
      kit.input(t, 'visual_placeholder', { label: 'Placeholder text for a diagram to add later (optional)', maxlength: 200 }),
      h('div', { class: 'ed-qcard__bar' },
        h('div', { class: 'ed-tools' }, kit.arrows(ids, i, 'chapter', reorderCards)),
        h('div', { class: 'ed-tools' },
          kit.iconButton('✕', 'Delete chapter', function () {
            kit.act(BASE + 'cards/' + c.id + '/delete/', {}, { confirm: 'Delete the chapter "' + c.title + '"?' });
          }),
          h('span', { class: 'ed-divider', 'aria-hidden': 'true' }),
          kit.button('Done', function () { openCard(null); }, { class: 'ed-link ed-done' }))));
    el.addEventListener('keydown', function (e) { if (e.key === 'Escape') { e.preventDefault(); openCard(null); } });
    return el;
  }

  function openCard(id) {
    var prev = activeCard;
    activeCard = id;
    (prev ? kit.flush(BASE + 'cards/' + prev + '/') : Promise.resolve()).then(function () {
      render();
      var sel = id ? '.ed-qcard[data-id="' + id + '"] .ed-line' : (prev ? '.ed-qcard[data-id="' + prev + '"]' : null);
      var target = sel && main.querySelector(sel);
      if (target) { target.focus({ preventScroll: true }); target.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); }
    });
  }

  function importPanel() {
    var ta = h('textarea', { class: 'ed-input st-md', rows: 8, 'aria-label': 'Markdown with chapters to import',
                             placeholder: '<!-- CARD -->\n<!-- TITLE: ... -->\n<!-- TEASER: ... -->\nText...\n<!-- TAKEAWAYS -->\n- Point\n<!-- /CARD -->' });
    var result = h('div', { class: 'st-import__result' });
    function show(data) {
      kit.clear(result);
      if (data.errors && data.errors.length) {
        result.appendChild(h('p', { class: 'ed-err', text: 'Problems to fix first:' }));
        result.appendChild(h('ul', { class: 'st-list' }, data.errors.map(function (e) {
          return h('li', { text: 'Chapter ' + e.index + (e.title ? ' ("' + e.title + '")' : '') + ': ' + e.message });
        })));
      }
      if (data.cards && data.cards.length) {
        result.appendChild(h('p', { class: 'ed-note', text: data.cards.length + ' chapter(s) found:' }));
        result.appendChild(h('ol', { class: 'st-list' }, data.cards.map(function (c) {
          return h('li', { text: c.title + ' (' + c.words + ' words' + (c.takeaways ? ', ' + c.takeaways + ' takeaways' : '') + ')' });
        })));
        if (!(data.errors && data.errors.length)) {
          result.appendChild(h('div', { class: 'ed-add' },
            kit.button('Add to the end', function () { commit(false); }, { class: 'btn btn--primary ed-btn' }),
            data.existing ? kit.button('Replace all ' + data.existing + ' chapters', function () { commit(true); }) : null));
        }
      } else if (!(data.errors && data.errors.length)) {
        result.appendChild(kit.note('No chapters found. Each one starts with <!-- CARD --> and ends with <!-- /CARD -->.'));
      }
    }
    function check() { kit.api(BASE + 'cards/import/', { body: { markdown: ta.value } }).then(function (res) { show(res.data); }); }
    function commit(replace) {
      kit.act(BASE + 'cards/import/', { markdown: ta.value, commit: true, replace: replace },
              replace ? { confirm: 'Replace all existing chapters with these?' } : {});
    }
    return h('details', { class: 'ed-card st-import' },
      h('summary', { class: 'st-new__summary', text: 'Import or export chapters as markdown' }),
      kit.note('Paste chapters written in the template format (for example drafted with an AI assistant), check them, then add them.'),
      ta,
      h('div', { class: 'ed-add' },
        kit.button('Check', check, { class: 'btn btn--primary ed-btn' }),
        h('a', { class: 'btn btn--ghost ed-btn', href: ST.links.export, text: 'Download current chapters (.md)' })),
      result);
  }

  function chaptersTab() {
    var ids = ST.cards.map(function (c) { return c.id; });
    var list = h('div', { class: 'ed-qlist' });
    ST.cards.forEach(function (c, i) { list.appendChild(activeCard === c.id ? chapterEditor(c, i, ids) : chapterPreview(c, i)); });
    kit.enableDrag(list, 'chapter', reorderCards);
    return [
      h('section', { class: 'ed-card ed-card--fixed' },
        h('h2', { class: 'ed-card__title', text: 'Chapters' }),
        kit.note('The article’s sections, shown after the intro as expandable chapters. Click one to edit it; drag ⠇ or use the arrows to reorder.')),
      list,
      h('button', { type: 'button', class: 'ed-addq', onclick: function () {
        kit.act(BASE + 'cards/new/', {}).then(function (data) { if (data && data.item) { openCard(data.item.id); } });
      } }, h('span', { 'aria-hidden': 'true', text: '+' }), ' Add chapter'),
      importPanel()
    ];
  }

  // ------------------------------------------------------------ Media (full editor in the next update)

  function mediaTab() {
    var c = ST.counts;
    return [h('section', { class: 'ed-card' },
      h('h2', { class: 'ed-card__title', text: 'Media' }),
      h('p', { class: 'ed-big' }, h('strong', { text: c.photos }), ' photos · ', h('strong', { text: c.videos }), ' videos · ',
        h('strong', { text: c.embeds }), ' embeds'),
      kit.note('Uploading and arranging photos, videos and embeds here is coming in the next Studio update. Until then, use the admin.'),
      h('div', { class: 'ed-add' }, h('a', { class: 'btn btn--ghost ed-btn', href: ST.links.admin, text: 'Edit media in the admin' })))];
  }

  // ------------------------------------------------------------ page

  function render() {
    var scroll = window.scrollY;
    var list = tabs().map(function (x) { return x[0]; });
    if (list.indexOf(tab) === -1) { tab = 'details'; }
    titleEl.textContent = ST.project.name;
    previewLink.href = ST.links.public;
    previewLink.hidden = false;
    kit.clear(main);
    var bar = h('nav', { class: 'st-subtabs', 'aria-label': 'Project sections' }, tabs().map(function (x) {
      return h('button', { type: 'button', class: 'st-subtab', 'aria-current': x[0] === tab ? 'page' : 'false', text: x[1],
                           onclick: function () { kit.flushAll().then(function () { tab = x[0]; writeTab(tab); activeCard = null; render(); window.scrollTo(0, 0); }); } });
    }));
    main.appendChild(h('div', { class: 'st-crumbs' },
      h('a', { href: ST.links.projects, text: '← All projects' }),
      h('span', { class: 'ed-chip', text: isBlog() ? 'Blog post' : 'Portfolio' }),
      ST.project.featured ? h('span', { class: 'ed-chip st-chip--star', text: '★ Featured' }) : null));
    main.appendChild(bar);
    var content = { details: detailsTab, write: writeTabView, chapters: chaptersTab, media: mediaTab }[tab]();
    content.forEach(function (node) { if (node) { main.appendChild(node); } });
    window.scrollTo(0, scroll);
  }

  refresh();
})();
