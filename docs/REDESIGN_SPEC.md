# Front-end redesign spec

Decisions agreed on 2026-11-06. Every redesign PR follows this file; if a decision changes, update it here first.

- **Base style:** the Thomas Vimare reference (monochrome, editorial, left-aligned, flat, sharp corners, spacious).
- **Borrowed from Clutch:** mixed-weight headlines, small uppercase labels, hairline dividers, blue used only for actions.
- **Borrowed from Patch:** numbered section markers (01, 02, 03…).
- **Kept from the current site:** colors, fonts, the navy-to-black gradient with the Voronoi texture, the parallax texture, the scroll progress bar.
- **Restore point:** git tag `pre-redesign` (commit `2dbac6a`). "Before" screenshots are in `design-screenshots/before/` (local only, excluded from git).

## Foundations

### Color

| Role | Value |
|---|---|
| Background | Current gradient `#060636` → `#0D0D0D` with the Voronoi texture, unchanged |
| Primary text | `#EDEFF8` |
| Muted text (descriptions, labels, captions) | `#EDEFF8` at ~60% opacity |
| Hairline dividers | `#EDEFF8` at low opacity (~12–15%), 1px |
| Buttons | `#2436BC` fill, white text; hover `#2F50E4` |
| Active nav underline, focus states, link hover | blue (`#2F50E4` / `#245CD1`) |

- Blue appears **only** on actions and active/hover/focus states. No blue panels or section bands.
- Photos and videos are the only large areas of color.

### Typography

Same three fonts, but lighter weights and slightly tight tracking.

| Role | Font | Weight | Desktop size | Line height | Tracking |
|---|---|---|---|---|---|
| Display / hero | Montserrat | 400, key words 600 | 56px | 1.0 | -0.01em |
| Heading large | Montserrat | 400–500 | 32px | 1.2 | -0.008em |
| Heading | Raleway | 500 | 28px | 1.2 | -0.007em |
| Heading small / card title | Raleway | 500 | 20–24px | 1.4 | -0.005em |
| Body | IBM Plex Sans | 400 | 18px (16px on phone) | 1.5 | -0.003em |
| Label (uppercase) | IBM Plex Sans or Montserrat | 500 | 11–12px | 1.3 | +0.12–0.16em |

- **Mixed-weight headlines:** set one or two key words in 600 and the rest in 400. Never bold a whole headline.
- Phone sizes step down. The display size is about 36–40px on phone.
- Fix: `_animations.scss` uses Red Hat Display, which is never loaded. Replace it with one of the three fonts.

### Layout and spacing

- **Alignment:** left-aligned everywhere: headings, body, labels, cards. No centered compositions.
- **Spacing steps:** 5, 10, 20, 40, 60, 120px.
- **Gap between sections:** 120px on desktop, ~80px on tablet, ~60px on phone.
- **Gap between elements:** 20px.
- **Section markers:** each main section gets a number label (`01 Technology stack`, `02 Featured projects`…) in muted text.
- **Breakpoints** (existing): phone ≤440px, tablet 441–1023px, desktop ≥1024px.

### Shape, depth and motion

- **Corners:** 0px border-radius on everything, including images, cards, buttons, inputs and the portrait. The hero arch shape is removed.
- **Shadows:** none, with one exception: a soft blue glow behind the home hero portrait.
- **Motion kept:** the parallax texture and the scroll progress bar.
- **Motion added:** subtle hover effects (image zooms ~3%, underline slides in) and a gentle fade-in as sections scroll into view. Respect `prefers-reduced-motion`.
- **Motion removed:** the animated border on buttons (`borderAnimation`) and the floating cards (`.card-float`).

## Shared pieces

### Navbar
- **Layout:** one slim row, with the AM logo on the left and Home / About / Projects / Contact on the right.
- **Active page:** a thin blue underline. No color change on the text.
- **Scroll behavior:** the nav hides when scrolling down and slides back in when scrolling up.
- **Phone menu:** the menu button opens a full-screen overlay with large left-aligned links numbered 01–04 and the social icons at the bottom.

### Footer
- **Layout:** compact columns. Logo and a short bio on the left; columns for page links and social links on the right; a copyright row underneath.
- **Keeps all current items, at smaller sizes:** Download CV link, MIT License line, Last updated date, Powered by Heroku badge.

### Closing call to action (Home and About)
- A large left-aligned line (e.g. "Have a project in mind?") and a blue "Get in touch" button, placed before the footer.

### Project card (Home and Projects)
- **Image:** square corners; zooms slightly on hover.
- **Below the image:** a small uppercase label (category · year), then the title, then a one-line description in muted text.
- The one-liner comes from the start of the project description (truncated). There's no separate summary field and no model change.

## Pages, in redesign order

### 0. Foundations (no visual change)
- Replace hard-coded fonts and colors with variables.
- Add named transparency tokens for the common `rgba(...)` values.
- Create a shared `base.html` that every page extends. This also gives the 403/404/500 pages the missing viewport tag.
- **Check:** the compiled CSS is identical or near-identical before and after.

### 1. Navbar and footer
Built as described under Shared pieces.

### 2. Home
- **Hero:** mixed-weight headline on the left, short intro, blue "About me" button, and a "↓ Selected projects" label. Portrait on the right, square with the blue glow.
- **01 Technology stack:** three numbered rows separated by hairlines (Creative multimedia, Web & app development, Cybersecurity), each with its tool logos in a line. Logos are shown in faded white and switch to their real colors on hover.
- **02 Featured projects:** two-column grid (one column on phone) using project cards, followed by a "View all projects →" link. Replaces the carousel.
- **Closing call to action.**

