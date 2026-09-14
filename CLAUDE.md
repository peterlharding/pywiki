# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

PyWiki is a MediaWiki-inspired wiki: FastAPI + async SQLAlchemy + Jinja2, with pages in Markdown, reStructuredText or MediaWiki-style wikitext.
`SKILLS.md` is the long-form session primer (renderer internals, search, categories, email, deployment gotchas, release process).
Read it before non-trivial work.

## Commands

The Makefile expects a `uv`-managed `.venv` in the repo root and reads `APP_PORT` from `.env` (default `8000`).
Production instances use port `8` + the instance IP's last octet (e.g. `8222`); see `setup/README.md`.

```bash
make venv && make install        # uv venv .venv; uv pip install -r requirements.txt (includes pytest + ruff)
make dev                          # uvicorn app.main:app --reload on $APP_PORT
make test                         # full pytest suite (in-memory SQLite, no external DB needed)
make lint                         # ruff check app/ tests/

# Single file / single test
.venv/bin/python -m pytest tests/test_03_pages.py -v
.venv/bin/python -m pytest tests/test_03_pages.py::test_create_markdown_page -v

# Migrations (Alembic reads DATABASE_URL from app settings, not alembic.ini)
make db-revision MSG="add_foo"    # autogenerate after changing app/models/models.py
make db-upgrade
make db-reset-dev                 # recreate local SQLite pywiki.db

make import-mw XML=export.xml ARGS="--dry-run --limit 10"   # MediaWiki XML import
```

Never pipe test output through `tail`/`head`; show the full run so failures are visible.

## Architecture

**Two parallel HTTP layers share one service layer.**
- `app/routes/*` is the JSON API under `/api/v1`, authenticated with Bearer JWTs (`get_current_user_id` in `app/core/security.py`).
- `app/ui/views.py` is the server-rendered HTML UI (one large router, templates in `app/templates/`), authenticated via an httponly `access_token` cookie.
  UI helpers `_current_user()` / `_apply_new_token()` silently refresh expired access tokens and re-set the cookie on the response.
- Both call into `app/services/*` (pages, namespaces, users, attachments, email, renderer), which take an `AsyncSession` and contain the business logic.
- `app/main.py:create_app()` wires routers; `lifespan` runs `create_all_tables()` and `_seed_defaults()` (creates `Main` + `Category` namespaces and the Main Page).

**Data model** (`app/models/models.py`): `Namespace` -> `Page` (slug is lowercase, URL-only; title stored separately) -> append-only `PageVersion` rows (every save is a new version) plus `Attachment` rows with files under `ATTACHMENT_ROOT/<ns>/<slug>/`.
Categories are not a table; they are parsed from `[[Category:Name]]` tags in content.
Redirects are page content parsed by `parse_redirect()`.

**Rendering** (`app/services/renderer.py`): `render()` dispatches to mistune (markdown), docutils (rst) or a custom wikitext parser.
Pipeline: `_expand_macros()` -> format render -> `_add_external_link_targets()` -> `_add_toc()`.
Rendered HTML is cached in `PageVersion.rendered`, prefixed with a `<!--rv:N-->` stamp; `is_cache_valid()` checks it.
**Bump `RENDERER_VERSION` whenever render output changes**, or stale cached HTML keeps being served.
Math is rendered client-side by KaTeX; the renderer only normalises delimiters.

**Database**: PostgreSQL (asyncpg) in production, SQLite (aiosqlite) for dev and tests.
Search in `pages.py` branches on dialect (`tsvector` ranking on PostgreSQL, `ILIKE` on SQLite), so keep both paths working.

**Config**: `app/core/config.py` pydantic-settings from `.env`; `get_settings()` is `lru_cache`d, so tests must call `get_settings.cache_clear()` after changing env.
Never put inline `# comments` on `.env` value lines; pydantic-settings treats them as part of the value.

**Version**: the only source of truth is `version` in `pyproject.toml`; `app/_version.py` parses it at import time.

**Setup**: all installation and deployment material (env template, production `requirements.txt`, systemd unit, nginx config, install scripts, SQL grants) lives in `setup/`; keep new setup files there.
`.gitignore` ignores `SETUP/` but re-includes `/setup/`, which matters on case-insensitive filesystems.

## Gotchas that have caused real bugs

- In UI POST handlers, `await db.commit()` before returning a `RedirectResponse`.
  `get_db` commits only after the response is sent, and the browser's follow-up GET can arrive first and see stale data.
- In loops that issue further queries, capture ORM attributes (e.g. `ns_id = ns.id`) beforehand; attributes expire after `db.execute()`.
- Never nest `<form>` elements in templates; put secondary action forms (delete, etc.) after the main form's `</form>`.
- Do not apply Jinja2 `| title` to slugs (it mangles acronyms); use `slug | replace('-', ' ')`.
- The first registered user automatically becomes admin.
- There is no `/admin` UI route; admin pages live under `/special`.

## Tests

`tests/conftest.py` forces an in-memory SQLite DB, builds the app via `create_app()` and overrides `get_db`; tests use `httpx.AsyncClient` with `asyncio_mode = "auto"`.
Helpers: `register_user`, `login_user`, `auth_headers` (Bearer, for API) and `cookie_auth` (for UI routes).
`cookie_auth()` returns `{"Cookie": "access_token=..."}`; pass it as `headers=`, not `cookies=`.

## Project conventions

- Work happens on `devel`; `main` receives release merges.
- When a feature or fix is done, mark it `[x]` in `TODO.md` with a short note and the version.
- `CHANGELOG.md` is maintained by PLH; do not edit it.
- Release notes live in `release_notes/vX.Y.Z.md`; see "Release Process" in `SKILLS.md` for the full sequence (version bump in `pyproject.toml` and the `SKILLS.md` header, tag).
