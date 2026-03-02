# Changelog

All notable changes to PyWiki are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]


---

## [0.5.1] — 2026-03-02

### Fixed
- **RST headings stripped from rendered output** — docutils `doctitle_xform` (enabled by default) was promoting the first `===` heading to a document title and the first `---` heading to a subtitle; both were excluded from `parts["body"]` and silently dropped. Fixed by setting `doctitle_xform=False` and `sectsubtitle_xform=False` in `_render_rst()`.
- **Page creation lost on render failure** — if `render_markup()` raised an exception (e.g. a docutils error on malformed RST), the `get_db` session middleware called `session.rollback()`, discarding the newly created page. The render call is now isolated in its own `try/except` outside the DB transaction so a render failure never rolls back a page save. Same fix applied to `edit_page_submit`.
- **Attachment images broken after edit+save** — `edit_page_submit` and `create_page_submit` were calling `render_markup()` without the `attachments` map, so `attachment:filename` refs were not resolved to real URLs. The rendered HTML (with broken src attributes) was then cached and served on the next page view. Both save routes now load `att_map` from the DB before rendering.
- **Page view never cached renders for pages with attachments** — the cache-write condition `if version is None and not att_map` prevented the rendered HTML from ever being stored when a page had attachments, causing a full re-render on every view. Condition relaxed to `if version is None` — attachment URLs are resolved at render time and are stable.
- **Image delete button** — red × button added to each image thumbnail in the page gallery (logged-in users only); calls the DELETE API and removes the item from the DOM without a page reload.
- **Wikitext figures wrapped in `<p>`** — `_flush_para()` now detects lines that render to block-level HTML (`<figure>`, `<div>`, `<table>`) and emits them unwrapped.
- **CSS float layout** — clearfix `::after` on `.wiki-content`; `clear: both` on headings, `.wiki-categories`, and `.wiki-categories-bar` to prevent floated images overlapping subsequent content.

### Changed
- `RENDERER_VERSION` bumped from `9` → `11` — invalidates all stale cached HTML on next page view.
- CSS links in `base.html` now include `?v={{ app_version }}` cache-buster to force browser refresh on deploy.


---

## [0.5.0] — 2026-03-02

### Added
- **Production deployment** — `deploy/` directory with all files needed to stand up PyWiki on a live server:
  - `deploy/README.md` — 11-step guide covering system user, code deploy, venv, PostgreSQL setup, migrations, systemd, certbot SSL, nginx, firewall, and first-admin bootstrap
  - `deploy/pywiki.service` — systemd unit; runs uvicorn on `127.0.0.1:8700` as the `pywiki` system user, restarts on failure
  - `deploy/nginx-pywiki.conf` — HTTPS on port 443 → `127.0.0.1:8700`; HTTP→HTTPS redirect; ACME challenge pass-through; static files served by nginx; 55 MB upload limit
  - `deploy/.env.example` — all configuration keys with production-appropriate defaults for `expanse.performiq.com`


---

## [0.4.0] — 2026-03-02

### Added

#### Macro framework
- `_expand_macros()` pre-processor in `app/services/renderer.py` — runs before format-specific rendering on all three formats (Markdown, RST, Wikitext)
- `{{toc}}` / `{{TOC}}` / `{{ Toc }}` — general macro syntax to insert a Table of Contents at any position in the page
- `__TOC__` — MediaWiki magic word support (all formats, not just Wikitext)
- Sentinel-based insertion: macros are replaced with `<!--PYWIKI-TOC-PLACEHOLDER-->` before rendering; the TOC block is injected at that exact position in the final HTML
- RST (docutils) escapes HTML comments; the post-processor detects and unwraps the escaped sentinel from its `<p>` wrapper automatically
- Heading anchor IDs (`id=` attributes) are still added to all h1–h6 on every page regardless of whether a TOC macro is present
- 10 new tests in `tests/test_13_toc.py` covering `{{toc}}`, `__TOC__`, position, nesting, all three formats, and opt-in behaviour
- `<ref>text</ref>` / `<references />` — MediaWiki inline footnote/citation support in Wikitext: plain refs, named refs (`<ref name="...">`) and back-references (`<ref name="..." />`), inline markup inside note text, `↑` back-link, CSS styled `.references` block
- 15 new tests in `tests/test_16_refs.py` — **262 tests total**

