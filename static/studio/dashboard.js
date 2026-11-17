/* Studio dashboard: counts, shortcuts and recent edits. */
(function () {
  'use strict';
  var kit = StudioKit.create({ api: '/studio/api/' });
  var h = kit.h;
  var main = document.getElementById('ed-main');

  function tile(label, value, href) {
    return h('a', { class: 'st-tile', href: href },
      h('span', { class: 'st-tile__value', text: value }),
      h('span', { class: 'st-tile__label', text: label }));
  }

  function shortcut(title, text, href, external) {
    return h('a', { class: 'st-shortcut', href: href, target: external ? '_blank' : null, rel: external ? 'noopener' : null },
      h('span', { class: 'st-shortcut__title', text: title + (external ? ' ↗' : '') }),
      h('span', { class: 'st-shortcut__text', text: text }));
  }

  kit.api('dashboard/', { method: 'GET' }).then(function (res) {
    kit.clear(main);
    if (!res.ok) {
      main.appendChild(h('p', { class: 'ed-banner', text: res.data.error || 'Studio couldn’t load. Reload the page.' }));
      return;
    }
    var d = res.data;
    var c = d.counts;
    var L = d.links;
    main.appendChild(h('section', { class: 'st-hero' },
      h('h1', { class: 'st-h1', text: 'Welcome back' }),
      kit.note('Everything on your site in one place. Changes save themselves and go live straight away.')));
    main.appendChild(h('div', { class: 'st-tiles' },
      tile('Projects', c.total, L.projects),
      tile('Featured on home', c.featured, L.projects + '?featured=1'),
      tile('Portfolio', c.portfolio, L.projects + '?mode=portfolio'),
      tile('Blog posts', c.blog, L.projects + '?mode=blogpost')));
    main.appendChild(h('section', { class: 'ed-card' },
      h('h2', { class: 'ed-card__title', text: 'Shortcuts' }),
      h('div', { class: 'st-shortcuts' },
        shortcut('+ New project', 'Start a portfolio piece or a blog post', L.projects + '?new=1'),
        shortcut('About page', 'Experience and Education', L.about),
        shortcut('Survey editor', 'Think Before You Prompt', L.survey),
        shortcut('View site', 'adhenzmiranda.com', L.site, true),
        shortcut('Django admin', 'Backup, users and 2FA devices', L.admin))));
    if (d.recent.length) {
      main.appendChild(h('section', { class: 'ed-card' },
        h('h2', { class: 'ed-card__title', text: 'Recently edited' }),
        h('ul', { class: 'st-recent' }, d.recent.map(function (p) {
          return h('li', {},
            h('a', { href: p.editor, class: 'st-recent__link' },
              p.thumbnail ? h('img', { src: p.thumbnail, alt: '', class: 'st-recent__img' }) : h('span', { class: 'st-recent__img st-recent__img--empty' }),
              h('span', { class: 'st-recent__name', text: p.name }),
              h('span', { class: 'st-recent__meta', text: (p.mode === 'blogpost' ? 'Blog post' : 'Portfolio') + ' · ' + p.year })));
        }))));
    }
  });
})();
