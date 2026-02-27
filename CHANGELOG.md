# Changelog

All notable changes to PyWiki are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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

[Unreleased]: https://github.com/your-org/pywiki/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/your-org/pywiki/releases/tag/v0.1.0

<!-- When cutting the next release:
  1. Rename [Unreleased] to [X.Y.Z] — YYYY-MM-DD
  2. Add a new empty [Unreleased] section above it
  3. Add [X.Y.Z]: compare link below
  4. Update pyproject.toml version
  5. git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push origin vX.Y.Z
-->
