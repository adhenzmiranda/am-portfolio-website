// Blog-post chapters (templates/components/chapters.html).
//
// Desktop (1024px+): "pane" mode. The chapter index stays on the left; clicking a
// chapter shows it in the reading pane on the right, with Previous / Next below it.
// Smaller screens: "accordion" mode. Each chapter is a row that opens in place.
//
// Hover only changes colours (in CSS); nothing here runs on hover, so the layout
// never moves until something is clicked. The open chapter is kept in the URL
// (#chapter-3) so it can be linked to. Without JavaScript every chapter shows in full.
(function () {
    const root = document.querySelector('[data-chapters]');
    if (!root) return;

    const chapters = [...root.querySelectorAll('[data-chapter]')];
    const indexLinks = [...root.querySelectorAll('.chapters__index [data-chapter-link]')];
    if (!chapters.length) return;

    const desktop = window.matchMedia('(min-width: 1024px)');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const count = chapters.length;
    let current = 1;

    // Fill in the Previous / Next chapter names from the index.
    const nameOf = (n) => {
        const link = indexLinks[n - 1];
        return link ? `${link.querySelector('.chapters__num').textContent} · ${link.querySelector('.chapters__name').textContent}` : '';
    };
    root.querySelectorAll('[data-chapter-name-of]').forEach((el) => {
        el.textContent = nameOf(Number(el.dataset.chapterNameOf));
    });

    // Accordion mode turns each chapter title into a toggle button; pane mode puts the
    // plain heading back (a button that does nothing would mislead screen readers).
    const toggles = chapters.map((chapter) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chapter__toggle';
        button.setAttribute('aria-expanded', 'false');
        button.setAttribute('aria-controls', chapter.querySelector('.chapter__body').id);
        const icon = document.createElement('span');
        icon.className = 'chapter__icon';
        icon.setAttribute('aria-hidden', 'true');
        button.append(icon);
        button.addEventListener('click', () => toggle(Number(chapter.dataset.chapter)));
        return button;
    });

    function useToggles(on) {
        chapters.forEach((chapter, i) => {
            const title = chapter.querySelector('.chapter__title');
            const button = toggles[i];
            const icon = button.querySelector('.chapter__icon');
            if (on && !button.isConnected) {
                button.prepend(...title.childNodes);
                title.append(button);
            } else if (!on && button.isConnected) {
                title.append(...[...button.childNodes].filter((node) => node !== icon));
                button.remove();
            }
        });
    }

    const numberFromHash = () => {
        const match = window.location.hash.match(/^#chapter-(\d+)$/);
        const n = match ? Number(match[1]) : 0;
        return n >= 1 && n <= count ? n : 0;
    };

    const setHash = (n) => {
        const url = new URL(window.location.href);
        url.hash = n ? `chapter-${n}` : '';
        window.history.replaceState(null, '', url);
    };

    // ------------------------------------------------------------ Pane mode (desktop)
    function show(n, { focus = false, scroll = false, updateUrl = true } = {}) {
        current = n;
        chapters.forEach((chapter) => {
            chapter.hidden = Number(chapter.dataset.chapter) !== n;
        });
        indexLinks.forEach((link) => {
            const active = Number(link.dataset.chapterLink) === n;
            link.classList.toggle('is-active', active);
            if (active) link.setAttribute('aria-current', 'true');
            else link.removeAttribute('aria-current');
        });
        if (updateUrl) setHash(n);
        const chapter = chapters[n - 1];
        // If the top of the pane is above the screen (e.g. after reading a long chapter),
        // bring it back into view so the new chapter starts at its beginning.
        if (scroll && root.getBoundingClientRect().top < 0) {
            root.scrollIntoView({ behavior: reduceMotion.matches ? 'auto' : 'smooth', block: 'start' });
        }
        if (focus) chapter.querySelector('.chapter__title').focus({ preventScroll: true });
    }

    // ------------------------------------------------------------ Accordion mode
    function setOpen(chapter, open) {
        chapter.classList.toggle('is-open', open);
        toggles[Number(chapter.dataset.chapter) - 1].setAttribute('aria-expanded', String(open));
    }

    function toggle(n) {
        if (desktop.matches) return; // titles aren't toggles in pane mode
        const chapter = chapters[n - 1];
        const open = !chapter.classList.contains('is-open');
        setOpen(chapter, open);
        setHash(open ? n : 0);
    }

    // ------------------------------------------------------------ Mode switching
    function applyMode() {
        const fromHash = numberFromHash();
        if (desktop.matches) {
            root.classList.add('is-pane');
            root.classList.remove('is-accordion');
            useToggles(false);
            chapters.forEach((chapter) => setOpen(chapter, false));
            // Only touch the address when a chapter was actually asked for.
            show(fromHash || current, { updateUrl: Boolean(fromHash) });
        } else {
            root.classList.add('is-accordion');
            root.classList.remove('is-pane');
            useToggles(true);
            chapters.forEach((chapter) => { chapter.hidden = false; });
            chapters.forEach((chapter, i) => setOpen(chapter, i + 1 === fromHash));
        }
    }

    // Index links and Previous / Next: switch chapters in pane mode, jump in accordion mode.
    root.addEventListener('click', (event) => {
        const link = event.target.closest('[data-chapter-link]');
        if (!link) return;
        const n = Number(link.dataset.chapterLink);
        event.preventDefault();
        if (desktop.matches) {
            const fromPager = Boolean(link.closest('.chapter__pager'));
            show(n, { focus: fromPager, scroll: fromPager });
        } else {
            const chapter = chapters[n - 1];
            setOpen(chapter, true);
            setHash(n);
            chapter.scrollIntoView({ behavior: reduceMotion.matches ? 'auto' : 'smooth', block: 'start' });
        }
    });

    // Chapter titles can take focus (for moving focus after Previous / Next).
    chapters.forEach((chapter) => chapter.querySelector('.chapter__title').setAttribute('tabindex', '-1'));

    root.classList.add('js-enabled');
    applyMode();
    desktop.addEventListener('change', applyMode);
    window.addEventListener('hashchange', () => {
        const n = numberFromHash();
        if (!n) return;
        if (desktop.matches) show(n);
        else setOpen(chapters[n - 1], true);
    });
})();
