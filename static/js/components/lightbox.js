// Project media lightbox.
// Opens videos, photos and embeds full screen with their title, in page order.
// Keyboard: arrows to move, Esc to close, Tab stays inside. Touch: swipe to move.
// Videos play in Plyr (static/vendor/plyr), themed in _lightbox.scss; if Plyr is
// unavailable they fall back to the browser's own controls.
(function () {
    // Set while this script runs; the template passes the local icon sprite path.
    const PLYR_ICONS = document.currentScript?.dataset.plyrIcons || '';
    const SELECTOR = '.video-item, .gallery-item, .embed-item';
    const nodes = [...document.querySelectorAll(SELECTOR)];
    if (!nodes.length) return;

    // ------------------------------------------------------------ Collect media
    const items = nodes.map((node) => {
        if (node.classList.contains('video-item')) {
            const video = node.querySelector('video');
            return {
                node, type: 'video',
                src: video.querySelector('source')?.src || video.src,
                poster: video.poster,
                title: node.querySelector('.media-tile__title')?.textContent.trim() || '',
            };
        }
        if (node.classList.contains('gallery-item')) {
            const img = node.querySelector('img');
            return {
                node, type: 'photo',
                src: img.dataset.full || img.src,
                alt: img.alt,
                title: node.querySelector('.gallery-caption')?.textContent.trim() || '',
            };
        }
        const iframe = node.querySelector('iframe');
        const frame = node.querySelector('.embed-item__frame');
        return {
            node, type: 'embed',
            src: iframe ? iframe.src : '',
            shape: [...(frame?.classList || [])].find((c) => c.startsWith('embed-item__frame--'))?.replace('embed-item__frame--', '') || 'wide',
            title: node.querySelector('.embed-caption')?.textContent.trim() || '',
        };
    }).filter((item) => item.src);
    if (!items.length) return;

    // ------------------------------------------------------------ Build the dialog
    document.body.insertAdjacentHTML('beforeend', `
        <div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="Media viewer" hidden>
            <div class="lightbox__bar">
                <p class="lightbox__counter" aria-live="polite"></p>
                <button type="button" class="lightbox__close">Close <span aria-hidden="true">&#10005;</span></button>
            </div>
            <div class="lightbox__stage"></div>
            <div class="lightbox__footer">
                <p class="lightbox__title"></p>
                <div class="lightbox__nav">
                    <button type="button" class="lightbox__btn lightbox__prev" aria-label="Previous"><span aria-hidden="true">&larr;</span></button>
                    <button type="button" class="lightbox__btn lightbox__next" aria-label="Next"><span aria-hidden="true">&rarr;</span></button>
                </div>
            </div>
        </div>`);

    const box = document.getElementById('lightbox');
    const stage = box.querySelector('.lightbox__stage');
    const counter = box.querySelector('.lightbox__counter');
    const titleEl = box.querySelector('.lightbox__title');
    const closeBtn = box.querySelector('.lightbox__close');
    const nav = box.querySelector('.lightbox__nav');
    const pad = (n) => String(n).padStart(2, '0');
    let index = 0;
    let opener = null;
    let player = null; // current Plyr instance

    const PLYR_OPTIONS = {
        iconUrl: PLYR_ICONS,  // local sprite, not cdn.plyr.io
        blankVideo: '',       // used when a player is destroyed; empty = no request to cdn.plyr.io
        controls: ['play', 'progress', 'current-time', 'duration', 'mute', 'volume', 'settings', 'pip', 'fullscreen'],
        settings: ['speed'],
        speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] },
        tooltips: { controls: false, seek: true },
        keyboard: { focused: true, global: false },
        fullscreen: { enabled: true, iosNative: true },
        storage: { enabled: false }, // don't write volume/speed to localStorage
        hideControls: true,
        resetOnEnd: true,
    };

    function destroyPlayer() {
        if (player) {
            player.destroy();
            player = null;
        }
    }

    if (items.length < 2) nav.hidden = true;

    function render() {
        const item = items[index];
        destroyPlayer();
        stage.replaceChildren(); // also stops any video or embed that was playing
        let media;
        let video = null;
        if (item.type === 'photo') {
            media = document.createElement('img');
            media.src = item.src;
            media.alt = item.alt || item.title;
            media.decoding = 'async';
        } else if (item.type === 'video') {
            // fit() sizes this wrapper; Plyr builds its controls inside it.
            media = document.createElement('div');
            media.className = 'lightbox__player';
            video = document.createElement('video');
            video.src = item.src;
            video.poster = item.poster;
            video.playsInline = true;
            video.controls = !window.Plyr; // native controls only if Plyr didn't load
            media.appendChild(video);
        } else {
            media = document.createElement('div');
            media.className = `lightbox__embed lightbox__embed--${item.shape}`;
            const iframe = document.createElement('iframe');
            iframe.src = item.src;
            iframe.title = item.title || 'Embedded work';
            // Same restrictions as the iframes on the page.
            iframe.setAttribute('sandbox', 'allow-scripts allow-same-origin allow-presentation allow-popups');
            iframe.setAttribute('allow', 'fullscreen');
            iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
            iframe.allowFullscreen = true;
            media.appendChild(iframe);
        }
        media.classList.add('lightbox__media');
        // Hidden until its real size is known, then scaled to fit (see fit()).
        media.classList.add('is-sizing');
        if (item.type === 'photo') media.addEventListener('load', fit, { once: true });
        if (item.type === 'video') video.addEventListener('loadedmetadata', fit, { once: true });
        // If it can't load, show whatever the browser can (alt text / poster) rather than nothing.
        (video || media).addEventListener('error', () => media.classList.remove('is-sizing'), { once: true });
        stage.appendChild(media);
        if (video) {
            if (window.Plyr) player = new window.Plyr(video, PLYR_OPTIONS);
            // Opened by a click, so playing straight away is expected.
            const playing = video.play();
            if (playing) playing.catch(() => {});
        }
        if (item.type === 'embed' || (item.type === 'photo' && media.complete)) fit();

        const label = { video: 'Video', photo: 'Photo', embed: 'Embed' }[item.type];
        counter.textContent = `${pad(index + 1)} / ${pad(items.length)} · ${label}`;
        titleEl.textContent = item.title;

        // Warm up the neighbouring photos so moving through them feels instant.
        [index - 1, index + 1].forEach((i) => {
            const next = items[(i + items.length) % items.length];
            if (next.type === 'photo') new Image().src = next.src;
        });
    }

    // Platform shapes for embeds (width / height); everything else uses its own size.
    const EMBED_RATIOS = { wide: 16 / 9, itch: 552 / 167, linkedin: 504 / 600 };

    // Scale the current item to the largest size that fits the space between the bars
    // while keeping its own proportions. Photos are never enlarged past their real size.
    function fit() {
        const media = stage.querySelector('.lightbox__media');
        if (!media) return;
        const item = items[index];
        let w;
        let h;
        if (item.type === 'photo') { w = media.naturalWidth; h = media.naturalHeight; }
        else if (item.type === 'video') { const v = media.querySelector('video'); w = v.videoWidth; h = v.videoHeight; }
        else { w = EMBED_RATIOS[item.shape] || EMBED_RATIOS.wide; h = 1; }
        if (!w || !h) return; // size not known yet: stay hidden until load / loadedmetadata

        const style = getComputedStyle(stage);
        const availW = stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
        const availH = stage.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
        let scale = Math.min(availW / w, availH / h);
        if (item.type === 'photo') scale = Math.min(scale, 1);
        if (item.type === 'embed') scale = Math.min(scale, 1280 / w); // cap very wide screens

        media.style.width = `${Math.floor(w * scale)}px`;
        media.style.height = `${Math.floor(h * scale)}px`;
        media.classList.remove('is-sizing');
    }

    if ('ResizeObserver' in window) new ResizeObserver(() => { if (!box.hidden) fit(); }).observe(stage);
    else window.addEventListener('resize', () => { if (!box.hidden) fit(); });

    function open(i, trigger) {
        index = i;
        opener = trigger || items[i].node;
        // Pause anything playing on the page behind.
        document.querySelectorAll('video').forEach((v) => { if (!box.contains(v)) v.pause(); });
        render();
        box.hidden = false;
        requestAnimationFrame(() => box.classList.add('is-open'));
        document.body.classList.add('lightbox-open');
        closeBtn.focus({ preventScroll: true });
    }

    function close() {
        box.classList.remove('is-open');
        box.hidden = true;
        destroyPlayer();
        stage.replaceChildren();
        document.body.classList.remove('lightbox-open');
        if (opener) opener.focus({ preventScroll: true });
    }

    function move(step) {
        index = (index + step + items.length) % items.length;
        render();
    }

    // ------------------------------------------------------------ Open from the page
    items.forEach((item, i) => {
        if (item.type === 'embed') {
            // Embeds are interactive in place; only their Expand button opens the viewer.
            const button = item.node.querySelector('[data-lightbox-open]');
            if (button) button.addEventListener('click', () => open(i, button));
            return;
        }
        const { node } = item;
        node.tabIndex = 0;
        node.setAttribute('role', 'button');
        node.setAttribute('aria-label', `Open ${item.type}${item.title ? `: ${item.title}` : ''}`);
        node.addEventListener('click', () => open(i, node));
        node.addEventListener('keydown', (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                open(i, node);
            }
        });
    });

    // ------------------------------------------------------------ Controls
    closeBtn.addEventListener('click', close);
    box.querySelector('.lightbox__prev').addEventListener('click', () => move(-1));
    box.querySelector('.lightbox__next').addEventListener('click', () => move(1));

    // Clicking the empty space around the media closes it.
    stage.addEventListener('click', (event) => {
        if (event.target === stage) close();
    });

    // Capture phase: a focused <video> keeps Escape to itself otherwise.
    document.addEventListener('keydown', (event) => {
        if (box.hidden) return;
        // While the video player has focus, the arrow keys seek within the video.
        const inPlayer = Boolean(document.activeElement?.closest('.plyr, video'));
        if (event.key === 'Escape') {
            // An open player menu (e.g. speed) closes first; the next Escape closes the viewer.
            if (box.querySelector('.plyr__menu__container:not([hidden])')) return;
            event.preventDefault();
            close();
        }
        else if (event.key === 'ArrowLeft' && items.length > 1 && !inPlayer) move(-1);
        else if (event.key === 'ArrowRight' && items.length > 1 && !inPlayer) move(1);
        else if (event.key === 'Tab') {
            // Keep keyboard focus inside the viewer.
            const focusable = [...box.querySelectorAll('button, input, video, iframe')]
                .filter((el) => !el.closest('[hidden]') && el.offsetParent !== null);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    }, true);

    // Swipe left/right on touch screens (not over embeds, which need their own touches).
    let startX = null;
    let startY = null;
    stage.addEventListener('touchstart', (event) => {
        if (event.target.closest('.lightbox__embed, .plyr__controls, .plyr__menu') || event.touches.length !== 1) { startX = null; return; }
        startX = event.touches[0].clientX;
        startY = event.touches[0].clientY;
    }, { passive: true });
    stage.addEventListener('touchend', (event) => {
        if (startX === null || items.length < 2) return;
        const dx = event.changedTouches[0].clientX - startX;
        const dy = event.changedTouches[0].clientY - startY;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) move(dx < 0 ? 1 : -1);
        startX = null;
    }, { passive: true });
})();
