/* Studio: all projects. Search and filters run in the browser; "+ New project" creates one and opens it. */
(function () {
  'use strict';
  var kit = StudioKit.create({ api: '/studio/api/' });
  var h = kit.h;
  var main = document.getElementById('ed-main');
  var params = new URLSearchParams(location.search);
  // Filters start from the link (e.g. ?mode=blogpost from the dashboard); values are only compared, never shown.
  var filters = {
    q: '',
    category: '',
    mode: ['portfolio', 'blogpost'].indexOf(params.get('mode')) !== -1 ? params.get('mode') : '',
    featured: params.get('featured') === '1' ? '1' : ''
  };
  var DATA = null;

  function load() {
    return kit.api('projects/', { method: 'GET' }).then(function (res) {
      if (!res.ok) {
        kit.clear(main);
        main.appendChild(h('p', { class: 'ed-banner', text: res.data.error || 'Couldn’t load the projects.' }));
        return;
      }
      DATA = res.data;
      render();
    });
  }

  function matches(p) {
    if (filters.q && (p.name + ' ' + p.category + ' ' + p.year).toLowerCase().indexOf(filters.q.toLowerCase()) === -1) { return false; }
    if (filters.category && String(p.category_id) !== filters.category) { return false; }
    if (filters.mode && p.mode !== filters.mode) { return false; }
    if (filters.featured && !p.featured) { return false; }
    return true;
  }

  function filterSelect(key, label, choices) {
    var el = h('select', { class: 'ed-input ed-select', 'aria-label': label });
    choices.forEach(function (c) { el.appendChild(h('option', { value: c[0], text: c[1], selected: filters[key] === c[0] })); });
    el.addEventListener('change', function () { filters[key] = el.value; drawGrid(); });
    return el;
  }

  var grid = null;
  var countEl = null;

  function card(p) {
    return h('a', { class: 'st-pcard', href: p.editor },
      p.thumbnail ? h('img', { class: 'st-pcard__img', src: p.thumbnail, alt: '', loading: 'lazy' })
                  : h('span', { class: 'st-pcard__img st-pcard__img--empty', text: 'No cover image' }),
      h('span', { class: 'st-pcard__body' },
        h('span', { class: 'st-pcard__name', text: p.name }),
        h('span', { class: 'st-pcard__meta', text: p.year + (p.category ? ' · ' + p.category : '') }),
        h('span', { class: 'st-pcard__badges' },
          h('span', { class: 'ed-chip', text: p.mode === 'blogpost' ? 'Blog post' : 'Portfolio' }),
          p.featured ? h('span', { class: 'ed-chip st-chip--star', text: '★ Featured' }) : null)));
  }

  function drawGrid() {
    var shown = DATA.projects.filter(matches);
    kit.clear(grid);
    shown.forEach(function (p) { grid.appendChild(card(p)); });
    if (!shown.length) { grid.appendChild(kit.note('No projects match. Clear the search or filters.')); }
    countEl.textContent = shown.length + ' of ' + DATA.projects.length + ' projects';
  }

  function newProjectBox(open) {
    var name = h('input', { class: 'ed-input', type: 'text', maxlength: 255, placeholder: 'Project name', 'aria-label': 'New project name' });
    var mode = 'portfolio';
    var modeGroup = h('div', { class: 'ed-seg', role: 'group', 'aria-label': 'Type' });
    DATA.modes.forEach(function (m) {
      var b = h('button', { type: 'button', class: 'ed-seg__btn', 'aria-pressed': String(m[0] === mode), text: m[1] });
      b.addEventListener('click', function () {
        mode = m[0];
        modeGroup.querySelectorAll('.ed-seg__btn').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
      });
      modeGroup.appendChild(b);
    });
    var err = h('p', { class: 'ed-err', role: 'alert' });
    var create = kit.button('Create and open', function () {
      err.textContent = '';
      kit.api('projects/new/', { body: { name: name.value, mode: mode } }).then(function (res) {
        if (res.ok) { location.assign(res.data.project.editor); return; }
        err.textContent = res.data.error || ((res.data.errors && Object.values(res.data.errors)[0].join(' ')) || 'Couldn’t create it.');
      });
    }, { class: 'btn btn--primary ed-btn' });
    name.addEventListener('keydown', function (e) { if (e.key === 'Enter') { create.click(); } });
    var box = h('details', { class: 'ed-card st-new', open: open },
      h('summary', { class: 'st-new__summary', text: '+ New project' }),
      h('div', { class: 'st-new__row' }, name, modeGroup, create), err,
      kit.note('Portfolio: photos, videos and embeds in sections. Blog post: an article with chapters. You can switch later.'));
    if (open) { requestAnimationFrame(function () { name.focus(); }); }
    return box;
  }

  function render() {
    kit.clear(main);
    var search = h('input', { class: 'ed-input', type: 'search', placeholder: 'Search projects', 'aria-label': 'Search projects', value: filters.q });
    search.addEventListener('input', function () { filters.q = search.value; drawGrid(); });
    countEl = h('span', { class: 'ed-note st-count' });
    grid = h('div', { class: 'st-grid' });
    main.appendChild(newProjectBox(params.get('new') === '1'));
    main.appendChild(h('div', { class: 'st-filters' },
      search,
      filterSelect('category', 'Category', [['', 'All categories']].concat(DATA.categories.map(function (c) { return [String(c[0]), c[1]]; }))),
      filterSelect('mode', 'Type', [['', 'All types'], ['portfolio', 'Portfolio'], ['blogpost', 'Blog posts']]),
      filterSelect('featured', 'Featured', [['', 'Featured or not'], ['1', 'Featured only']])));
    main.appendChild(countEl);
    main.appendChild(grid);
    drawGrid();
  }

  load();
})();
