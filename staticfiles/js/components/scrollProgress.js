/**
 * Reading progress bar - thin line fixed to the top of the viewport that
 * fills left-to-right as the page scrolls. See components/_scroll-progress.scss.
 */
(function () {
    function initScrollProgress(bar) {
        let ticking = false;

        function updateBar() {
            const scrollTop = window.scrollY || document.documentElement.scrollTop;
            const scrollable = document.documentElement.scrollHeight - window.innerHeight;
            const progress = scrollable > 0 ? (scrollTop / scrollable) * 100 : 0;
            bar.style.width = Math.min(100, Math.max(0, progress)) + '%';
            ticking = false;
        }

        function onScroll() {
            if (!ticking) {
                window.requestAnimationFrame(updateBar);
                ticking = true;
            }
        }

        window.addEventListener('scroll', onScroll, { passive: true });
        window.addEventListener('resize', onScroll);
        updateBar();
    }

    document.addEventListener('DOMContentLoaded', () => {
        const bar = document.querySelector('.scroll-progress__bar');
        if (bar) initScrollProgress(bar);
    });
})();
