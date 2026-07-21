document.addEventListener('DOMContentLoaded', function () {
    const modeSelect = document.querySelector('#id_display_mode');
    if (!modeSelect) return;

    const photoGroup = document.querySelector('#photos-group');
    const videoGroup = document.querySelector('#videos-group');
    const embedGroup = document.querySelector('#embeds-group');
    const cardGroup = document.querySelector('#cards-group');
    const techRow = document.querySelector('.field-technologies');

    // Build the toggle UI and insert it before the select's parent row
    const row = modeSelect.closest('.form-row, .field-display_mode, tr, li') || modeSelect.parentElement;

    const toggle = document.createElement('div');
    toggle.className = 'am-mode-toggle';
    toggle.innerHTML = `
        <span class="am-mode-label">Content Mode</span>
        <div class="am-mode-btn-group">
            <button type="button" data-mode="portfolio" class="am-mode-btn">
                <span>&#128230;</span> Portfolio
            </button>
            <button type="button" data-mode="blogpost" class="am-mode-btn">
                <span>&#9997;&#65039;</span> Blog Post
            </button>
        </div>
        <p class="am-mode-hint"></p>
    `;
    row.parentElement.insertBefore(toggle, row);
    row.style.display = 'none'; // hide the raw select — value is synced via buttons

    const buttons = toggle.querySelectorAll('.am-mode-btn');
    const hint = toggle.querySelector('.am-mode-hint');

    const HINTS = {
        portfolio: 'Media (photos, videos, embeds) displays in separate sections below the description.',
        blogpost: 'Only the description is rendered. Upload photos below to get their markdown snippets, then paste them inline.'
    };

    const PHOTO_LABELS = {
        portfolio: 'Project Photos',
        blogpost: 'Media Library — upload images here, then copy the markdown snippet into the description'
    };

    function applyMode(mode) {
        buttons.forEach(btn => btn.classList.toggle('active', btn.dataset.mode === mode));
        hint.textContent = HINTS[mode] || '';

        if (photoGroup) {
            const h2 = photoGroup.querySelector('h2');
            if (h2) h2.textContent = PHOTO_LABELS[mode] || h2.textContent;
        }

        if (videoGroup) videoGroup.style.display = mode === 'blogpost' ? 'none' : '';
        if (embedGroup) embedGroup.style.display = mode === 'blogpost' ? 'none' : '';
        if (cardGroup) cardGroup.style.display = mode === 'blogpost' ? '' : 'none';
        if (techRow) techRow.style.display = mode === 'blogpost' ? 'none' : '';
    }

    buttons.forEach(btn => {
        btn.addEventListener('click', function () {
            modeSelect.value = this.dataset.mode;
            applyMode(this.dataset.mode);
        });
    });

    // Initialise to current saved value
    applyMode(modeSelect.value || 'portfolio');
});