### Changed
- **TOC is now opt-in** — the automatic `_add_toc()` injection (which fired when ≥ 3 headings were present) has been removed; a TOC only appears when `{{toc}}` or `__TOC__` is explicitly placed in the page content
- `TOC_MIN_HEADINGS` constant retained for backward-compatible imports but is no longer used internally
- `RENDERER_VERSION` bumped from 8 → 9 (invalidates all cached HTML on next page load)
- Live preview debounce reduced from 800ms → 400ms; `AbortController` now cancels in-flight render requests when new input arrives, preventing stale responses overwriting fresher ones


---

## [0.3.1] — 2026-03-02

### Fixed
- **SMTP fallback** — any SMTP error (auth failure, connection refused, TLS mismatch) is now caught, logged, and falls back to stdout; prevents HTTP 500 on mail send failure
- **Nav username link** — username in the top nav bar is now a clickable link to `/user/{username}` instead of a plain `<span>`
- **Profile page layout** — replaced cramped two-column layout with a single-column layout: details table on top, Recent Contributions below; table now uses full content width
- **Profile contributions** — Recent Contributions now shows only the most recent version the user authored per page (was listing every version separately)
- **Profile summary dash** — empty edit summaries now render as a muted `—` instead of the raw HTML string `<span class="muted">—</span>`
- **Test isolation** — `conftest.py` now forces `REQUIRE_EMAIL_VERIFICATION=false` and `SMTP_HOST=""` so live `.env` values no longer leak into the test suite


---

## [0.3.0] — 2026-03-01

### Added

#### Email Verification
- New `REQUIRE_EMAIL_VERIFICATION` setting (default `false`) — when enabled, newly registered users receive a verification email before they can log in; admins are exempt
- `GET /verify-email?token=...` — validates token, marks user verified, logs them in automatically
- `verify_pending.html` template shown after registration when verification is required
- New `User` columns: `email_verified`, `verification_token`, `reset_token`, `reset_token_expires`
- Alembic migration `a1b2c3d4e5f6` adds the four new columns

#### Password Reset
- `GET/POST /forgot-password` — accepts email address, sends a reset link (always returns success to prevent email enumeration)
- `GET/POST /reset-password?token=...` — validates token expiry (1 hour), sets new password, redirects to login
- `forgot_password.html` and `reset_password.html` templates
- "Forgot password?" link added to `login.html`; success banner shown after a reset

