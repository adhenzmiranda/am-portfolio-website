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
- [x] Photos: multi-upload straight to Cloudinary, progress per file, drop files onto the section
- [x] Photos: caption, reorder (drag and arrows), delete, copy the markdown snippet
- [x] Videos: direct upload (100 MB or less), caption, reorder, delete
- [x] Embeds: paste code, validate with the model's check, preview, caption, reorder, delete
- [x] Blog Post: Media shows the photo library only (the live page shows no gallery, videos or embeds); existing videos and embeds are kept
- [x] Tests: forged upload references refused, embed validation, ownership checks

## Phase 5: About page (PR 3)
- [x] Experience: add, edit, highlights (one per line), reorder, show or hide, delete
- [x] Education: add, edit, reorder, show or hide, delete
- [x] New entries start hidden at the top, so placeholder text never reaches the live page
- [x] About in the Studio navigation and a dashboard shortcut; Preview opens `/about/`
- [x] Tests

## Phase 6: Quality and release
- [x] Browser click-through on a laptop and a phone (Edge), no JavaScript errors
  - [x] PR 1: dashboard, projects list, new project, Details, Write, Chapters, delete (35 checks, desktop and phone)
  - [x] PR 2: Media (26 checks, with Cloudinary's upload answered by the test so nothing new lands in the library)
  - [x] PR 3: About (20 checks; the local entries' order is saved first and put back afterwards)
- [ ] CodeQL clean (PR 1 and PR 2 clean; PR 3 waiting)
- [x] `CLAUDE.md` and docs updated
- [ ] PRs merged and deploys checked

## Later
- [ ] Move the survey editor onto the shared kit (after the survey has launched)
- [ ] Manage categories (rename, merge)
- [ ] Site-wide text (home hero, footer bio) if wanted
