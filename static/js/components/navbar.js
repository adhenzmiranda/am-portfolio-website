// Site header behaviour:
// - hides the header while scrolling down and brings it back on scroll up
// - gives the header a backing once the page has scrolled
// - opens and closes the full-screen phone menu
(function () {
    const header = document.querySelector('[data-site-header]');
    const toggle = document.querySelector('.toggle-nav-btn');
    const menu = document.getElementById('mobile-menu');
    if (!header) return;

    // ------------------------------------------------------------ Scroll
    const SHOW_BACKING_AFTER = 10;   // px scrolled before the bar gets a background
    const MIN_DELTA = 6;             // ignore tiny scroll jitters
    let lastY = window.scrollY;
    let ticking = false;

    function onScroll() {
        const y = Math.max(window.scrollY, 0);
        header.classList.toggle('is-scrolled', y > SHOW_BACKING_AFTER);

        if (!document.body.classList.contains('menu-open') && Math.abs(y - lastY) > MIN_DELTA) {
            const goingDown = y > lastY;
            header.classList.toggle('is-hidden', goingDown && y > header.offsetHeight);
            lastY = y;
        }
        ticking = false;
    }

    window.addEventListener('scroll', () => {
        if (!ticking) {
            ticking = true;
            window.requestAnimationFrame(onScroll);
        }
    }, { passive: true });
    onScroll();

    // Keyboard users tabbing into a hidden header should see it.
    header.addEventListener('focusin', () => header.classList.remove('is-hidden'));

    // ------------------------------------------------------------ Phone menu
    if (!toggle || !menu) return;
    const label = toggle.querySelector('.toggle-nav-btn__label');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

    function openMenu() {
        menu.hidden = false;
        // Next frame so the opening transition runs after display changes.
        window.requestAnimationFrame(() => menu.classList.add('is-open'));
        document.body.classList.add('menu-open');
        header.classList.remove('is-hidden');
        toggle.setAttribute('aria-expanded', 'true');
        if (label) label.textContent = 'Close menu';
        const first = menu.querySelector('a');
        if (first) first.focus({ preventScroll: true });
    }

    function closeMenu({ returnFocus = true } = {}) {
        if (menu.hidden) return;
        menu.classList.remove('is-open');
        document.body.classList.remove('menu-open');
        toggle.setAttribute('aria-expanded', 'false');
        if (label) label.textContent = 'Open menu';
        const hide = () => { menu.hidden = true; };
        if (reduceMotion.matches) hide(); else window.setTimeout(hide, 300);
        if (returnFocus) toggle.focus({ preventScroll: true });
    }

    toggle.addEventListener('click', () => {
        if (toggle.getAttribute('aria-expanded') === 'true') closeMenu(); else openMenu();
    });

    // Close when a menu link is followed, on Escape, or when the screen grows past phone size.
    menu.addEventListener('click', (event) => {
        if (event.target.closest('a')) closeMenu({ returnFocus: false });
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') closeMenu();
    });
    window.matchMedia('(min-width: 441px)').addEventListener('change', (event) => {
        if (event.matches) closeMenu({ returnFocus: false });
    });
})();