#### Email Service
- `app/services/email.py` — async SMTP mailer using `aiosmtplib`
- Falls back to stdout print when `SMTP_HOST` is not configured (safe for development)
- SMTP config in `Settings`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_tls`, `smtp_ssl`
- 17 new tests in `tests/test_15_email.py` covering unit helpers, UI routes, and full end-to-end flows — **237 tests total**

### Fixed
- Alembic FTS migration (`58579c489d29`) used `conn.execution_options(isolation_level="AUTOCOMMIT")` inside an active transaction, causing `InvalidRequestError` on fresh runs; fixed to use `op.get_context().autocommit_block()`


---

## [0.2.5] — 2026-03-01

### Added
- **`/special/status`** — new site info page: statistics (pages, revisions, users, namespaces, app version, renderer version), namespace list, recent changes (last 20)
- **Sidebar** — "Site status" link added between "Recent changes" and "Special pages"
- **Rename button** — 🚚 Rename button added to the page-actions bar (next to Edit) on every page view
- **Image size modifiers** — `[[File:photo.png|200px]]`, `[[File:photo.png|300x200px]]`, `[[File:photo.png|x150px]]` set `width`/`height` on rendered `<img>` tags in Wikitext
- **Markdown attachment size suffix** — `![alt](attachment:photo.png|200x150)` / `|200` / `|x150` emits `<img width="..." height="...">` at render time
- **Live preview resolves attachments** — `/api/v1/render` now accepts `slug` query param, loads page attachments from DB, passes them to `render()` so images show correctly in editor preview
- **Home page Edit button** — ✏️ Edit button shown on home page when a `Main/main-page` exists and user is logged in; "Create main page" button shown when no main page exists
- 9 new tests for size modifiers (Markdown and Wikitext) — **220 tests total**

### Fixed
- **Attachment upload auth** — upload API now accepts the browser's `httponly` cookie token in addition to Bearer tokens; fixes "Not authenticated" error when uploading via the editor panel
- **Create page namespace default** — namespace selector now correctly defaults to `Main` instead of the first alphabetical namespace (was defaulting to `Go`)
- **Duplicate `DATABASE_URL`** in `.env` — documented; second entry takes precedence

### Changed
- **Home page** is now fully customisable — renders `Main/main-page` wiki page as content; recent changes and namespace list moved to `/special/status`
- `get_current_user_id_bearer_or_cookie` dependency added to `security.py` — used by attachment routes to support both API (Bearer) and UI (cookie) auth


---

## [0.2.4] — 2026-03-01

### Added

#### Image Upload & Inline Embedding
- `render()` accepts an optional `attachments: dict[str, str]` parameter (filename → URL map)
- **Wikitext**: `[[File:name.png]]`, `[[File:name.png|thumb]]`, `[[File:name.png|thumb|Caption]]` inline image embedding; supports `left`/`right`/`center` alignment modifiers; renders as `<figure class="wiki-figure">` (thumb) or `<img class="wiki-img">` (inline); missing files show a `<span class="missing-file">` placeholder
- **Markdown**: `![alt](attachment:filename)` shorthand resolves against the page’s attachment map at render time; unknown filenames left unchanged
- **Image upload panel** on the edit page: drag-and-drop / file-picker uploads to the existing attachment API via fetch; newly uploaded files appear instantly in the attachment list
- **Insert syntax button** on each attachment: inserts format-appropriate syntax at cursor position (`[[File:...]]` for wikitext, `![...](attachment:...)` for Markdown, `.. image::` for RST)
- **Image gallery** on page view: shows thumbnails of all image attachments below page content
- **Lightbox**: click any gallery thumbnail to view full-size; close with `×` button, backdrop click, or Escape key
- CSS: `.wiki-figure`, `.wiki-thumb`, `.wiki-img`, `.wiki-gallery-*`, `.lightbox-*`, `.missing-file` added to `wiki.css`
- `tests/test_14_images.py` — 20 new tests: `[[File:]]` thumb/inline/align/missing/case-insensitive/multi, `attachment:` shorthand resolved/missing/unchanged, regression tests
- **Total: 211 tests** (was 193 at v0.2.3)

### Changed
- `RENDERER_VERSION` bumped to `8` — invalidates cached HTML so pages re-render with image support
- Version assertions in `test_12` / `test_13` made forward-compatible (`>= 7` instead of `== 7`)
- `view_page` in `views.py` now loads page attachments and passes them to `render()` and template; cache bypass when attachments are present
- `edit_page_form` in `views.py` now loads attachments for the upload panel


---

## [0.2.3] — 2026-02-28

### Added

#### Table of Contents (auto-generated)
- All rendered pages with ≥ 3 headings (h1–h6) automatically receive a floating **Contents** box before the first heading
- All heading elements (`<h1>`–`<h6>`) in rendered output now carry a unique `id=` attribute for deep-linking
- Implemented as a pure HTML post-processing step in `_add_toc()` — works identically across Markdown, RST, and Wikitext formats
- Duplicate heading text resolved by appending `-1`, `-2`, … suffixes
- Nested headings produce nested `<ol>` lists mirroring document depth
- `TOC_MIN_HEADINGS = 3` constant controls the threshold (MediaWiki convention)
- TOC CSS added to `app/static/css/wiki.css` (`.toc`, `.toc-title`, `.toc-list`)
- `tests/test_13_toc.py` — 21 new tests: threshold, anchor IDs, duplicate deduplication, nesting, injection position, all three formats, edge cases
- **Total: 193 tests** (was 173 at v0.2.2)

### Changed
- `RENDERER_VERSION` bumped to `7` — invalidates cached HTML so all pages are re-rendered with heading anchors and TOC
- Existing tests updated to match `<h1 id="...">` heading format

---

## [0.2.2] — 2026-02-28

### Added

#### Syntax Highlighting (Pygments)
- Server-side syntax highlighting via [Pygments](https://pygments.org/) 2.17+ across all three formats
- **Markdown**: fenced code blocks (` ```lang `) highlighted using Pygments `HtmlFormatter`; unknown languages fall back to plain `<pre><code>`
- **Wikitext**: four code block syntaxes supported:
  - `<syntaxhighlight lang="python">...</syntaxhighlight>` — MediaWiki native, multi-line, highlighted
  - ` ```lang\n...\n``` ` — fenced blocks (GitHub style), highlighted when lang specified
  - `<pre>...</pre>` — plain preformatted block, HTML-escaped
  - Leading-space indentation (`\ code`) — MediaWiki space-indent convention, plain `<pre>`
