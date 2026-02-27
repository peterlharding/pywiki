# Changelog

All notable changes to PyWiki are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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

[Unreleased]: https://github.com/your-org/pywiki/compare/v0.1.3...HEAD
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
