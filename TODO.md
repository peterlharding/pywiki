# PyWiki — Feature Backlog

Items are grouped by theme and loosely prioritised within each group.
Update status with: `[ ]` pending · `[~]` in progress · `[x]` done

---

## Markup & Rendering

- [x] **Wikitext: tables** — `{| ... |}` MediaWiki table syntax rendered to `<table>`.
- [x] **Wikitext: `<code>` and `<pre>` blocks** — verbatim / syntax-highlighted blocks.
- [x] **Syntax highlighting** — Pygments server-side; fenced blocks in Markdown, `<syntaxhighlight>` / fenced / `<pre>` / space-indent in wikitext, code-block in RST. CSS served as `/static/css/pygments.css`.
- [ ] **Math rendering** — LaTeX via MathJax or KaTeX for `$...$` / `$$...$$`
      (Markdown) and `:math:` role (RST).
- [x] **Wikitext: image embedding** — `[[File:name.png|thumb|Caption]]` syntax; alignment modifiers; `<figure>` with caption or inline `<img>`; missing-file placeholder.
- [x] **Image size modifiers (Wikitext)** — `[[File:name.png|200px]]`, `[[File:name.png|300x200px]]`, `[[File:name.png|x150px]]`; sets `width`/`height` on rendered `<img>`.
- [x] **Image size suffix (Markdown)** — `![alt](attachment:file.png|200x150)` / `|200` / `|x150` emits `<img width height>` at render time.
- [x] **Live preview resolves attachments** — `/api/v1/render` passes attachment map so `[[File:]]` and `attachment:` refs display correctly in preview.
- [ ] **Live preview debounce** — reduce preview API calls; currently fires on every
      keystroke.

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
- [x] **Full-text search index** — PostgreSQL `tsvector`/`plainto_tsquery` with GIN index migration; ILIKE fallback for SQLite.


---

## Authentication & Users

- [x] **User profile page** — display name, avatar, contribution history.
- [x] **Attachment upload auth** — upload API accepts browser `httponly` cookie token or Bearer token; fixes "Not authenticated" error in editor panel.


---

## Image Upload & Embedding

- [x] **Image upload UI** — drag-and-drop / file-picker on the edit page; AJAX upload; Insert button injects format-appropriate syntax at cursor.
- [x] **Inline image rendering (Markdown)** — `![alt](attachment:filename)` shorthand resolved to attachment URL at render time.
- [x] **Inline image rendering (Wikitext)** — `[[File:name.png|thumb|Caption]]` renders as `<figure><img …></figure>`; inline variant also supported.
- [ ] **Image resizing / thumbnails** — server-side thumbnail generation on upload
      (e.g. via Pillow); serve `?width=N` variants.
- [x] **Lightbox / full-size view** — click an inline thumbnail to open the full image; close with ×, backdrop click, or Escape.
- [ ] **Inline image rendering (RST)** — `.. image::` / `.. figure::` directives with server-side attachment URL resolution.


---

## Attachments

- [x] **Image gallery on page** — image thumbnails shown below page content with lightbox.


---

## UI / UX

- [x] **Table of contents** — auto-generated from headings for all three formats; injected before first heading when ≥ 3 headings; heading anchors always added.
- [x] **Customisable home page** — `/` renders `Main/main-page` wiki page; Edit button for logged-in users; "Create main page" prompt when absent.
- [x] **Site status page** — `/special/status` shows stats, namespaces, and recent changes; linked from sidebar and Special Pages.

---

## Operations & Quality

- [x] **Alembic migrations** — replace `create_all` startup with proper versioned
      migrations; add initial migration for current schema.
- [x] **PostgreSQL support** — test and document running against PostgreSQL in
      production (async driver: `asyncpg`).

