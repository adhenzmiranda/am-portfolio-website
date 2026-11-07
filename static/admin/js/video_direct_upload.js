// Admin video field: upload straight from the browser to Cloudinary.
// See projects/direct_upload.py for why (Heroku's 30-second request limit).
//
// 1. A file is chosen (or dropped in by the "Select Multiple Videos" batch button).
// 2. Ask the server for a short-lived upload signature (admin-only, POST + CSRF).
// 3. Upload to Cloudinary with a progress bar.
// 4. Put Cloudinary's signed reference in the hidden input; Save submits only that.
// Save is held back while uploads are still running.
(function () {
    'use strict';

    const MB = 1024 * 1024;
    const uploading = new Set();

    function csrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
        const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    function setStatus(wrap, text, state) {
        const status = wrap.querySelector('.direct-upload__status');
        status.textContent = text;
        status.dataset.state = state || '';
    }

    function setProgress(wrap, percent) {
        const bar = wrap.querySelector('.direct-upload__bar');
        if (percent === null) { bar.hidden = true; return; }
        bar.hidden = false;
        bar.value = percent;
    }

    async function getSignature(signUrl) {
        const response = await fetch(signUrl, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken() },
            credentials: 'same-origin',
        });
        if (!response.ok) throw new Error(`Could not start the upload (server said ${response.status}).`);
        return response.json();
    }

    function sendToCloudinary(sig, file, wrap) {
        return new Promise((resolve, reject) => {
            const body = new FormData();
            body.append('file', file);
            body.append('api_key', sig.api_key);
            body.append('timestamp', sig.timestamp);
            body.append('folder', sig.folder);
            body.append('signature', sig.signature);

            const xhr = new XMLHttpRequest();
            xhr.open('POST', sig.upload_url);
            xhr.upload.addEventListener('progress', (event) => {
                if (!event.lengthComputable) return;
                const percent = Math.round((event.loaded / event.total) * 100);
                setProgress(wrap, percent);
                setStatus(wrap, `Uploading to Cloudinary… ${percent}%`, 'busy');
            });
            xhr.addEventListener('load', () => {
                let data = {};
                try { data = JSON.parse(xhr.responseText); } catch (e) { /* handled below */ }
                if (xhr.status >= 200 && xhr.status < 300 && data.public_id) resolve(data);
                else reject(new Error((data.error && data.error.message) || `Cloudinary refused the upload (${xhr.status}).`));
            });
            xhr.addEventListener('error', () => reject(new Error('Network error while uploading. Check your connection and try again.')));
            xhr.send(body);
        });
    }

    async function handleFile(input) {
        const wrap = input.closest('.direct-upload');
        const hidden = wrap.querySelector('input[type="hidden"]');
        const file = input.files && input.files[0];
        hidden.value = '';
        input.removeAttribute('name');
        setProgress(wrap, null);
        if (!file) { setStatus(wrap, ''); return; }

        const sizeMb = file.size / MB;
        const maxMb = Number(input.dataset.maxMb) || 100;
        if (sizeMb > maxMb) {
            if (input.dataset.allowServerUpload === 'true') {
                // Local admin only: post the file normally so it is compressed on Save.
                input.setAttribute('name', input.dataset.fieldName);
                setStatus(wrap, `${sizeMb.toFixed(0)} MB: over ${maxMb} MB, so it will be compressed and uploaded when you click Save.`, 'info');
            } else {
                input.value = '';
                setStatus(wrap, `This video is ${sizeMb.toFixed(0)} MB. Cloudinary's free plan allows up to ${maxMb} MB per video. ` +
                    'Compress it first (for example with HandBrake), or upload it from your local admin, which compresses it automatically.', 'error');
            }
            return;
        }

        uploading.add(input);
        setStatus(wrap, 'Preparing upload…', 'busy');
        setProgress(wrap, 0);
        try {
            const sig = await getSignature(input.dataset.signUrl);
            const result = await sendToCloudinary(sig, file, wrap);
            // Same format Cloudinary's own direct-upload field uses; the server checks the signature.
            hidden.value = `${result.resource_type}/${result.type}/v${result.version}/${result.public_id}.${result.format}#${result.signature}`;
            setProgress(wrap, 100);
            setStatus(wrap, `Uploaded ✓ (${sizeMb.toFixed(1)} MB). Click Save to keep it.`, 'done');
        } catch (error) {
            input.value = '';
            setProgress(wrap, null);
            setStatus(wrap, error.message, 'error');
        } finally {
            uploading.delete(input);
        }
    }

    document.addEventListener('change', (event) => {
        const input = event.target.closest && event.target.closest('input[data-direct-upload]');
        if (input) handleFile(input);
    });

    // Hold Save back until every upload has finished (capture phase: before other handlers).
    document.addEventListener('submit', (event) => {
        if (!uploading.size) return;
        event.preventDefault();
        event.stopImmediatePropagation();
        window.alert(`Please wait: ${uploading.size} video${uploading.size === 1 ? ' is' : 's are'} still uploading.`);
    }, true);

    // Warn before leaving the page mid-upload.
    window.addEventListener('beforeunload', (event) => {
        if (!uploading.size) return;
        event.preventDefault();
        event.returnValue = '';
    });
})();
