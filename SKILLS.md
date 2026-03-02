# PyWiki — Session Primer (v0.5.0)

## Project
- **Location**: `c:\src\projects\pywiki` (Windows) / `/mnt/c/src/projects/pywiki` (WSL)
- **Host OS**: Windows 11
- **Dev environment**: WSL2 (Ubuntu) + Docker Desktop (configured to start on login)
- **Stack**: FastAPI + SQLAlchemy (async) + Jinja2 + PostgreSQL (prod) / SQLite (tests)
- **Python env**: `.venv` inside the project root (managed by `uv`)
- **uv path**: `/home/plh/.local/bin/uv` — not on default WSL PATH
- **Install packages**: `/home/plh/.local/bin/uv pip install <pkg> --python .venv/bin/python`
- **PostgreSQL**: runs in Docker Desktop on `localhost:5432`; if the app fails to start with `ConnectionRefusedError`, Docker isn't running — start Docker Desktop first

## Running the app (from WSL)
```bash
cd /mnt/c/src/projects/pywiki
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# or via make:
make dev
```

## Running tests
Always run tests via `wsl.exe` from PowerShell using the Makefile to get live output:
```powershell
wsl.exe -e bash -c "cd /mnt/c/src/projects/pywiki && make test"
```
- `PYTHONUNBUFFERED=1` is set in the Makefile `test` target for live streaming through the Windows pipe
- **269 tests passing**
- Tests use **SQLite in-memory** — `conftest.py` sets `ALLOW_REGISTRATION=true` and `DATABASE_URL` env vars and clears `get_settings()` lru_cache before imports
- Never use `wsl.exe ... | tail -N` — the pipe swallows intermediate output

## Database
- **Production**: PostgreSQL via `asyncpg` — `DATABASE_URL` in `.env`
- **Migrations**: Alembic (`alembic upgrade head`), or `make db-upgrade`
- **Tests**: SQLite in-memory, managed by `conftest.py` fixtures — never touches production DB
- **Seeding**: `_seed_defaults()` in `app/main.py` creates `Main` and `Category` namespaces on startup if absent

## Key architecture notes
- `get_settings()` is `@lru_cache` — call `get_settings.cache_clear()` if overriding in tests
- `RENDERER_VERSION = 9` in `app/services/renderer.py` — bump this whenever render output changes to bust cached HTML
- `slugify()` is public in `app/services/pages.py`
- `/admin` UI route does **not** exist — the nav "Admin" link points to `/special`
- First registered user auto-becomes admin (`users.py` counts existing users at registration)

## Renderer pipeline (`app/services/renderer.py`)
- Supports three formats: `markdown` (mistune), `rst` (docutils), `wikitext` (custom)
- **Syntax highlighting**: `_highlight_code()` via Pygments; fenced blocks in Markdown, `<syntaxhighlight>`/fenced/`<pre>`/space-indent in wikitext, `syntax_highlight="short"` for RST
- **Macro pre-processor**: `_expand_macros()` runs first on raw source; replaces `{{toc}}` / `__TOC__` with sentinel `<!--PYWIKI-TOC-PLACEHOLDER-->`
- **TOC**: opt-in via `{{toc}}` or `__TOC__` macro — heading `id=` attributes are always added; `<div class="toc">` only injected at sentinel position; `TOC_MIN_HEADINGS` retained for import compat only
- **Pygments CSS**: `app/static/css/pygments.css` (friendly theme), linked in `base.html`
- Pipeline order: `_expand_macros()` → format render → `_add_external_link_targets()` → `_add_toc()`
- `render()` returns `_CACHE_STAMP + html`; `is_cache_valid()` checks the stamp

## Search (`app/services/pages.py`)
- `search_pages()` detects dialect via `_db_dialect()`: uses `tsvector`/`plainto_tsquery`/`ts_rank` on PostgreSQL, `ILIKE` fallback on SQLite
- GIN indexes: migration `58579c489d29` adds `ix_page_versions_fts` and `ix_pages_title_fts`; created `CONCURRENTLY` using `autocommit_block()` — run `make db-upgrade` on deploy
- `SearchResult` schema includes `rank: float` field

## Category system
- Categories are derived from `[[Category:Name]]` tags in page content (no separate DB model)
- **Category description pages** live in the `Category` namespace (e.g. `/wiki/Category/science`)
- `Category` namespace is **hidden** from the `/create` page dropdown but usable via `?namespace=Category` prefill
- After saving a Category description page, the user is redirected to `/category/{title}` not `/wiki/Category/{slug}`
- `Categories:` label on page view links to `/special/categories`
- Category page lists pages alphabetically grouped by first letter (3-column CSS layout)

