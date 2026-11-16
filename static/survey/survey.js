/*
 * Survey runner. Everything it shows comes from the admin, sent by the page in
 * the "survey-config" JSON block (see survey/views.py page_config).
 *
 * Flow: consent -> each page (section) in order -> thank-you.
 * - Back only works on pages before the random media, so nobody can change
 *   their "before" answers after seeing the message.
 * - Live: the server picks the media group (/start/) and scores the answers (/submit/).
 * - Preview (admin only): nothing is saved; ends with a researcher view.
 * - Progress is kept in sessionStorage, so a refresh resumes where they were.
 */
(function () {
  'use strict';

  var C = JSON.parse(document.getElementById('survey-config').textContent);
  var app = document.getElementById('survey-app');
  var PREVIEW = C.mode === 'preview';
  var STORE_KEY = C.storageKey + (PREVIEW ? ':preview' : '');
  var DONE_KEY = C.storageKey + ':done';
  var SECTIONS = C.sections;
  var MEDIA_INDEX = SECTIONS.findIndex(function (s) { return s.kind === 'media'; });
  var LAST_INDEX = SECTIONS.length - 1;
  var PROMPTS = {};
  C.prompts.forEach(function (p) { PROMPTS[p.n] = p; });
  var CONDITIONS = {};
  C.conditions.forEach(function (c) { CONDITIONS[c.key] = c; });
  var QUESTIONS = [];
  SECTIONS.forEach(function (s) { QUESTIONS = QUESTIONS.concat(s.questions); });
  var S;               // state
  var mediaShownAt = null;

  // ------------------------------------------------------------ helpers

  function $(sel) { return app.querySelector(sel); }
  function $$(sel) { return Array.prototype.slice.call(app.querySelectorAll(sel)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function storage(area) {
    return {
      get: function (k) { try { var v = window[area].getItem(k); return v ? JSON.parse(v) : null; } catch (e) { return null; } },
      set: function (k, v) { try { window[area].setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
      del: function (k) { try { window[area].removeItem(k); } catch (e) { /* private mode */ } }
    };
  }
  var session = storage('sessionStorage');
  var local = storage('localStorage');

  function shuffle(a) {
    a = a.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  // Random order per person; prompts sharing a pair group are never next to each other.
  function spread() {
    var numbers = C.prompts.map(function (p) { return p.n; });
    var groups = {};
    C.prompts.forEach(function (p) { if (p.pair) { (groups[p.pair] = groups[p.pair] || []).push(p.n); } });
    function clash(order) {
      return Object.keys(groups).some(function (g) {
        var members = groups[g];
        return members.some(function (a) {
          return members.some(function (b) { return a !== b && Math.abs(order.indexOf(a) - order.indexOf(b)) < 2; });
        });
      });
    }
    var order, tries = 0;
    do { order = shuffle(numbers); } while (clash(order) && ++tries < 1000);
    return order;
  }

  function readSource() {
    var src = new URLSearchParams(location.search).get('src') || '';
    return /^[a-z0-9_-]{1,60}$/i.test(src) ? src.toLowerCase() : '';
  }

  function hashCondition() {
    var key = decodeURIComponent((location.hash || '').slice(1));
    return CONDITIONS[key] ? key : null;
  }

  function freshState() {
    return {
      step: 'consent',          // 'consent' | section index | 'done' | 'declined'
      consent: [],
      token: null,
      condition: null,
      source: readSource(),
      startedAt: null,
      answers: {},
      before: {},
      after: {},
      beforeOrder: spread(),
      afterOrder: spread(),
      timing: { message: 0, watched: 0, finished: false }
    };
  }

  function validState(s) {
    return s && typeof s === 'object' && s.timing && s.answers &&
      Array.isArray(s.beforeOrder) && s.beforeOrder.length === C.prompts.length &&
      (s.step === 'consent' || s.step === 'done' || s.step === 'declined' ||
        (typeof s.step === 'number' && s.step >= 0 && s.step <= LAST_INDEX));
  }

  function save() { session.set(STORE_KEY, S); }

  // ------------------------------------------------------------ icons and mock screenshots

  var ICON = {
    heart: '<svg viewBox="0 0 24 24"><path d="M12 20s-7-4.4-9.2-8.6C1.3 8.4 3 5 6.4 5c2 0 3.3 1.1 4.1 2.3h1C12.3 6.1 13.6 5 15.6 5 19 5 20.7 8.4 19.2 11.4 17 15.6 12 20 12 20z"/></svg>',
    comment: '<svg viewBox="0 0 24 24"><path d="M20 12a8 8 0 0 1-11.8 7L4 20l1.1-4A8 8 0 1 1 20 12z"/></svg>',
    share: '<svg viewBox="0 0 24 24"><path d="M21 4 10 14M21 4l-7 17-4-7-7-4z"/></svg>',
    save: '<svg viewBox="0 0 24 24"><path d="M6 3h12v18l-6-5-6 5z"/></svg>',
    repost: '<svg viewBox="0 0 24 24"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg>',
    views: '<svg viewBox="0 0 24 24"><path d="M5 20V12M10 20V6M15 20v-9M20 20V9"/></svg>',
    note: '<svg viewBox="0 0 24 24"><path d="M9 18a3 3 0 1 1-2-2.8V4l11-2v12a3 3 0 1 1-2-2.8V5.5L9 6.8z"/></svg>',
    muted: '<svg viewBox="0 0 24 24"><path d="M11 5 6 9H2v6h4l5 4zM23 9l-6 6M17 9l6 6"/></svg>',
    sound: '<svg viewBox="0 0 24 24"><path d="M11 5 6 9H2v6h4l5 4zM15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14"/></svg>'
  };
  var AVATAR = '<span class="post__avatar" aria-hidden="true"><i></i></span>';

  // Built-in placeholder screenshots (all details fictional). Uploads in the admin replace them.
  var MOCKS = {
    formFilled: '<div class="mock"><div class="mt">Visa application form</div><div class="row"><span>Full name</span><b>Ahmed Khalid Rahman</b></div><div class="row"><span>Passport no.</span><b>P8364215</b></div><div class="row"><span>Emirates ID</span><b>784-1999-4567890-1</b></div><div class="row"><span>Date of birth</span><b>12/03/2004</b></div><div class="row"><span>Mobile</span><b>050 123 4567</b></div></div>',
    formBlank: '<div class="mock"><div class="mt">Visa application form</div><div class="row"><span>Full name</span><b></b></div><div class="row"><span>Passport no.</span><b></b></div><div class="row"><span>Emirates ID</span><b></b></div><div class="row"><span>Date of birth</span><b></b></div><div class="row"><span>Mobile</span><b></b></div></div>',
    slide: '<div class="mock mslide"><div class="mt">Lecture 4: Network security basics</div><ul><li>Firewalls and what they block</li><li>TCP vs UDP</li><li>Common attacks: phishing, DDoS</li></ul><div class="pg">4 / 22</div></div>',
    chat: '<div class="mock mchat"><div class="mt">Group project (5 members)</div><p><b>Sara Al Mansoori</b>my number is 050 987 6543 if anyone needs it</p><p><b>Omar Haddad</b>grades are out, I got 68 in the midterm</p><p><b>Lina</b>meeting moved to Thursday, room B214</p></div>',
    bank: '<div class="mock mbank"><div class="mt">Your bank</div><div class="row"><span>Account no.</span><b>0123 4567 8901 23</b></div><div class="row"><span>Balance</span><b>AED 3,250.40</b></div><div class="err">Error 403: session expired. Please log in again.</div></div>',
    memory: '<div class="mock mmem"><div class="mt">Saved memories</div><ul><li>Studies cybersecurity at university</li><li>Prefers short, simple answers</li><li>Passport number P8364215, expires 2029</li><li>Plays football on weekends</li><li>Mentioned their ethnicity and religion in an earlier chat</li><li>Is vegetarian</li><li>Lives in Al Nahda, Sharjah</li></ul><div class="pg">Memory is on</div></div>'
  };

  // ------------------------------------------------------------ top bar and site chrome

  function updateTop() {
    var top = document.querySelector('[data-survey-top]');
    var bar = document.getElementById('survey-bar');
    var count = document.getElementById('survey-count');
    var finished = S.step === 'done' || S.step === 'declined';
    top.hidden = finished;
    document.querySelectorAll('[data-survey-chrome]').forEach(function (el) { el.hidden = !finished; });
    if (typeof S.step === 'number') {
      bar.style.width = ((S.step + 1) / (SECTIONS.length + 1) * 100) + '%';
      count.textContent = 'Part ' + (S.step + 1) + ' of ' + SECTIONS.length;
    } else {
      bar.style.width = finished ? '100%' : '0';
      count.textContent = '';
    }
  }

  function actionsHTML(nextLabel, opts) {
    opts = opts || {};
    return '<p class="survey-error" id="survey-err" role="alert"></p>' +
      '<div class="survey-actions">' +
      (opts.back ? '<button type="button" class="btn btn--ghost" id="survey-back"><span aria-hidden="true">&larr;</span> Back</button>' : '') +
      (opts.extra || '') +
      '<button type="button" class="btn btn--primary" id="survey-next"' + (opts.disabled ? ' disabled' : '') + '>' +
      esc(nextLabel) + ' <span aria-hidden="true">&rarr;</span></button></div>';
  }

  function showError(message) {
    var el = document.getElementById('survey-err');
    if (el) { el.textContent = message; }
  }

  // ------------------------------------------------------------ consent

  function contactLink(value) {
    var v = String(value || '');
    var email = v.match(/[^\s<>()]+@[^\s<>()]+\.[^\s<>()]+/);
    if (!email) { return esc(v); }
    return esc(v.slice(0, email.index)) + '<a href="mailto:' + esc(email[0]) + '">' + esc(email[0]) + '</a>' +
      esc(v.slice(email.index + email[0].length));
  }

  function consentHTML() {
    var c = C.consent;
    var started = !!(S.token || (PREVIEW && S.condition));
    var researcher = c.researcherEmail ? contactLink(c.researcherEmail) : '[researcher email]';
    var ethics = c.ethicsContact ? contactLink(c.ethicsContact) : '[supervisor or ethics contact]';
    return '<span class="survey__eyebrow">' + esc(C.title) + '</span>' +
      '<h1 class="survey__title">' + esc(c.heading) + '</h1>' +
      '<div class="survey__prose">' + c.html + '</div>' +
      '<div class="survey__contacts"><p>Questions about the study: ' + researcher + '</p>' +
      '<p>Questions about your rights: ' + ethics + '</p></div>' +
      c.statements.map(function (text, i) {
        return '<label class="survey-check"><input type="checkbox" data-consent="' + i + '"' +
          (started || S.consent.indexOf(i) !== -1 ? ' checked' : '') + '><span>' + esc(text) + '</span></label>';
      }).join('') +
      (PREVIEW ? '<p class="survey__note">Preview: nothing you enter is saved.</p>' : '') +
      actionsHTML(started ? 'Continue' : c.startLabel, {
        disabled: !started && S.consent.length < c.statements.length,
        extra: started ? '' : '<button type="button" class="btn btn--ghost" id="survey-decline">I don’t want to take part</button>'
      });
  }

  function bindConsent() {
    var boxes = $$('[data-consent]');
    var next = document.getElementById('survey-next');
    boxes.forEach(function (box) {
      box.addEventListener('change', function () {
        S.consent = boxes.filter(function (b) { return b.checked; }).map(function (b) { return +b.dataset.consent; });
        next.disabled = !(S.token || (PREVIEW && S.condition)) && S.consent.length < boxes.length;
        save();
      });
    });
    var decline = document.getElementById('survey-decline');
    if (decline) { decline.addEventListener('click', function () { S.step = 'declined'; save(); render(); }); }
    next.addEventListener('click', startSurvey);
  }

  function startSurvey() {
    var next = document.getElementById('survey-next');
    if (S.token || (PREVIEW && S.condition)) { go(0); return; }
    if (PREVIEW) {
      var keys = Object.keys(CONDITIONS);
      S.condition = hashCondition() || keys[Math.floor(Math.random() * keys.length)];
      S.startedAt = Date.now();
      go(0);
      return;
    }
    next.disabled = true;
    showError('');
    post(C.startUrl, { source: S.source }).then(function (res) {
      if (res.ok && res.data.token && CONDITIONS[res.data.condition]) {
        S.token = res.data.token;
        S.condition = res.data.condition;
        S.startedAt = Date.now();
        go(0);
        return;
      }
      next.disabled = false;
      if (res.status === 410) { location.reload(); return; }   // the survey just closed
      showError(res.status === 429
        ? 'Too many people have started from this network in the last hour. Please try again in a few minutes.'
        : 'Something went wrong starting the survey. Please try again.');
      next.innerHTML = 'Try again <span aria-hidden="true">&rarr;</span>';
    });
  }

  // ------------------------------------------------------------ questions

  function questionHTML(q) {
    var id = 'q-' + q.code;
    var value = S.answers[q.code];
    var optional = q.required ? '' : ' <span class="sq__optional">(optional)</span>';
    var help = q.help ? '<p class="sq__help" id="' + id + '-help">' + esc(q.help) + '</p>' : '';
    var describedBy = (q.help ? id + '-help ' : '') + id + '-err';
    var err = '<p class="sq__error" id="' + id + '-err"></p>';

    if (q.kind === 'short_text' || q.kind === 'long_text' || q.kind === 'number' || q.kind === 'dropdown') {
      var field;
      if (q.kind === 'long_text') {
        field = '<textarea class="sq__input" id="' + id + '" maxlength="2000" aria-describedby="' + describedBy + '">' + esc(value || '') + '</textarea>';
      } else if (q.kind === 'dropdown') {
        field = '<select class="sq__input" id="' + id + '" aria-describedby="' + describedBy + '"><option value="">Choose</option>' +
          q.options.map(function (o) { return '<option' + (value === o ? ' selected' : '') + '>' + esc(o) + '</option>'; }).join('') + '</select>';
      } else if (q.kind === 'number') {
        field = '<input class="sq__input" type="number" inputmode="numeric" step="1" id="' + id + '"' +
          (q.min != null ? ' min="' + q.min + '"' : '') + (q.max != null ? ' max="' + q.max + '"' : '') +
          ' value="' + esc(value == null ? '' : value) + '" aria-describedby="' + describedBy + '">';
      } else {
        field = '<input class="sq__input" type="text" id="' + id + '" maxlength="200" autocomplete="off" value="' +
          esc(value || '') + '" aria-describedby="' + describedBy + '">';
      }
      return '<div class="sq" data-q="' + esc(q.code) + '"><label class="sq__label" for="' + id + '">' + esc(q.text) + optional + '</label>' +
        help + '<div class="sq__body">' + field + '</div>' + err + '</div>';
    }

    var inputs;
    if (q.kind === 'scale') {
      inputs = '<div class="scale">' + [1, 2, 3, 4, 5].map(function (n) {
        return '<label class="chip"><input type="radio" name="' + id + '" value="' + n + '"' + (value === n ? ' checked' : '') +
          '><span>' + n + '</span></label>';
      }).join('') + '</div><div class="scale__ends" aria-hidden="true"><span>1 ' + esc(q.low) + '</span><span>5 ' + esc(q.high) + '</span></div>';
    } else {
      var type = q.kind === 'checkboxes' ? 'checkbox' : 'radio';
      inputs = '<div class="chips">' + q.options.map(function (o) {
        var on = type === 'checkbox' ? (Array.isArray(value) && value.indexOf(o) !== -1) : value === o;
        return '<label class="chip"><input type="' + type + '" name="' + id + '" value="' + esc(o) + '"' + (on ? ' checked' : '') +
          '><span>' + esc(o) + '</span></label>';
      }).join('') + '</div>';
    }
    var scaleHint = q.kind === 'scale' ? '<span class="prompt__legend"> (1 ' + esc(q.low) + ', 5 ' + esc(q.high) + ')</span>' : '';
    return '<fieldset class="sq" data-q="' + esc(q.code) + '" aria-describedby="' + describedBy + '"><legend class="sq__label">' +
      esc(q.text) + optional + scaleHint + '</legend>' + help + '<div class="sq__body">' + inputs + '</div>' + err + '</fieldset>';
  }

  function readQuestion(q) {
    var box = app.querySelector('[data-q="' + CSS.escape(q.code) + '"]');
    if (!box) { return; }
    var value;
    if (q.kind === 'choice' || q.kind === 'scale') {
      var picked = box.querySelector('input:checked');
      value = picked ? (q.kind === 'scale' ? +picked.value : picked.value) : undefined;
    } else if (q.kind === 'checkboxes') {
      value = Array.prototype.map.call(box.querySelectorAll('input:checked'), function (el) { return el.value; });
      if (!value.length) { value = undefined; }
    } else if (q.kind === 'number') {
      var raw = box.querySelector('input').value.trim();
      value = raw === '' ? undefined : Number(raw);
    } else {
      var el = box.querySelector('input, textarea, select');
      value = el.value.trim() === '' ? undefined : el.value;
    }
    if (value === undefined) { delete S.answers[q.code]; } else { S.answers[q.code] = value; }
  }

  function questionProblem(q) {
    var v = S.answers[q.code];
    if (v === undefined) { return q.required ? 'This question needs an answer.' : ''; }
    if (q.kind === 'number') {
      if (!Number.isInteger(v)) { return 'Enter a whole number.'; }
      if ((q.min != null && v < q.min) || (q.max != null && v > q.max)) {
        if (q.rangeMessage) { return q.rangeMessage; }
        if (q.min != null && q.max != null) { return 'Enter a number from ' + q.min + ' to ' + q.max + '.'; }
        return q.min != null ? 'Enter ' + q.min + ' or more.' : 'Enter ' + q.max + ' or less.';
      }
    }
    if (q.kind === 'short_text' && v.trim().length > 200) { return 'Keep this under 200 characters.'; }
    return '';
  }

  // ------------------------------------------------------------ "Would you send this?"

  function promptHTML(phase, n, position) {
    var p = PROMPTS[n];
    var current = S[phase][n];
    var ctx = '';
    if (p.contextImage || p.contextMock) {
      ctx = '<div class="prompt__ctx"><span class="prompt__ctx-label">' + esc(p.contextLabel) + '</span>' +
        (p.contextImage ? '<img class="prompt__shot" src="' + esc(p.contextImage) + '" alt="' + esc(p.contextLabel) + '" loading="lazy">' : (MOCKS[p.contextMock] || '')) +
        '</div>';
    }
    var attachment = p.screenshot
      ? '<img class="prompt__shot" src="' + esc(p.screenshot) + '" alt="Attached screenshot" loading="lazy">'
      : (MOCKS[p.mock] || '');
    return '<fieldset class="prompt" data-prompt="' + n + '"><legend class="prompt__legend">Message ' + position + ' of ' + C.prompts.length + '</legend>' +
      ctx +
      '<div class="prompt__row"><div class="bubble">' + (attachment ? '<div class="bubble__att">' + attachment + '</div>' : '') + esc(p.text) + '</div></div>' +
      '<div class="chips">' + C.sendChoices.map(function (choice) {
        return '<label class="chip"><input type="radio" name="' + phase + '-' + n + '" value="' + choice[0] + '"' +
          (current === choice[0] ? ' checked' : '') + '><span>' + esc(choice[1]) + '</span></label>';
      }).join('') + '</div></fieldset>';
  }

  function readTask(phase) {
    C.prompts.forEach(function (p) {
      var picked = app.querySelector('input[name="' + phase + '-' + p.n + '"]:checked');
      if (picked) { S[phase][p.n] = picked.value; }
    });
  }

  // ------------------------------------------------------------ random media

  function captionHTML(text) {
    return esc(text).replace(/(#[\wÀ-￿]+)/g, '<span class="post__tag">$1</span>');
  }

  function postFrame(inner, caption) {
    return '<div class="post" aria-label="Social media post">' +
      '<div class="post__head">' + AVATAR + '<div><span class="post__name">' + esc(C.handle) + '</span><span class="post__sub">UAE</span></div><span class="post__more" aria-hidden="true">&hellip;</span></div>' +
      inner +
      '<div class="post__icons" aria-hidden="true">' + ICON.heart + ICON.comment + ICON.share + '<span class="post__save">' + ICON.save + '</span></div>' +
      '<p class="post__cap">' + (caption ? '<b>' + esc(C.handle) + '</b> ' + captionHTML(caption) : '') + '<span class="post__time">2 hours ago</span></p></div>';
  }

  function textPostHTML(c) {
    var paragraphs = String(c.text || '').split(/\n\s*\n/).filter(function (p) { return p.trim(); });
    return '<div class="post post--text" aria-label="Text post">' +
      '<div class="post__head">' + AVATAR + '<div><span class="post__name">' + esc(C.handle) + '</span><span class="post__sub">@' + esc(C.handle) + ', 2h</span></div><span class="post__more" aria-hidden="true">&hellip;</span></div>' +
      '<div class="post__body">' + paragraphs.map(function (p) { return '<p>' + esc(p.trim()).replace(/\n/g, '<br>') + '</p>'; }).join('') + '</div>' +
      '<div class="post__row" aria-hidden="true">' + ICON.comment + ICON.repost + ICON.heart + ICON.views + ICON.save + '</div></div>';
  }

  function reelHTML(c) {
    if (!c.video) { return postFrame('<div class="post__empty">No video uploaded for this group yet.</div>', ''); }
    return '<div class="reel" id="reel">' +
      '<video class="reel__video" id="reel-video" src="' + esc(c.video) + '"' + (c.image ? ' poster="' + esc(c.image) + '"' : '') +
      ' playsinline webkit-playsinline muted autoplay preload="auto"></video>' +
      '<div class="reel__shade"></div>' +
      '<div class="reel__rail" aria-hidden="true">' + ICON.heart + ICON.comment + ICON.share + ICON.save + '</div>' +
      '<div class="reel__meta"><div class="reel__who">' + AVATAR + '<span>' + esc(C.handle) + '</span><span class="reel__follow">Follow</span></div>' +
      (c.caption ? captionHTML(c.caption) : '') +
      '<div class="reel__audio">' + ICON.note + '<span>Original audio</span></div></div>' +
      '<div class="reel__paused" aria-hidden="true">Paused, tap to play</div>' +
      '<button type="button" class="reel__tap" id="reel-tap" aria-label="Pause or play the video"></button>' +
      '<button type="button" class="reel__sound" id="reel-sound" aria-pressed="false" aria-label="Turn sound on">' + ICON.muted + '</button>' +
      '</div><div class="reel-controls"><button type="button" class="btn btn--ghost" id="reel-replay">Replay</button></div>';
  }

  function mediaHTML() {
    var c = CONDITIONS[S.condition];
    if (!c) { return '<p class="survey-error">This content could not be loaded. Please let the researcher know.</p>'; }
    if (c.kind === 'video') { return reelHTML(c); }
    if (c.kind === 'image') {
      return postFrame(c.image
        ? '<img class="post__img" src="' + esc(c.image) + '" alt="' + esc(c.alt || c.name) + '">'
        : '<div class="post__empty">No image uploaded for this group yet.</div>', c.caption);
    }
    return textPostHTML(c);
  }

  function bindVideo() {
    var video = document.getElementById('reel-video');
    if (!video) { return; }
    var reel = document.getElementById('reel');
    var sound = document.getElementById('reel-sound');
    var last = 0;
    video.addEventListener('timeupdate', function () {
      var delta = video.currentTime - last;
      if (!video.paused && delta > 0 && delta < 1.5) { S.timing.watched += delta; }   // ignores seeking
      last = video.currentTime;
    });
    video.addEventListener('seeked', function () { last = video.currentTime; });
    video.addEventListener('play', function () { reel.classList.remove('is-paused'); });
    video.addEventListener('pause', function () { if (!video.ended) { reel.classList.add('is-paused'); } });
    video.addEventListener('ended', function () { S.timing.finished = true; save(); });
    document.getElementById('reel-tap').addEventListener('click', function () {
      if (video.paused) {
        reel.classList.remove('is-paused');
        video.play().catch(function () { reel.classList.add('is-paused'); });
      } else {
        reel.classList.add('is-paused');   // show "Paused" straight away
        video.pause();
      }
    });
    sound.addEventListener('click', function () {
      video.muted = !video.muted;
      sound.setAttribute('aria-pressed', String(!video.muted));
      sound.setAttribute('aria-label', video.muted ? 'Turn sound on' : 'Turn sound off');
      sound.innerHTML = video.muted ? ICON.muted : ICON.sound;
    });
    document.getElementById('reel-replay').addEventListener('click', function () {
      video.currentTime = 0;
      video.play().catch(function () {});
    });
    var playing = video.play();
    if (playing && playing.catch) { playing.catch(function () { reel.classList.add('is-paused'); }); }
  }

  function leaveMedia() {
    if (mediaShownAt !== null) {
      S.timing.message += (Date.now() - mediaShownAt) / 1000;
      mediaShownAt = null;
    }
    var video = document.getElementById('reel-video');
    if (video) { video.pause(); }
  }

  // ------------------------------------------------------------ sections

  function sectionHTML(i) {
    var s = SECTIONS[i];
    var body = '';
    if (s.kind === 'questions') {
      body = s.questions.map(questionHTML).join('');
    } else if (s.kind === 'task_before' || s.kind === 'task_after') {
      var phase = s.kind === 'task_before' ? 'before' : 'after';
      var order = phase === 'before' ? S.beforeOrder : S.afterOrder;
      body = order.map(function (n, idx) { return promptHTML(phase, n, idx + 1); }).join('');
    } else if (s.kind === 'media') {
      body = mediaHTML();
    }
    var label = s.button || (i === LAST_INDEX ? 'Submit answers' : 'Next');
    // Back only before the random media: the "before" answers can't change after seeing it.
    var back = MEDIA_INDEX === -1 || i < MEDIA_INDEX;
    return '<h1 class="survey__title">' + esc(s.title) + '</h1>' +
      (s.html ? '<div class="survey__lede survey__prose">' + s.html + '</div>' : '') +
      body + actionsHTML(label, { back: back });
  }

  function collect() {
    if (typeof S.step !== 'number') { return; }
    var s = SECTIONS[S.step];
    if (s.kind === 'questions') { s.questions.forEach(readQuestion); }
    if (s.kind === 'task_before') { readTask('before'); }
    if (s.kind === 'task_after') { readTask('after'); }
  }

  // Returns true if the current page can be left.
  function checkPage() {
    var s = SECTIONS[S.step];
    var first = null;
    if (s.kind === 'questions') {
      s.questions.forEach(function (q) {
        var problem = questionProblem(q);
        var box = app.querySelector('[data-q="' + CSS.escape(q.code) + '"]');
        box.toggleAttribute('data-invalid', !!problem);
        document.getElementById('q-' + q.code + '-err').textContent = problem;
        var field = box.querySelector('.sq__input');
        if (field) { field.setAttribute('aria-invalid', problem ? 'true' : 'false'); }
        if (problem && !first) { first = box; }
      });
      if (first) { showError('Answer the questions marked in red to continue.'); }
    } else if (s.kind === 'task_before' || s.kind === 'task_after') {
      var phase = s.kind === 'task_before' ? 'before' : 'after';
      $$('[data-prompt]').forEach(function (box) {
        var missing = !S[phase][box.dataset.prompt];
        box.toggleAttribute('data-invalid', missing);
        if (missing && !first) { first = box; }
      });
      if (first) { showError('Choose an option for all ' + C.prompts.length + ' messages to continue.'); }
    }
    if (first) {
      first.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return false;
    }
    return true;
  }

  function bindSection() {
    var next = document.getElementById('survey-next');
    var back = document.getElementById('survey-back');
    app.addEventListener('change', onChange);
    app.addEventListener('input', onChange);
    if (SECTIONS[S.step].kind === 'media') {
      mediaShownAt = Date.now();
      bindVideo();
    }
    next.addEventListener('click', function () {
      collect();
      showError('');
      if (!checkPage()) { save(); return; }
      if (SECTIONS[S.step].kind === 'media') { leaveMedia(); }
      if (S.step === LAST_INDEX) { finish(next); } else { go(S.step + 1); }
    });
    if (back) {
      back.addEventListener('click', function () {
        collect();
        go(S.step === 0 ? 'consent' : S.step - 1);
      });
    }
  }

  function onChange() { collect(); save(); }

  // ------------------------------------------------------------ submit

  function post(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': C.csrfToken },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        return { ok: res.ok, status: res.status, data: data };
      });
    }).catch(function () { return { ok: false, status: 0, data: {} }; });
  }

  function payload() {
    var answers = {};
    QUESTIONS.forEach(function (q) {
      var v = S.answers[q.code];
      if (v !== undefined) { answers[q.code] = typeof v === 'string' ? v.trim() : v; }
    });
    var isVideo = (CONDITIONS[S.condition] || {}).kind === 'video';
    var round = function (x) { return Math.round(x * 10) / 10; };
    return {
      token: S.token,
      answers: answers,
      before_order: S.beforeOrder,
      before: S.before,
      after_order: S.afterOrder,
      after: S.after,
      timing: {
        message_seconds: round(S.timing.message),
        video_watched_seconds: isVideo ? round(S.timing.watched) : null,
        video_finished: isVideo ? !!S.timing.finished : null,
        total_seconds: S.startedAt ? Math.min(round((Date.now() - S.startedAt) / 1000), 86400) : null
      }
    };
  }

  function finish(button) {
    if (PREVIEW) { go('done'); return; }
    button.disabled = true;
    button.textContent = 'Sending…';
    post(C.submitUrl, payload()).then(function (res) {
      if (res.ok) {
        local.set(DONE_KEY, true);
        session.del(STORE_KEY);
        S.step = 'done';
        render();
        return;
      }
      button.disabled = false;
      button.innerHTML = 'Try again <span aria-hidden="true">&rarr;</span>';
      if (res.status === 410) {
        showError('Your session has timed out or the survey has closed, so these answers can’t be saved. Thank you for your time.');
        var fresh = button.cloneNode(false);   // drops the submit handler
        fresh.textContent = 'Start again';
        fresh.addEventListener('click', restart);
        button.replaceWith(fresh);
      } else if (res.status === 429) {
        showError('Too many attempts from this network. Please wait a few minutes, then tap Try again. Your answers are kept.');
      } else {
        showError('Your answers couldn’t be sent. Check your connection, then tap Try again. Your answers are kept.');
      }
    });
  }

  // ------------------------------------------------------------ end screens

  function thanksHTML(already) {
    var t = C.thanks;
    return '<section class="survey-thanks">' +
      '<img class="survey-thanks__logo" src="' + esc(C.logo) + '" width="500" height="188" alt="Adhenz Miranda">' +
      '<h1 class="survey__title">' + esc(already ? t.alreadyDone : t.heading) + '</h1>' +
      (t.html ? '<div class="survey__prose">' + t.html + '</div>' : '') +
      (t.shareImage ? '<figure class="survey-thanks__share"><img src="' + esc(t.shareImage) + '" alt="Invite to take the survey"></figure>' : '') +
      '<div class="survey-actions">' +
      '<button type="button" class="btn btn--primary" id="share-btn">Share the survey</button>' +
      '<button type="button" class="btn btn--ghost" id="copy-btn">Copy link</button>' +
      (t.shareImage ? '<a class="btn btn--ghost" href="' + esc(t.shareImageDownload) + '" download>Save image</a>' : '') +
      '</div><p class="survey-thanks__status" id="share-status" role="status"></p>' +
      (PREVIEW ? researcherHTML() : '') +
      '</section>';
  }

  function shareLink() { return C.thanks.shareUrl + '?src=shared'; }

  function bindThanks() {
    var status = document.getElementById('share-status');
    function copy() {
      var done = function () { status.textContent = 'Link copied.'; };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(shareLink()).then(done, function () { status.textContent = shareLink(); });
      } else {
        status.textContent = shareLink();
      }
    }
    document.getElementById('copy-btn').addEventListener('click', copy);
    document.getElementById('share-btn').addEventListener('click', function () {
      if (!navigator.share) { copy(); return; }
      var data = { title: C.title, text: C.thanks.shareText, url: shareLink() };
      var withImage = C.thanks.shareImage
        ? fetch(C.thanks.shareImage).then(function (r) { return r.blob(); }).then(function (blob) {
          var file = new File([blob], 'survey.' + ((blob.type.split('/')[1] || 'jpg').replace('jpeg', 'jpg')), { type: blob.type });
          return navigator.canShare && navigator.canShare({ files: [file] }) ? Object.assign({ files: [file] }, data) : data;
        }).catch(function () { return data; })
        : Promise.resolve(data);
      withImage.then(function (d) { return navigator.share(d); }).catch(function () { /* closed the share sheet */ });
    });
    var again = document.getElementById('preview-again');
    if (again) { again.addEventListener('click', restart); }
  }

  function researcherHTML() {
    var correct = function (phase) {
      return C.prompts.reduce(function (sum, p) {
        var a = S[phase][p.n];
        return sum + ((p.risky ? (a === 'change' || a === 'dont_send') : a === 'send') ? 1 : 0);
      }, 0);
    };
    var b = correct('before');
    var a = correct('after');
    var constructs = {};
    QUESTIONS.forEach(function (q) {
      if (q.construct && typeof S.answers[q.code] === 'number') { (constructs[q.construct] = constructs[q.construct] || []).push(S.answers[q.code]); }
    });
    var rows = [
      ['Media group', (CONDITIONS[S.condition] || {}).name || '-'],
      ['Score before', b + ' of ' + C.prompts.length],
      ['Score after', a + ' of ' + C.prompts.length],
      ['Change (main outcome)', (a - b > 0 ? '+' : '') + (a - b)]
    ].concat(Object.keys(constructs).map(function (k) {
      var v = constructs[k];
      return ['Mean ' + k.replace(/_/g, ' '), (v.reduce(function (x, y) { return x + y; }, 0) / v.length).toFixed(1)];
    })).concat(QUESTIONS.filter(function (q) { return q.attention; }).map(function (q) {
      return ['Attention check ' + q.code, String(S.answers[q.code] || '').toLowerCase() === q.attention.toLowerCase() ? 'passed' : 'failed'];
    })).concat([
      ['Time on the media', Math.round(S.timing.message) + ' s'],
      ['Total time', S.startedAt ? Math.round((Date.now() - S.startedAt) / 1000) + ' s' : '-']
    ]);
    return '<section class="survey-panel" aria-label="Researcher view"><h2>Researcher view (preview only)</h2>' +
      rows.map(function (r) { return '<div class="survey-stat"><span>' + esc(r[0]) + '</span><b>' + esc(r[1]) + '</b></div>'; }).join('') +
      '<p class="survey__note">Preview a group: ' + C.conditions.map(function (c) {
        return '<a href="#' + esc(c.key) + '">' + esc(c.name) + '</a>';
      }).join(' ') + '</p>' +
      '<div class="survey-actions"><button type="button" class="btn btn--ghost" id="preview-again">Start again</button></div></section>';
  }

  function declinedHTML() {
    return '<h1 class="survey__title">No problem</h1>' +
      '<p class="survey__lede">You chose not to take part, so nothing has been recorded. You can close this page.</p>' +
      '<div class="survey-actions"><button type="button" class="btn btn--ghost" id="survey-restart">Back to the start</button></div>';
  }

  // ------------------------------------------------------------ navigation

  function go(step) {
    S.step = step;
    save();
    render();
  }

  function restart() {
    session.del(STORE_KEY);
    S = freshState();
    save();
    render();
  }

  function render() {
    app.removeEventListener('change', onChange);
    app.removeEventListener('input', onChange);
    leaveMedia();
    updateTop();
    var already = S.step === 'done' && S.already;
    if (S.step === 'consent') {
      app.innerHTML = consentHTML();
      bindConsent();
    } else if (S.step === 'declined') {
      app.innerHTML = declinedHTML();
      document.getElementById('survey-restart').addEventListener('click', restart);
    } else if (S.step === 'done') {
      app.innerHTML = thanksHTML(already);
      bindThanks();
    } else {
      app.innerHTML = sectionHTML(S.step);
      bindSection();
    }
    window.scrollTo(0, 0);
    app.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------ start up

  if (!PREVIEW && local.get(DONE_KEY)) {
    S = { step: 'done', already: true, timing: { message: 0 }, answers: {}, before: {}, after: {} };   // soft duplicate check
  } else {
    S = session.get(STORE_KEY);
    if (!validState(S) || (PREVIEW && hashCondition() && S.condition && S.condition !== hashCondition())) {
      S = freshState();
    }
  }

  if (PREVIEW) {
    window.addEventListener('hashchange', function () { if (hashCondition()) { restart(); } });
  }

  // Keep time on the media and video progress if the page is closed or refreshed mid-way.
  window.addEventListener('pagehide', function () {
    if (mediaShownAt !== null) {
      S.timing.message += (Date.now() - mediaShownAt) / 1000;
      mediaShownAt = Date.now();
    }
    if (S.step !== 'done') { save(); }
  });

  render();
})();
