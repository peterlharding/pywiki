# PyWiki — Feature Backlog

Items are grouped by theme and loosely prioritised within each group.
Update status with: `[ ]` pending · `[~]` in progress · `[x]` done

---

## Markup & Rendering

- [x] **Wikitext: tables** — `{| ... |}` MediaWiki table syntax rendered to `<table>`.
- [x] **Wikitext: `<code>` and `<pre>` blocks** — verbatim / syntax-highlighted blocks.
- [x] **Syntax highlighting** — Pygments server-side; fenced blocks in Markdown, `<syntaxhighlight>` / fenced / `<pre>` / space-indent in wikitext, code-block in RST. CSS served as `/static/css/pygments.css`.
- [x] **Wikitext: image embedding** — `[[File:name.png|thumb|Caption]]` syntax; alignment modifiers; `<figure>` with caption or inline `<img>`; missing-file placeholder.
- [x] **Image size modifiers (Wikitext)** — `[[File:name.png|200px]]`, `[[File:name.png|300x200px]]`, `[[File:name.png|x150px]]`; sets `width`/`height` on rendered `<img>`.
- [x] **Image size suffix (Markdown)** — `![alt](attachment:file.png|200x150)` / `|200` / `|x150` emits `<img width height>` at render time.
- [x] **Live preview resolves attachments** — `/api/v1/render` passes attachment map so `[[File:]]` and `attachment:` refs display correctly in preview.
- [x] **RST image embedding** — `.. image:: attachment:file.png` and `.. figure:: attachment:file.png` directives resolve to real URLs; `` `label <attachment:file>`_ `` links also resolved (v0.5.0)
- [x] **Special:Upload** — `/special/upload` page; select namespace + page slug, upload file, shows embed syntax for all three formats after success
- [x] **Wikitext: `<ref>` / `<references />`** — inline footnote/citation support; named refs, back-references, anchor IDs, inline markup in notes (v0.4.0)
- [x] **Live preview debounce** — 400ms debounce + `AbortController` cancels in-flight requests on new input (v0.4.0)
- [x] **Table of Contents** — opt-in via `{{toc}}` or `__TOC__` macro; no longer auto-injected (v0.4.0)
- [x] **Math rendering** — KaTeX `v0.16.11` client-side via CDN auto-render; `$...$` / `$$...$$` (Markdown), `:math:`/`.. math::` (RST), `<math>` tag (Wikitext) (RENDERER_VERSION 12)
- [ ] **Page history** — view revision history and restore previous versions.


---  

## Page Management

- [x] **Page move / redirect** — when a page is renamed, leave a redirect stub at
      the old slug so existing links continue to resolve.
- [x] **Rename button on page view** — 🚚 Rename button in the page-actions bar alongside Edit and History.
- [x] **Namespace default format** — honour `Namespace.default_format` when pre-
      filling the format selector on the Create Page form.
- [x] **Create page namespace default** — namespace selector correctly defaults to `Main`.
- [~] **Bulk import** — MediaWiki XML import done (`scripts/import_mediawiki.py`); ZIP of flat files not yet implemented.



---

## Search

- [x] **Category pages** — `[[Category:Name]]` tags on any page (all three formats)
      create a auto-generated `/category/{name}` page listing all tagged pages
      alphabetically, with namespace and last-edited date. Category links appear
      in a footer bar on every page that declares them.
- [x] **Full-text search index** — ILIKE substring matching on both SQLite and PostgreSQL; PostgreSQL FTS (`tsvector`/`plainto_tsquery`) used for ranking only; GIN index migration in place. Filters: format, author, date range, `Category:` prefix. Filter-only queries (empty search box) supported.


---

## Authentication & Users

- [x] **User profile page** — display name, avatar, contribution history.
- [x] **Attachment upload auth** — upload API accepts browser `httponly` cookie token or Bearer token; fixes "Not authenticated" error in editor panel.
- [x] **Email verification** — `REQUIRE_EMAIL_VERIFICATION=true` sends a verification link on registration; login blocked until verified (admins exempt).
- [x] **Password reset** — `/forgot-password` and `/reset-password` flow; tokens expire after 1 hour; email sent via `aiosmtplib` (stdout fallback when SMTP not configured).


---

## Image Upload & Embedding

