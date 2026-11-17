# CLAUDE.md

Notes for Claude Code and other agents working in this repo. Read this first.

## What this is

Adhenz Miranda's portfolio site, live at **adhenzmiranda.com**.

- Django 5.2, Python 3.12 (pinned in `.python-version`). One Django project, also called `projects`: settings in `projects/settings.py`, URLs in `projects/urls.py`, and the app code (models, views, admin) in the same folder.
- SCSS compiled with Dart Sass (npm) from `static/scss/main.scss` to `static/css/main.css`. Both files are committed.
- Plain JavaScript in `static/js/` (GSAP animations, lightbox, filters). No bundler.
- Media (project photos and videos) lives on **Cloudinary**.
- Production: Heroku app `am04`, Neon Postgres, behind Cloudflare. Locally: SQLite.

## Set up a new Windows machine

From the repo root in a VS Code terminal:

```
powershell -ExecutionPolicy Bypass -File scripts\setup_dev.ps1
```

This installs Python 3.12, Node, Git and the Heroku CLI if they're missing. It then creates `.venv`, installs `requirements.txt` and npm packages, writes a starter `.env`, compiles the SCSS and runs `migrate`. It is safe to run again. Restart VS Code afterwards so the new PATH is picked up.

Then fill in `.env` (see below) and load real content (see "Local data").

## Everyday commands

```
npm run dev                          # runserver at http://127.0.0.1:8000 (uses .venv)
npm run sass                         # compile SCSS once
npm run sass:watch                   # recompile on save
.venv\Scripts\python manage.py test  # run tests
.venv\Scripts\python manage.py check
```

The `*1` npm scripts (`sass1`, `dev1`...) are leftovers for an old `venv` folder name. Use the ones without the 1.

Sass note: a newer Sass version can reorder a few rules in `main.css` without changing anything visible. If `main.css` shows up as changed and you didn't touch SCSS, restore it with `git checkout -- static/css/main.css static/css/main.css.map`.

## Environment (`.env`, never committed)

`settings.py` reads `.env` with python-dotenv. The format is `KEY=value`. The `KEY: value` lines that `heroku config` prints are silently ignored.

Local `.env` should have:

- `SECRET_KEY` (a local one, never the production key) and `DEBUG=True`
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`
- Optionally `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` (Gmail app password) for the contact form

Leave these **unset** locally:

- `DATABASE_URL`: unset means SQLite. Setting it to the Neon URL points the laptop at the **live database**.
- `ADMIN_URL`: unset with `DEBUG=True` means the admin is at `/admin-dev/`. In production it's a secret path.
- `TURNSTILE_*`: the widget is tied to the live domain and blocks the contact form on localhost.
- `INDEXNOW_KEY`, `SENTRY_DSN`, `HEROKU_*`: production only.

Live values are Heroku config vars: `heroku config -a am04`, or the Heroku dashboard under Settings, then Config Vars.

## Local data

A fresh local database is empty. To copy the live content down (read-only on the live side):

```
.venv\Scripts\python scripts\backup_live_site.py --no-media
.venv\Scripts\python manage.py flush --noinput
.venv\Scripts\python manage.py loaddata backups\<newest folder>\data.json
```

This needs `heroku login` first. Images still load from Cloudinary. `backups/` is gitignored.

**Admin 2FA locally.** The admin uses django-otp. The backup leaves 2FA secrets out on purpose, so the authenticator app's codes don't work locally. Make a one-time code with `.venv\Scripts\python manage.py addstatictoken admin`, then log in with the live username and password plus that code.

## Safety rules

- **Cloudinary is shared with the live site.** Anything uploaded from the local admin lands in the real Cloudinary library.
- Never point local work at the live Neon database. Never run `migrate`, `flush` or `loaddata` against it.
- Never commit `.env`, `backups/`, database dumps or survey CSVs (`survey_responses_*.csv`). `.gitignore` covers these; keep it that way.
- Don't store personal data you don't need. For example, the IP address is only used for rate limiting (`client_ip()` in `projects/views.py`, which reads `CF-Connecting-IP`) and is never saved.
- With `DEBUG=False`, settings turn on HTTPS redirects, secure cookies and HSTS, and `ADMIN_URL` must be set.

## Deploying

- Work on a branch and open a PR. **Adhenz merges.** Don't push to `main` directly.
- Merging to `main` auto-deploys to Heroku. The release phase (`Procfile`) runs `migrate --noinput`, so migrations go live on merge.
- Static files are served by WhiteNoise in production.
- No GitHub CLI (`gh`) is installed on Adhenz's machine. Push the branch, then open the PR from GitHub Desktop or the link git prints.

## Working with Adhenz

- Short numbered steps when explaining how to do something.
- Plain words. No em dashes, and no "it's not X, it's Y" lines in any copy.
- British spelling in anything visitors or survey participants read.
- One branch, one PR per change.

## Docs and current work

- `docs/`: security notes (`SECURITY_DOCUMENTATION.md`, `SECURITY_ROUTINE_CHECKLIST.md`, `NIST_SECURITY_REPORT.md`), `REDESIGN_SPEC.md`, `EMBED_IMPLEMENTATION.md`, `DATABASE_LOCK_PREVENTION.md`.
- **Studio:** the website builder at `/studio/` (staff with 2FA), used instead of the Django admin for everyday content. **Read `docs/STUDIO_ARCHITECTURE.md` first**; progress is in `docs/STUDIO_CHECKLIST.md` (tick a box only when it's built and tested).
  - Code: the `studio` app (`api.py` does every write through a ModelForm), `templates/studio/page.html` (a shell), and `static/studio/` (`kit.js` is shared; one script per page).
  - Same front-end rules as the survey: DOM methods only, and state loaded with `fetch`.
  - Tests mock Cloudinary uploads. Don't upload real files from local tests.
- **Dissertation survey:** the `survey` app at `/msc-survey/` (Draft until ethics approval). **Read `docs/SURVEY.md` first**; `SURVEY_HANDOVER.md` is the original brief.
  - Content lives in the database, not the code. It's edited in the Google Forms-style editor at `/msc-survey/edit/` (staff with 2FA) or in the Django admin.
  - `survey/seed.py` only loads the starting version.
  - The approved prompts, script and rating statements are locked for the dissertation, so don't reword them.
  - The server enforces: locking once responses exist, the "Ready to open?" checklist, balanced assignment and server-side scoring. Keep those rules in `survey/models.py`, `logic.py` and `editor.py`, not only in the browser.
  - Front ends build HTML with escaping or DOM methods only. CodeQL flags anything else.
