# Studio architecture: the website builder at /studio/

**Studio** is a website builder for the whole site. It replaces the Django admin for everyday content: projects (in **Portfolio** and **Blog Post** mode), their media, and the About page. It uses the same look and building blocks as the survey editor at `/msc-survey/edit/`.

Progress is tracked in [STUDIO_CHECKLIST.md](STUDIO_CHECKLIST.md). This file describes the design and is updated as each part ships.

> Diagrams are in Mermaid. GitHub draws them. In VS Code, install **Markdown Preview Mermaid Support** and press Ctrl+Shift+V.

**Status**

| Part | State |
| --- | --- |
| Dashboard, All projects, project editor (Details, Write, Chapters) | Built (PR 1) |
| Media tab | Shows the counts and links to the admin for now. The full editor comes in PR 2. |
| About page (`/studio/about/`) | PR 2 |

---

## 1. Goals

- **No Django admin for day-to-day work.** Every project, photo, video, embed, card and About entry is editable in a friendly UI.
- **Google Forms-style editing:** cards, autosave, drag-and-drop with arrows, and phone-friendly.
- **The same rules as the admin:** the same validation (a ModelForm on every save), the same safe embeds, the same direct uploads to Cloudinary, and the same Bing (IndexNow) ping when content changes.
- **A reusable kit:** the editing building blocks live in one shared file, so the next builder is quick to make.
- **The Django admin stays** as a backup, and for users, 2FA devices and raw data.

---

## 2. Pages

```mermaid
flowchart TD
    D["/studio/<br/>Dashboard"] --> P["/studio/projects/<br/>All projects: search, filter"]
    D -.-> A["/studio/about/<br/>Experience and Education<br/>(PR 2)"]
    D --> S["/msc-survey/edit/<br/>Survey editor (existing)"]
    D --> X["Django admin<br/>(backup)"]
    P -->|"+ New project"| E
    P -->|open| E["/studio/projects/:id/<br/>Project editor"]
    E --> T1["Details"]
    E --> T2["Write"]
    E --> T3["Media"]
    E --> T4["Chapters<br/>(Blog Post only)"]
    E -.->|Preview button| L["/projects/:id/<br/>live page, new tab"]
```

