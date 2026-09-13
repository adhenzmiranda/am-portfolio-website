document.addEventListener('DOMContentLoaded', function () {
    if (!window.AM_IMPORT_URLS) return; // only present on the change page (existing project)

    const cardGroup = document.querySelector('#cards-group');
    if (!cardGroup || document.getElementById('amImportBanner')) return;

    const banner = document.createElement('div');
    banner.id = 'amImportBanner';
    banner.className = 'am-import-banner';
    banner.innerHTML = `
        <p class="am-import-banner__title">📝 Import / Export Sections as Markdown</p>
        <p class="am-import-banner__warning">
            ⚠️ <strong>The file must follow the template's marker format exactly</strong> —
            <code>&lt;!-- CARD --&gt;</code>, <code>&lt;!-- TITLE: ... --&gt;</code>,
            <code>&lt;!-- TEASER: ... --&gt;</code>, <code>&lt;!-- /CARD --&gt;</code> —
            or the sections below will be rejected during preview.
        </p>
        <p class="am-import-banner__rules">
            Download the template, attach it to a chatbot along with your article draft and
            the instruction "fill in this template, keeping every marker line exactly as-is,"
            then upload the chatbot's output here.
        </p>
        <div class="am-import-banner__actions">
            <a class="am-import-download" href="${window.AM_IMPORT_TEMPLATE_URL}" target="_blank" rel="noopener">
                ⬇ Download Markdown Template
            </a>
            <a class="am-import-download" href="${window.AM_IMPORT_URLS.export}">
                ⬇ Export Current Sections as Markdown
            </a>
            <input type="file" id="amImportFile" class="am-import-file" accept=".md,.markdown,text/markdown,text/plain">
        </div>
        <textarea id="amImportText" class="am-import-textarea" placeholder="...or paste the filled-in markdown here"></textarea>
        <p class="am-import-replace-row">
            <label>
                <input type="checkbox" id="amImportReplace" checked>
                Replace all existing sections with this import
                <span id="amImportReplaceHint" class="am-import-replace-hint"></span>
            </label>
            <br>
            <small>Uncheck this to add these as new sections instead, keeping the ones already saved.</small>
        </p>
        <div>
            <button type="button" id="amImportPreviewBtn" class="am-import-btn am-import-btn--preview">Preview Import</button>
            <button type="button" id="amImportConfirmBtn" class="am-import-btn am-import-btn--confirm" style="display:none;" disabled>Confirm Import</button>
        </div>
        <div id="amImportPreview" class="am-import-preview"></div>
        <div id="amImportStatus"></div>
    `;
    cardGroup.insertAdjacentElement('afterbegin', banner);

    const fileInput = document.getElementById('amImportFile');
    const textArea = document.getElementById('amImportText');
    const replaceCheckbox = document.getElementById('amImportReplace');
    const replaceHint = document.getElementById('amImportReplaceHint');
    const previewBtn = document.getElementById('amImportPreviewBtn');
    const confirmBtn = document.getElementById('amImportConfirmBtn');
    const previewDiv = document.getElementById('amImportPreview');
    const statusDiv = document.getElementById('amImportStatus');
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    let existingCardCount = 0;
    let parsedCardCount = 0;

    fileInput.addEventListener('change', function () {
        const file = fileInput.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function (e) {
            textArea.value = e.target.result;
        };
        reader.readAsText(file);
    });

    function updateConfirmLabel() {
        if (!parsedCardCount) {
            confirmBtn.textContent = 'Confirm Import';
            return;
        }
        const sectionWord = parsedCardCount === 1 ? 'Section' : 'Sections';
        confirmBtn.textContent = replaceCheckbox.checked
            ? `Confirm & Replace with ${parsedCardCount} ${sectionWord}`
            : `Confirm & Add ${parsedCardCount} ${sectionWord}`;
    }

    replaceCheckbox.addEventListener('change', function () {
        replaceHint.textContent = replaceCheckbox.checked && existingCardCount
            ? `(deletes ${existingCardCount} existing section${existingCardCount === 1 ? '' : 's'} first)`
            : '';
        updateConfirmLabel();
    });

    function renderPreview(data) {
        previewDiv.style.display = 'block';
        let html = '';

        if (data.errors && data.errors.length) {
            html += '<div class="am-import-preview__errors"><strong>Fix these before importing:</strong><ul>';
            data.errors.forEach(function (err) {
                const label = err.title ? `"${err.title}"` : `block ${err.index}`;
                html += `<li>${label}: ${err.message}</li>`;
            });
            html += '</ul></div>';
        }

        if (data.cards && data.cards.length) {
            html += '<div class="am-import-preview__cards">';
            data.cards.forEach(function (card) {
                html += `
                    <div class="am-import-preview__card">
                        <span class="am-import-preview__card-title">${card.title}</span>
                        <span class="am-import-preview__card-meta">${card.word_count} words · ${card.takeaway_count} takeaways</span>
                    </div>
                `;
            });
            html += '</div>';
        }

        previewDiv.innerHTML = html;

        const hasErrors = data.errors && data.errors.length;
        const hasCards = data.cards && data.cards.length;
        existingCardCount = data.existing_card_count || 0;
        parsedCardCount = hasCards ? data.cards.length : 0;

        confirmBtn.style.display = hasCards ? 'inline-block' : 'none';
        confirmBtn.disabled = !hasCards || hasErrors;
        replaceCheckbox.dispatchEvent(new Event('change'));
    }

    function buildFormData(extra) {
        const formData = new FormData();
        if (fileInput.files[0] && !textArea.value.trim()) {
            formData.append('md_file', fileInput.files[0]);
        } else {
            formData.append('md_text', textArea.value);
        }
        if (extra) {
            Object.keys(extra).forEach(function (key) { formData.append(key, extra[key]); });
        }
        return formData;
    }

    previewBtn.addEventListener('click', function () {
        statusDiv.innerHTML = '';
        previewBtn.disabled = true;
        previewBtn.textContent = 'Parsing...';

        fetch(window.AM_IMPORT_URLS.preview, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: buildFormData(),
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                renderPreview(data);
            })
            .catch(function () {
                statusDiv.innerHTML = '<p class="am-import-status am-import-status--error">Preview failed — check the browser console.</p>';
            })
            .finally(function () {
                previewBtn.disabled = false;
                previewBtn.textContent = 'Preview Import';
            });
    });

    confirmBtn.addEventListener('click', function () {
        if (replaceCheckbox.checked && existingCardCount > 0) {
            const ok = window.confirm(
                `This will permanently delete the ${existingCardCount} existing section(s) and replace ` +
                `them with ${parsedCardCount} new one(s). This cannot be undone. Continue?`
            );
            if (!ok) return;
        }

        confirmBtn.disabled = true;
        confirmBtn.textContent = 'Importing...';

        fetch(window.AM_IMPORT_URLS.commit, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: buildFormData({ replace: replaceCheckbox.checked ? '1' : '0' }),
        })
            .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); })
            .then(function (result) {
                if (result.ok) {
                    const replacedNote = result.data.replaced ? `, replacing ${result.data.replaced}` : '';
                    statusDiv.innerHTML = `<p class="am-import-status am-import-status--success">✓ Created ${result.data.created} section(s)${replacedNote}. Reloading...</p>`;
                    setTimeout(function () { window.location.reload(); }, 1200);
                } else {
                    renderPreview(result.data);
                    statusDiv.innerHTML = `<p class="am-import-status am-import-status--error">${result.data.error || 'Import failed.'}</p>`;
                    confirmBtn.disabled = false;
                    updateConfirmLabel();
                }
            })
            .catch(function () {
                statusDiv.innerHTML = '<p class="am-import-status am-import-status--error">Import failed — check the browser console.</p>';
                confirmBtn.disabled = false;
                updateConfirmLabel();
            });
    });
});
