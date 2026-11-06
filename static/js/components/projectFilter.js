// Projects page category filter.
// Shows only the cards in the chosen category, hides years left empty,
// updates the counts, and keeps the choice in the URL (?category=...) so a
// filtered view can be shared or reloaded. Without JavaScript the filter row
// stays hidden and every project shows.
(function () {
    const filter = document.querySelector('[data-project-filter]');
    if (!filter) return;

    const buttons = [...filter.querySelectorAll('[data-filter]')];
    const cards = [...document.querySelectorAll('[data-category]')];
    const groups = [...document.querySelectorAll('[data-year-group]')];
    const total = document.querySelector('[data-filter-total]');
    const status = filter.querySelector('[data-filter-status]');
    const known = new Set(buttons.map((b) => b.dataset.filter));

    const plural = (n) => `${n} project${n === 1 ? '' : 's'}`;

    function apply(slug, { updateUrl = true } = {}) {
        if (!known.has(slug)) slug = 'all';

        cards.forEach((card) => {
            card.hidden = slug !== 'all' && card.dataset.category !== slug;
        });

        let shown = 0;
        groups.forEach((group) => {
            const visible = group.querySelectorAll('[data-category]:not([hidden])').length;
            group.hidden = visible === 0;
            const count = group.querySelector('[data-year-count]');
            if (count) count.textContent = plural(visible);
            shown += visible;
        });

        buttons.forEach((button) => {
            const active = button.dataset.filter === slug;
            button.classList.toggle('is-active', active);
            button.setAttribute('aria-pressed', String(active));
        });

        if (total) total.textContent = plural(shown);
        if (status) {
            const name = buttons.find((b) => b.dataset.filter === slug)?.firstChild.textContent.trim();
            status.textContent = slug === 'all' ? `Showing all ${plural(shown)}` : `Showing ${plural(shown)} in ${name}`;
        }

        if (updateUrl) {
            const url = new URL(window.location.href);
            if (slug === 'all') url.searchParams.delete('category');
            else url.searchParams.set('category', slug);
            window.history.replaceState(null, '', url);
        }
    }

    filter.addEventListener('click', (event) => {
        const button = event.target.closest('[data-filter]');
        if (!button) return;
        apply(button.dataset.filter);
        // On phones the row scrolls sideways: keep the chosen filter in view.
        button.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    });

    filter.hidden = false;
    const fromUrl = new URL(window.location.href).searchParams.get('category');
    // A link to an unknown category falls back to All and tidies the address bar.
    if (fromUrl) apply(fromUrl, { updateUrl: !known.has(fromUrl) });
})();