- **RST**: `code-block` directive highlighting enabled via docutils `syntax_highlight = "short"` setting
- Pygments CSS (`friendly` theme) served as `/static/css/pygments.css`; linked in `base.html`
- `pygments>=2.17.0` added to `requirements.txt` and `pyproject.toml`
- `tests/test_12_syntax_highlight.py` — 18 new tests covering all formats and fallback paths
- **Total: 173 tests** (was 155 at v0.2.1)

### Changed
- `RENDERER_VERSION` bumped to `6` — invalidates all cached rendered HTML to pick up code block changes

---

## [0.2.1] — 2026-02-28

### Added

#### PostgreSQL Full-Text Search
- `search_pages()` in `app/services/pages.py` now uses `to_tsvector` / `plainto_tsquery` / `ts_rank` on PostgreSQL, returning results ordered by relevance score
- Automatic dialect detection via `_db_dialect()` — falls back to `ILIKE` on SQLite (used by the test suite)
- `rank: float` field added to `SearchResult` schema and returned by `GET /api/v1/search`
- Alembic migration `58579c489d29` adds two `GIN` indexes: `ix_page_versions_fts` (content) and `ix_pages_title_fts` (title); created `CONCURRENTLY` in autocommit mode; no-op on non-PostgreSQL databases
- `tests/test_11_search.py` — 11 new tests covering UI and API search: empty query, no results, title match, content match, exclusion, snippet, namespace filter, result links, rank field, case-insensitive matching
- **Total: 155 tests** (was 144 at v0.2.0)

### Changed
- Search results are now ranked by relevance (PostgreSQL `ts_rank`) rather than alphabetical title order

### Operations
- Run `make db-upgrade` after deploying to apply the GIN index migration

---

## [0.2.0] — 2026-02-28

### Added

#### MediaWiki XML Import (`scripts/import_mediawiki.py`)
- Standalone async script to import pages from a MediaWiki XML export file
- Iterative XML parsing via `iterparse` — handles large exports without loading into memory
- Imports latest revision of each page as `wikitext` format
- MW namespace filtering: main articles (ns=0) imported by default; Talk, User, Template, Help, File, MediaWiki, Category namespaces skipped by default
- `--include-talk` flag maps Talk pages to a pywiki `Talk` namespace
- `--namespace NS` to target any pywiki namespace (default: `Main`)
- `--overwrite` flag adds a new version to existing pages instead of skipping
- `--dry-run` mode reports what would be imported without touching the database
- `--limit N` for test runs
- Auto-creates target namespace in pywiki if it doesn't exist
- `make import-mw XML=path/to/export.xml [ARGS="..."]` Makefile target

#### Category Description Pages (MediaWiki style)
- Pages in the `Category` namespace (e.g. `/wiki/Category/python`) serve as descriptions for `/category/Python`
- Category description displayed above the page list on `/category/{name}`
- "✏️ Edit description" button when description exists; "➕ Add description" when it doesn't (logged-in only)
- `Category` namespace auto-seeded at startup by `_seed_defaults()` in `app/main.py`

#### Alphabetical Category Page
- `/category/{name}` now groups pages alphabetically by first letter with H3 letter headings
- Three-column CSS layout (responsive: 2-col at 900 px, 1-col at 600 px), matching MediaWiki style
- Namespace shown in parentheses for non-Main pages