| Page | What you do there |
| --- | --- |
| **Dashboard** | Counts (projects, featured, blog posts), shortcuts to everything, recent edits |
| **All projects** | Cards with thumbnail, name, year, category, Featured and mode badges. Search and filter by category, mode and featured. |
| **Project editor: Details** | Name, year, category (add new inline), Featured switch, Portfolio / Blog Post switch, technologies as chips (Portfolio only, since the Blog Post page hides them), thumbnail upload, delete |
| **Project editor: Write** | The description: a markdown editor with a toolbar, a formatted preview drawn in the page (no frame, so it can't steal typing focus), and Insert image from the project's photos. **Portfolio:** shown beside the cover image. **Blog Post:** the article intro. |
| **Project editor: Chapters** (Blog Post) | The article's sections, which the live page shows as **Chapters**: title, teaser, body, takeaways, image, placeholder. Reorder, plus import and export as markdown. |
| **Project editor: Media** | **Portfolio:** Videos, Photos and Embeds sections. Photos are multi-uploaded straight to Cloudinary with progress bars, captions, drag to reorder; videos by direct upload (up to 100 MB); embeds pasted, validated and previewed. **Blog Post:** the photo library for images placed in the article (copy or insert the markdown). |

How the two modes show on the live page:

| Mode | Live project page |
| --- | --- |
| **Portfolio** | Description beside the cover → Videos → Photos → Embeds; technology list shown |
| **Blog Post** | Article intro beside the cover → Chapters (the cards); photos used inline in the text; no technology list |
| **About** | Experience roles and Education entries: edit, reorder, show or hide |

---

## 3. How it fits together

```mermaid
flowchart LR
    YOU["You<br/>(admin login + 2FA)"] --> PAGES["Studio pages<br/>(Django templates, shells only)"]
    PAGES --> JS["static/studio/*.js<br/>(built with DOM methods)"]
    JS -->|"JSON: state, update,<br/>create, delete, reorder"| API["studio/api.py<br/>(ModelForm on every save)"]
    JS -->|signed direct upload| CDN[("Cloudinary")]
    API --> DB[("Neon Postgres")]
    API -->|"save signals"| BING["IndexNow ping<br/>(once per page per 10 min)"]
    PUBLIC["Public site<br/>/projects/, /about/"] --> DB
    PUBLIC -.-> CDN
```

- **Pages are shells:** each page loads its data from the API, the same pattern that passed CodeQL in the survey editor, so nothing is read back out of the page.
- **Every write** goes through a `ModelForm` with an explicit list of fields. The models' own `clean()` runs, including the embed safety check.
- **Uploads:** photos and videos (PR 2) go **straight from the browser to Cloudinary** with a signature from the server (`projects/direct_upload.py`, shared with the admin), so Heroku's 30-second limit never applies. Thumbnails and chapter images (10 MB or less) go through the server, inside their own database savepoint, so a failed upload reports a clear error and changes nothing.
- **Saves trigger the same signals as the admin,** so the IndexNow ping for changed pages keeps working. Autosave saves often, so `_ping_indexnow` in `projects/models.py` sends each page **at most once every 10 minutes** (a cache key per URL). Saving in the admin follows the same rule.

### The API

All under `/studio/api/`. Reads are GET, writes are POST with JSON (uploads use form data).

| Path | Does |
| --- | --- |
| `dashboard/`, `projects/` | Counts and recent edits; the list for All projects |
| `projects/new/`, `categories/new/` | Create a project (name and mode) or a category (reuses one with the same name) |
| `preview/` | Markdown to sanitised HTML, for the Write preview |
| `projects/<id>/` | GET: everything the editor needs. POST: save changed fields. |
| `projects/<id>/delete/`, `projects/<id>/upload/<field>/` | Delete; upload or remove the cover image |
| `projects/<id>/cards/new/`, `cards/<cid>/`, `cards/<cid>/delete/`, `cards/<cid>/upload/image/` | Chapter add, save, delete, image |
| `projects/<id>/cards/reorder/` | New order (must list exactly this project's chapters) |
| `projects/<id>/cards/import/`, `cards/export/` | Check or add markdown chapters (append or replace); download them as `.md` |

---

## 4. The shared editor kit

`static/studio/kit.js` holds the building blocks every builder page needs:

| Piece | What it does |
| --- | --- |
| `h()` | Builds HTML with DOM methods and `textContent`, never HTML strings |
| `api()` | `fetch` with the CSRF token from the cookie and JSON in and out |
| Autosave queue | Saves each field about 0.7 s after typing stops; merges edits per item; shows *Saving… / Saved* or the reason in red |
| Field helpers | Text, number, textarea (auto-growing), select, switch, segmented buttons, chips; locked or disabled states; per-field errors |
| Drag and drop + arrows | The ⠇ handle on a laptop, ↑ ↓ everywhere; posts the new order |
| Uploads | Server upload for small images, with Remove. Signed direct upload with a progress bar comes with Media (PR 2). |
| Actions | `act()`: create, delete or reorder, with an optional confirm, then reload the state |

The survey editor was built first, with its own copy of these pieces. Moving it onto the kit is a later step (see the checklist), so the survey isn't touched while it waits for approval.

---

## 5. Access and safety

- **Who:** staff with **2FA**, the same check as the survey editor. Anyone else is redirected to the admin login, and API calls get a 403.
- **CSRF** on every write. Responses are `noindex, nofollow` and `no-store`.
- **Items are always looked up through their project,** so an id from another project gets a 404.
- **Embeds:** only one `<iframe>`, https only, from the allowed domains (YouTube, Vimeo, Instagram, Figma, itch.io, LinkedIn). That's the model's existing check.
- **Markdown preview** is rendered on the server by django-markdownify, with the site's bleach allow-list.

---

## 6. Where things live

| What | Where |
| --- | --- |
| App | `studio/` (views, api, urls, tests) |
| Pages | `templates/studio/` |
| Front end | `static/studio/kit.js` (shared) plus one script per page |
| Styles | `static/scss/scss-styles-pages/_studio.scss` |
| Content models (unchanged) | `projects/models.py` |
| Direct uploads (shared) | `projects/direct_upload.py` |

---

## 7. Testing

- **`studio/tests.py`** (`.venv\Scripts\python manage.py test studio`): access, dashboard, create, edit and validation, categories, delete, uploads with Cloudinary mocked (so nothing lands in the live library), the sanitised preview, chapters (add, edit, delete, reorder, other projects' chapters refused), import and export, and the IndexNow limit.
- **Browser click-through** in Edge on a laptop and a phone size, against the local database with a throwaway admin user. It covers every tab, autosave, the toolbar, the photo picker, import, drag and arrow reorder, the phone Write/Preview switch, no sideways scrolling, and no JavaScript errors.