## Makefile targets
```
make dev          # run with --reload
make test         # run pytest with live output
make lint         # ruff check
make db-upgrade   # alembic upgrade head
make db-downgrade # alembic downgrade -1
make db-revision MSG="description"  # create new migration
make db-history   # show migration history
make db-current   # show current migration
make db-reset-dev # drop + recreate dev DB
make import-mw XML=path/to/export.xml [ARGS="--dry-run --limit 10"]  # MediaWiki XML import
```

## Release Process
When cutting a new release (e.g. vX.Y.Z):
1. Update `CHANGELOG.md` — move `[Unreleased]` section to `[X.Y.Z] — YYYY-MM-DD`, add a new empty `[Unreleased]` above it, and add the `[X.Y.Z]` compare link at the bottom
2. Create `release_notes/vX.Y.Z.md` — standalone release note with highlights, full what's-new breakdown, upgrade instructions, and known limitations
3. Bump `version` in `pyproject.toml`
4. Update version in `SKILLS.md` header
5. Commit all four files: `git commit -m "chore: bump version to vX.Y.Z"`
6. Tag: `git tag vX.Y.Z` (use `git tag -f vX.Y.Z HEAD` if re-tagging after post-release doc commits)
7. Push tag: `git push origin vX.Y.Z` (use `--force` if the tag was moved after initial creation)

## Email System (`app/services/email.py`)
- `send_email(to, subject, body_text, body_html)` — sends via `aiosmtplib`; prints to stdout when `SMTP_HOST` is empty (dev mode)
- `send_verification_email()` and `send_password_reset_email()` — convenience wrappers
- SMTP config in `Settings`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_tls`, `smtp_ssl`
- `REQUIRE_EMAIL_VERIFICATION=false` (default) — set `true` to block login until email verified; admins are always exempt
- User model: `email_verified`, `verification_token`, `reset_token`, `reset_token_expires` columns (migration `a1b2c3d4e5f6`)
- Service helpers: `set_verification_token`, `verify_email_token`, `set_reset_token`, `consume_reset_token` in `users.py`
- Routes: `GET /verify-email?token=...`, `GET+POST /forgot-password`, `GET+POST /reset-password`
- Reset tokens expire after **1 hour**; timezone-naive datetimes from SQLite handled by `.replace(tzinfo=utc)`


---

## User Style Conventions
- **Markdown section endings**: always two blank lines before the closing `---` separator (i.e. two blank lines at the end of each section body)

## Deployment
- Deploy files in `deploy/`: `README.md`, `pywiki.service`, `nginx-pywiki.conf`, `.env.example`, `requirements.txt`
- Uvicorn listens on `127.0.0.1:8700`; nginx proxies from port 443
- SSL: wildcard cert at `/etc/openssl/certs/<domain>/_.domain.fullchain.crt` + `.key`; **not** Let's Encrypt
- `deploy/requirements.txt` — use instead of `pip install -e .` on server (avoids setuptools build backend issues)
- Recent releases: v0.3.1 (SMTP fallback, profile fixes), v0.4.0 (macro framework, TOC opt-in, `<ref>`, live preview debounce), v0.5.0 (production deploy/ directory)

### Production gotchas (lessons learned)
- **Stale system `jose` package**: some distros have a Python 2 `jose.py` at `/usr/local/lib/python3.12/dist-packages/` that shadows `python-jose`; fix: `pip install --force-reinstall "python-jose[cryptography]>=3.3.0"` into the venv
- **`setuptools.backends.legacy` unavailable**: older setuptools doesn't support this build backend — use `pip install -r deploy/requirements.txt` instead of `pip install -e .`; `pyproject.toml` now uses `setuptools.build_meta`
- **`PYTHONPATH` inheritance**: systemd service sets `Environment=PYTHONPATH=/opt/pywiki` and `PATH=...` explicitly to prevent root's custom path leaking in
- **Inline `.env` comments**: pydantic-settings parses the whole line as the value — never put `# comment` on the same line as a value (e.g. `KEY=value  # comment` will fail int/bool parsing)
- **`systemctl restart` vs stop+start**: `restart` can leave old workers running if the master is stuck; use `systemctl stop && systemctl start` to guarantee a clean reload
- **Install sequence on server**: `stop service` → `git pull` → `pip install -r deploy/requirements.txt` → `alembic upgrade head` → `start service`

## Git
- Branch: `devel`
- Commit often with descriptive messages