#### PostgreSQL + Alembic
- Production database switched from SQLite to PostgreSQL via `asyncpg`
- `DATABASE_URL`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` settings added
- Alembic configured with async engine; `alembic/env.py` reads URL from app settings
- Initial migration `b7ed900152d9` covers full schema
- Makefile targets: `db-upgrade`, `db-downgrade`, `db-revision`, `db-history`, `db-current`, `db-reset-dev`

#### Session Primer (`SKILLS.md`)
- `SKILLS.md` at project root documents environment setup, test commands, architecture decisions, and Makefile targets for fast onboarding of new sessions

### Changed
- **Category page layout** — replaced namespace-grouped table with alphabetical letter-grouped list
- **`Categories:` label** on page view and in wikitext renderer output now links to `/special/categories`
- **`/create` namespace dropdown** — `Category` namespace hidden from dropdown; when arriving via `?namespace=Category` prefill a hidden input is used instead, and after save the user is redirected to `/category/{title}` rather than `/wiki/Category/{slug}`
- **Edit page preview** now renders immediately on page load (was blank until first keystroke)
- **`make test`** uses `PYTHONUNBUFFERED=1 .venv/bin/python -u` for live per-test output streaming through the Windows/WSL pipe

### Fixed
- `Category` namespace seed not committed at startup when `Main` namespace already existed (`session.commit()` was inside the `Main`-namespace conditional block)
- Test suite was picking up `ALLOW_REGISTRATION=false` from `.env` — `conftest.py` now sets env vars and clears `get_settings()` lru_cache before any app imports

### Technical
- `RENDERER_VERSION` bumped to `5` — invalidates all cached wikitext rendered HTML to pick up category footer link fix
- `slugify()` made public in `app/services/pages.py` (was `_slugify`)

---

## [0.1.5] — 2026-02-27

### Added

#### Wikitext table syntax (`{| ... |}`)
- Full MediaWiki table syntax support in the wikitext renderer
- `{| attrs` — table open with optional HTML attributes (e.g. `class=`, `style=`)
- `|+ caption` — table caption rendered as `<caption>`
- `|-` — row separator
- `! h1 !! h2` — header cells; inline multi-cell with `!!`
- `| c1 || c2` — data cells; inline multi-cell with `||`
- Per-cell attributes: `| style="color:red" | Text`
- `|}` — table close
- Inline markup (bold, italic, wikilinks, external links) fully supported inside cells
- Tables default to `class="wikitable"` unless an explicit `class=` attribute is present
- Multiple tables per page, freely mixed with paragraphs, headings, and lists
- `table.wikitable` CSS styles added: borders, padding, header background, alternating row shading, caption

#### External links open in new tab
- All external links (`https://`, `http://`, `//`) in rendered output now include `target="_blank" rel="noopener noreferrer"`
- Applied via a post-processing pass at the end of `render()` — covers all three formats (markdown, RST, wikitext)
- Internal wiki links (`/wiki/...`) are unaffected

#### Bare URL auto-linking in wikitext
- Raw `https://...` URLs written without bracket syntax now render as clickable `<a>` anchors
- Matches MediaWiki behaviour; complements the existing `[URL]` and `[URL label]` forms
- Lookbehind prevents double-wrapping URLs already inside `href="..."` or brackets

#### Self-healing render cache
- `RENDERER_VERSION` constant in `renderer.py` — increment to invalidate all cached rendered HTML
- `_CACHE_STAMP` embedded as an HTML comment at the start of every cached page
- `is_cache_valid(rendered)` helper used at every cache-read site in `views.py` and `routes/pages.py`
- Stale pages (missing stamp or wrong version) are silently re-rendered on first view — no migration needed
- Current version: `4`

### Tests
- `test_10_wikitext_tables.py` — 21 new tests covering table structure, cells, headers, captions, per-cell attrs, inline markup inside cells, mixed content, multiple tables, realistic example
- **Total: 144 tests** (was 123 at v0.1.4)

---

## [0.1.4] — 2026-02-27

### Added