- [x] **Image upload UI** — drag-and-drop / file-picker on the edit page; AJAX upload; Insert button injects format-appropriate syntax at cursor.
- [x] **Inline image rendering (Markdown)** — `![alt](attachment:filename)` shorthand resolved to attachment URL at render time.
- [x] **Inline image rendering (Wikitext)** — `[[File:name.png|thumb|Caption]]` renders as `<figure><img …></figure>`; inline variant also supported.
- [x] **Lightbox / full-size view** — click an inline thumbnail to open the full image; close with ×, backdrop click, or Escape.
- [x] **Inline image rendering (RST)** — `.. image::` / `.. figure::` directives with server-side attachment URL resolution; `:width:` / `:align:` options supported (v0.5.0)
- [x] **Deleting Images** — red × button on thumbnail hover; calls DELETE API; removes item from DOM and updates count without page reload (v0.5.1)


---

## Attachments

- [x] **Image gallery on page** — image thumbnails shown below page content with lightbox.


---

## UI / UX

- [x] **Table of contents** — auto-generated from headings for all three formats; injected before first heading when ≥ 3 headings; heading anchors always added.
- [x] **Customisable home page** — `/` renders `Main/main-page` wiki page; Edit button for logged-in users; "Create main page" prompt when absent.
- [x] **Site status page** — `/special/status` shows stats, namespaces, and recent changes; linked from sidebar and Special Pages.
- [x] **Default namespace preference** — per-user `pref_namespace` cookie; auto-updated on page create; ⭐ Set default button on namespace list; current default highlighted with badge (v0.5.2)
- [x] **Breadcrumb navigation** — `Home › Namespace › Page › (History/Diff/Move)` on page view, history, diff, move, and namespace index; CSS `.breadcrumb` class in `wiki.css` (v0.6.5).
- [x] **Dark mode** — CSS custom properties throughout; `prefers-color-scheme` auto-detection; 🌙/☀️ navbar toggle; `localStorage` persistence; flash-free inline script on `<html>` (v0.6.5).
- [x] **Colour utility classes** — `.text-red`, `.text-green`, `.text-blue`, `.text-orange`, `.text-purple`, `.text-teal`, `.text-grey`, `.text-gold`, `.text-muted/accent/danger/success/warn`; all adapt to dark mode; usage documented in `docs/colour-text.md`.
- [x] **Redirect deletion** — 🗑️ Delete redirect button on any redirect stub page (logged-in users); `POST /wiki/{ns}/{slug}/delete` UI route; redirects to namespace index on completion (v0.6.6).
- [x] **Page deletion from editor** — 🗑 Delete page button (red, danger-styled) at the bottom of the edit form; separate `<form>` with JS `confirm()` dialog; `POST /wiki/{ns}/{slug}/delete` deletes the page and all its history then redirects to namespace index (v0.6.8).


---

## API & Integrations

- [x] **Search by category** — `Category:Foo` query syntax; detects `Category:` prefix and filters by category tag in page content.
- [x] **Search filters** — filter by format (markdown/rst/wikitext), author username, date range (`from_date`/`to_date`); collapsible filter panel in search UI; filter-only queries (empty `q`) supported; `q=*` match-all; substring matching fixed on PostgreSQL (ILIKE, FTS for ranking only).
- [x] **Export** — `GET /wiki/{namespace}/export` downloads a ZIP of raw source files (`.md`/`.rst`/`.wiki`) plus page attachments in subdirectories; button on namespace index (logged-in users).
- [x] **Selective export** — checkboxes on namespace index and search results pages; `POST /wiki/{namespace}/export/selected` streams a ZIP of only the checked pages + their attachments; cross-namespace export from search via `POST /special/export/selected` (v0.6.7).
- [x] **Import** — `POST /wiki/{namespace}/import` accepts a ZIP archive and upserts pages by slug (creates new, adds a version to existing) and imports attachments (writes to storage, upserts `Attachment` records); import form in namespace index sidebar; result banner shows pages created/updated and attachments imported/updated (v0.6.7).


---

## Operations & Quality

- [x] **Alembic migrations** — replace `create_all` startup with proper versioned
      migrations; add initial migration for current schema.
- [x] **PostgreSQL support** — test and document running against PostgreSQL in
      production (async driver: `asyncpg`).
- [x] **Health check endpoint improvements** — `/api/health` now probes DB with `SELECT 1`, reports latency, returns `503` if DB unreachable; includes `version`, `renderer_version`, and `database.status`.
- [x] **Review Logs** — `/special/logs` admin-only page; in-memory ring buffer (500 records, INFO+); level filter dropdown; row-highlighted by severity.

