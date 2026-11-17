# Studio checklist

Progress on the website builder at `/studio/`. Design: [STUDIO_ARCHITECTURE.md](STUDIO_ARCHITECTURE.md).
Each phase ships as its own PR. A box is ticked only when it's built **and** tested.

## Phase 0: Plan and docs
- [x] Address agreed: `/studio/`
- [x] Scope agreed: projects (Portfolio and Blog Post), media, About page; the Django admin stays as a backup
- [x] Architecture doc
- [x] This checklist

## Phase 1: Foundation (PR 1)
- [x] `studio` app registered, URLs at `/studio/`
- [x] Access: staff with 2FA only; others redirected to the login; API 403; noindex and no-store
- [x] Shared editor kit `static/studio/kit.js`
- [x] Studio layout: header, navigation, save status, phone layout
- [x] Dashboard: counts, shortcuts (new project, survey editor, admin, view site). The About shortcut comes with Phase 5.
- [x] Tests: access, dashboard

## Phase 2: Projects (PR 1)
- [x] All projects: cards, search, filter by category, mode and featured
- [x] New project (named, then opens the editor)
- [x] Details tab: name, year, category (with add-new), Featured, technologies chips, Portfolio / Blog Post switch
- [x] Thumbnail upload, replace and remove (tested with Cloudinary mocked, so nothing lands in the live library)
- [x] Delete a project (with a confirmation)
- [x] Tests: create, edit, validation (duplicate name, bad year), delete, IndexNow signal still fires (now at most once per page every 10 minutes)

## Phase 3: Write and Chapters (PR 1)
- [x] Write tab: description editor with a toolbar (heading, bold, italic, link, list, quote)
- [x] Formatted preview, drawn in the page and rendered by the server's markdownify
- [x] Blog Post: Insert image from the project's photos
- [x] Chapters tab (Blog Post; the cards shown as "Chapters" on the live page): add, edit, delete, reorder (drag and arrows), image upload
- [x] Chapters: import and export as markdown (reuses `projects/markdown_import.py`)
- [x] Tabs adapt to the mode (Portfolio: Details, Write, Media · Blog Post: Details, Write, Chapters, Media)
- [x] Tests: preview sanitising, card CRUD and reorder, import

## Phase 4: Media (PR 2)
- [ ] Photos: multi-upload straight to Cloudinary, progress per file
- [ ] Photos: caption, reorder (drag and arrows), delete, copy the markdown snippet
- [ ] Videos: direct upload (100 MB or less), caption, reorder, delete
- [ ] Embeds: paste code, validate with the model's check, preview, caption, reorder, delete
- [ ] Tests: forged upload references refused, embed validation, ownership checks

## Phase 5: About page (PR 2)
- [ ] Experience: add, edit, highlights (one per line), reorder, show or hide, delete
- [ ] Education: add, edit, reorder, show or hide, delete
- [ ] Tests

## Phase 6: Quality and release
- [ ] Browser click-through on a laptop and a phone (Edge), no JavaScript errors
  - [x] PR 1: dashboard, projects list, new project, Details, Write, Chapters, delete (35 checks, desktop and phone)
  - [ ] PR 2: Media and About
- [ ] CodeQL clean
- [ ] `CLAUDE.md` and docs updated
- [ ] PRs merged and deploys checked

## Later
- [ ] Move the survey editor onto the shared kit (after the survey has launched)
- [ ] Manage categories (rename, merge)
- [ ] Site-wide text (home hero, footer bio) if wanted