#### User Profile Pages
- New public route `GET /user/{username}` — user profile page, no login required
- Shows display name, admin badge, disabled badge, member since date, total edit count
- **Recent contributions table** — last 20 edits with page link, namespace, version, edit summary, and timestamp
- "Showing N of M total edits" note when edit count exceeds the displayed list
- "Edit profile" button visible to the user themselves or any admin
- "Admin view" button (links to `/special/users/{username}`) visible to admins only
- New template: `user_profile.html`
- New service functions in `users.py`: `get_user_contributions()`, `get_user_edit_count()`

#### Admin Create User
- `GET/POST /special/users/create` — admin form to create a new user account directly
- Fields: username, display name, email, password, admin checkbox
- Errors re-render the form with pre-filled values (duplicate username/email)
- "➕ Create user" button added to `/special/users` list header (admin only)
- New template: `user_create.html`

#### Author names linked to profiles site-wide
- Page view sidebar Author field → `/user/{username}`
- Page history Author column → `/user/{username}`
- Recent changes Author column → `/user/{username}`
- Home page recent changes Author column → `/user/{username}`
- Category page Author column → `/user/{username}`
- User list Username column → `/user/{username}` (was `/special/users/{username}`)
- Anonymous edits shown as plain text (not linked)

### Fixed
- `UserUpdate` schema not imported at top level in `views.py` — caused `NameError` on profile edit submit
- Pydantic `ValidationError` on invalid namespace name not caught in `ns_create_submit` — now returns HTTP 400 with form re-rendered instead of 500

### Tests
- **Test suite restructured** — `test_04_features.py` trimmed to categories/recent-changes/special-pages/printable only
- `test_05_page_move.py` — extracted page move/rename tests (9 tests)
- `test_06_redirects.py` — extracted redirect tests + 2 new (case-insensitive `#redirect`, version-view bypass) (6 tests)
- `test_07_users_ui.py` — 19 new user management UI tests (list, view, edit, create)
- `test_08_namespaces_ui.py` — 17 new namespace management UI tests (list, create, edit, delete)
- `test_09_user_profile.py` — 18 new user profile tests (access, badges, edit button visibility, contributions, author links)
- **Total: 123 tests** (was 67 at v0.1.3)


---

## [0.1.3] — 2026-02-27

### Added

#### #REDIRECT handling
- `parse_redirect(content)` in `renderer.py` — detects `#REDIRECT [[Title]]` on the first non-blank line
- Visiting a redirect page issues a **302** to the target slug in the same namespace
- `?redirect=no` query parameter bypasses the redirect to view/edit the stub directly
- "Redirected from" notice displayed on the target page with a link back to the stub
- Redirect stub content created by page move now puts `#REDIRECT` on the first line so it is detected correctly
- Wikitext category links fixed to use `/category/{name}` (was `/search?q=Category:X`)

#### Namespace Management UI
- `GET /special/namespaces` — full namespace list with page counts and edit buttons for admins
- `GET/POST /special/namespaces/create` — create namespace form (admin only)
- `GET/POST /special/namespaces/{name}/edit` — edit description and default format
- `POST /special/namespaces/{name}/delete` — delete with JS confirmation (cascades all pages)
- New templates: `ns_list.html`, `ns_manage.html`
- Link to Manage Namespaces added to Special Pages hub

#### User Management UI
- `GET /special/users` — user list table (admin only): username, display name, email, admin badge, active status, joined date
- `GET /special/users/{username}` — user profile view (email visible to admins only)
- `GET/POST /special/users/{username}/edit` — edit form; admins can toggle `is_admin` / `is_active`; users can edit their own profile
- New templates: `user_list.html`, `user_edit.html`
- Link to Users added to Special Pages Maintenance section (admin only)
- `wide-page` CSS body class added — used by user list to expand past `--max-w` constraint

#### Create Page — namespace default format
- Format tabs on the Create Page form now auto-switch when the namespace selector changes
- Correct format is also set on initial page load based on the pre-selected namespace
- `ns_format_map` dict passed from both GET and POST error paths

#### Auth / User bootstrap
- **First registered user is automatically promoted to admin** — no manual DB edit needed on a fresh install