### 3. Projects
- **Grouping:** projects grouped by year. Each year heading shows a count and a hairline (e.g. "2025 · 14 projects").
- **Grid:** 3 columns on desktop, 2 on tablet, 1 on phone.
- **Filter:** a row of uppercase text filters (All + existing categories) at the top. The active filter gets the blue underline. Filtering is client-side, and years with no matching projects are hidden.

### 4. Project detail
- **Top of page:** a "← All projects" link, then the big title. Below it, one row of uppercase labels between hairlines: YEAR / CATEGORY / TOOLS / UPDATED. Then the intro text at reading width.
- **Videos:** Instagram-style grid of 4:5 tiles; 3 across on desktop, 2 on phone, 4px gaps.
  - On desktop, the title fades in over a dark tint on hover.
  - On phone, a small title is always visible at the bottom of each tile.
  - Clicking opens the lightbox, which shows the full uncropped video with its title and caption.
- **Photo gallery:** masonry layout; photos keep their natural shapes. The lightbox shows the photo with its title and caption.
- **Social embeds:** 3-column grid (1 on phone), each at its natural height and aligned to the top, with the caption below in muted text.
- **Section numbers:** each media type gets a numbered heading.
- **Content-card projects** (`display_mode` cards): restyled flat, with hairlines and square corners.
- **Fix:** project 35 overflows horizontally at tablet width (~844px wide in a 768px viewport).

### 5. About
- **Opening:** a large statement line, then two columns. The portrait (square, no glow) sits on the left; the bio paragraphs and social links sit on the right.
- **Experience:** two-column résumé rows separated by hairlines. Dates, company and location sit on the left in small muted text; the role and bullet points sit on the right. Education uses the same style.
- **Expertise:** four open columns, each with a hairline on top and an uppercase label, and no boxes or icons. 2×2 on tablet, stacked on phone.
- **Closing call to action.**

### 6. Contact
- **Layout:** split.
  - Left: a big "Let's work together" headline, three numbered reasons (Work with me / Collaborate / Get in touch), and a Download CV button.
  - Right: the form.
  - On phone the two sides stack, with the pitch first.
- **Inputs:** underline only, on a transparent background. The muted hairline turns blue on focus.
- **Do not change** the form fields, the honeypot field or the Turnstile widget. Restyle only. Send a real test message before merging.

### 7. Error pages (403, 404, 500)
- A huge left-aligned code (e.g. "404") with a short line, links back to Home and Projects, and the existing cat image shown smaller beside it.

## Rules for every PR

- **Wording:** Claude drafts new lines in the current voice using facts already on the site, and each PR lists every new line for approval.
- **Do not change:** the class names the JS depends on, or JS that is updated in the same PR. Key hooks: `.project-carousel`, `.project`, `.carousel-dot`, `.content-card__header`, `.content-card__body`, `.lightbox-*`, `.gallery-item`, `.video-item`, `.embed-item`, `.navbar-links`, `.toggle-nav-btn`, `.scroll-progress__bar`, `#lightbox`.
- **Do not change:** `seo_head.html` includes, `{% url %}` / `{% static %}` tags, or the contact form backend.
- **Build:** run `npm run sass` before committing. The compiled `static/css/main.css` is committed, and Heroku serves it as-is.
- **Review:** each PR comes with "after" screenshots matching the "before" set (phone, tablet and desktop) plus a local run for clicking around. The PR goes live only when merged; merging to `main` deploys immediately.

## As built: changes made during review (2026-11-06)

These override the plan above where they differ.

### Layout and rules
- **Content column:** every page is held to a centred 1440px column (`page-container`), so navbar, sections and footer share one left edge on wide screens.
- **Photo first on phones:** below 1024px the image comes before the title on Home, project pages, About and the error pages.
- **Section numbers:** shown on sections only, never on rows inside a section.
- **Card grid:** 1 column below 680px, 2 up to 1199px, 3 from 1200px. The Home featured grid stays at 2.
- **Hover:** only changes colour or underline, never layout.

### Shared pieces
- **Navbar:** 20px links (18px on tablet), SVG logo.
- **Footer:** "Last updated" shows the Heroku release date in Dubai time. This needs `runtime-dyno-metadata` to be enabled.

### Home
- **Portrait:** the cut-out portrait floats with its glow (no panel or frame).
- **Featured projects:** ordered newest first.

### Projects
- **Category filter:** with counts, kept in the URL (`?category=…`).

### Project detail
- **Lightbox:**
  - Sizes every item from its real dimensions.
  - Videos play in Plyr 3.8.5, vendored in `static/vendor/plyr` with no CDN requests.
  - Embeds open from an Expand button.
- **Blog posts:** an index and reading pane on desktop and accordion rows below 1024px, in place of the content cards.

### About
- **Statement:** sits directly above the bio, beside the photo: "Working where creativity meets technology, from short-form video to secure systems."

### Contact
- **Fields:** labelled, lightly filled square boxes rather than underline-only. The border is about 3.3:1 against the background (WCAG 1.4.11).
- **Errors:** shown per field in a single extra colour, used only for form errors (`$error: #ff8f8f`).

### Error pages
- **Template:** all three share `templates/error_base.html`.
- **Preview locally** at `/preview-error/<403|404|500>/`. This only works while `DEBUG` is on.

### Before every merge
Run the production check: `collectstatic` with `DEBUG` off (manifest storage), then render every page. A missing file referenced from CSS or JS only fails there.