### Fixed
- Wikitext pages showed **two** category bars — renderer emits its own footer and the template was adding a second; template bar is now suppressed for `wikitext` format
- Version number on page view showed stale value (e.g. v2 instead of v7) after a rename — `get_page()` was picking the max from an in-memory collection cleared by `db.refresh()`; fixed to query DB directly with `ORDER BY version DESC LIMIT 1`
- Edit summary field was pre-filled with the previous version's comment (e.g. "Version 2"), causing it to be re-saved on the next edit; now always starts blank
- Auto-generated "Version N" fallback comment removed from `update_page()` — empty string used instead
- `btn-sm` and `btn-danger:hover` CSS rules added (were referenced in templates but missing)

### Tests
- `test_register` updated — first user is now correctly asserted as `is_admin=True`
- `test_create_namespace_requires_admin` updated — registers a seed admin user first so test user is the second (non-admin)
- 4 new redirect tests: 302 issued, redirected-from notice, `?redirect=no` bypass, move-with-stub auto-redirect

---

## [0.1.2] — 2026-02-27

### Added

#### Special Pages — Categories
- Dedicated `/special/categories` page listing all categories alphabetically with page counts
- "Display categories starting at" filter input (submits `?from_=X`) matching MediaWiki behaviour
- Two-column display with member count (`1 member` / `N members`)
- `/special` hub updated to link to the new page instead of listing categories inline
- `get_all_categories(db, starts_with="")` service function

#### Page Move / Rename
- Move form at `GET /wiki/{ns}/{slug}/move` (logged-in only)
- **Reason** field — saved as a new `PageVersion` comment visible in page history
- **Leave a redirect** checkbox — creates a wikitext stub at the old slug pointing to the new title
- Move / Rename link added to Page tools sidebar
- `cookie_auth()` test helper added to `conftest.py` for UI route authentication

#### Tests
- `tests/test_04_features.py` extended with 9 new tests covering `/special/categories`,
  category filter, move form, redirect stub, reason in history, duplicate error, same-slug fix

### Fixed
- `[[Category:Name]]` and `.. category::` tags were not stripped from Markdown and RST content
  before rendering, causing them to appear as literal text alongside the category footer bar
- Same-slug rename collision — renaming `Health SHorts` → `Health Shorts` (same slug, different
  display title) incorrectly raised a 409 conflict; skipped when new slug equals current slug
- `rename_page()` used `db.flush()` without `db.commit()` — rename was never persisted to disk
- Global 404 handler in `main.py` used deprecated `TemplateResponse` signature
- `[project.scripts]` entry pointing at FastAPI `app` object (not a valid CLI entry point) removed
- `pytest.ini` deleted — configuration consolidated into `pyproject.toml`

### UI
- Home page layout changed from side-by-side two-column to vertical stacked sections
  (Recent Changes then Namespaces), resolving overlap at narrow widths
- Featured page block styled with background, border, padding
- Page title column in `wiki-table` given `width: 40%; min-width: 180px` to prevent squeezing


---

## [0.1.1] — 2026-02-27

### Added

#### Categories
- `[[Category:Name]]` tag support in all three formats (Markdown, Wikitext, RST `.. category::`)
- Auto-generated `/category/{name}` page listing all tagged pages alphabetically, grouped by namespace
- Category footer bar on every page view with clickable links to the category index
- `extract_categories(content, fmt)` renderer utility function
- `get_pages_in_category(db, name)` page service function

#### UI
- **Tools** sidebar section on page view: Printable version, Special pages, Upload file (logged-in)
- **Special Pages** hub (`/special`) — site statistics, namespace list, all-categories index
- **Printable version** (`/wiki/{ns}/{slug}/print`) — standalone print-optimised page with `@media print` CSS
- Recent Changes link added to base sidebar navigation
- Special Pages link added to base sidebar navigation

#### Tests
- `tests/test_04_features.py` — 25 tests covering `extract_categories()` unit tests, category page,
  recent changes, special pages, and printable version

### Fixed
- Starlette `TemplateResponse` deprecation — `request` now passed as first positional argument across
  all 21 call sites in `views.py`; `_ctx()` helper simplified accordingly
- Docutils `writer_name` deprecation — replaced with `writer=` keyword argument in `_render_rst()`


---

## [0.1.0] — 2026-02-27

### Added

#### Core
- FastAPI application factory with async SQLAlchemy ORM (SQLite via `aiosqlite`)
- Pydantic v2 settings loaded from `.env` with `pydantic-settings`
- JWT authentication: access tokens (8 h) + refresh tokens (30 d), cookie-based
- Transparent access token renewal via refresh token on all UI routes
- Password hashing with `bcrypt`

#### Content formats
- **Markdown** rendering via `mistune` (tables, strikethrough, URL auto-link plugins)
- **reStructuredText** rendering via `docutils` (html5 writer)
- **Wikitext** (MediaWiki syntax) renderer — headings `= H1 =`, bold/italic `'''`/`''`,
  `[[WikiLinks]]`, `[[Category:Name]]`, external links, nested `*`/`#` lists,
  definition lists `;term :def`, horizontal rules `----`, `{{template}}` boxes

#### Data model
- ORM models: `User`, `Namespace`, `Page`, `PageVersion`, `Attachment`
- Versioned pages — every save appends a new `PageVersion`; nothing is overwritten
- UUID primary keys throughout

#### API (`/api/v1`)
- Auth: register, login (OAuth2 password flow), refresh token, current user
- Namespaces: CRUD with admin-only create/update/delete
- Pages: list, create, read (rendered + raw), update, rename, delete, history, diff
- Attachments: upload, list, download, delete
- Search: full-text `ILIKE` across title and content
- Admin: stats, config, user management
- Render: live-preview endpoint (`GET /api/v1/render`)
- Health check: `GET /api/health`

#### UI (Jinja2 server-rendered)
- Home page with featured Main Page and recent-changes summary
- **Recent Changes** page (`/recent`) — filterable by namespace and row count
- Namespace index, page view, edit, history, diff
- Create page form
- Search results page
- Login / logout / register
- Full-width editor layout (sidebar hidden, `70vh` textarea)
- Format tabs: Markdown / reStructuredText / Wikitext on edit and create forms
- Sidebar navigation with Recent Changes link

#### Project
- `pyproject.toml` — single source of version truth (`0.1.0`), build config, ruff/mypy settings
- `app/_version.py` — reads version from installed package metadata or `pyproject.toml` fallback
- `requirements.txt` — pinned minimum versions
- `.env.example` — documented environment variables
- `Makefile` — `install`, `run`, `dev`, `test`, `lint`, `clean` targets
- `README.md` — quick-start, project structure, API overview, env vars
- `TODO.md` — feature backlog

#### Tests
- `pytest-asyncio` suite with in-memory SQLite
- `tests/test_01_auth.py` — registration, login, reserved usernames, duplicate handling
- `tests/test_02_namespaces.py` — namespace CRUD, admin checks
- `tests/test_03_pages.py` — page lifecycle (Markdown + RST), history, diff, search, live preview

### Fixed
- Duplicate `JOIN` on `Namespace` in `search_pages` causing SQLAlchemy runtime error
- `attachment_url()` missing `/api/v1` prefix
- `delete_page` route unnecessarily fetching user object
- `db_session` and `client` test fixtures using independent session factories (DB state mismatch)


---

[Unreleased]: https://github.com/peterlharding/pywiki/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/peterlharding/pywiki/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/peterlharding/pywiki/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/peterlharding/pywiki/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/peterlharding/pywiki/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/peterlharding/pywiki/compare/v0.2.5...v0.3.0
[0.2.5]: https://github.com/your-org/pywiki/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/your-org/pywiki/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/your-org/pywiki/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/your-org/pywiki/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/your-org/pywiki/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/your-org/pywiki/compare/v0.1.5...v0.2.0
[0.1.5]: https://github.com/your-org/pywiki/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/your-org/pywiki/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/your-org/pywiki/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/your-org/pywiki/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/your-org/pywiki/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/your-org/pywiki/releases/tag/v0.1.0

<!-- When cutting the next release:
  1. Rename [Unreleased] to [X.Y.Z] — YYYY-MM-DD
  2. Add a new empty [Unreleased] section above it
  3. Add [X.Y.Z]: compare link below
  4. Update pyproject.toml version
  5. git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push origin vX.Y.Z
-->
