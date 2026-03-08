# PyWiki — Session Primer (v0.6.8)

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
- **295 tests passing** (as of v0.6.8)
- Tests use **SQLite in-memory** — `conftest.py` sets `ALLOW_REGISTRATION=true` and `DATABASE_URL` env vars and clears `get_settings()` lru_cache before imports
- **NEVER pipe or tail test output** (`| tail -N`, `| head`, etc.) — always run the full command and show all output so failures are visible

## Database
- **Production**: PostgreSQL via `asyncpg` — `DATABASE_URL` in `.env`
- **Migrations**: Alembic (`alembic upgrade head`), or `make db-upgrade`
- **Tests**: SQLite in-memory, managed by `conftest.py` fixtures — never touches production DB
- **Seeding**: `_seed_defaults()` in `app/main.py` creates `Main` and `Category` namespaces on startup if absent

## Key architecture notes — DB commit before redirect (CRITICAL)
- **Always `await db.commit()` before any `RedirectResponse`** in POST handlers. The `get_db` dependency commits *after* the response is sent, but the browser follows a `303` redirect immediately — so the next GET arrives before the session commits, causing "Page not found" or stale namespace list.
- Routes that already have explicit commit: `ns_create_submit`, `ns_edit_submit`, `ns_delete_submit`, `create_page_submit`, `edit_page_submit`.
- Pattern: call `await db.commit()` after all DB work, just before building the `RedirectResponse`.

## Key architecture notes
- `get_settings()` is `@lru_cache` — call `get_settings.cache_clear()` if overriding in tests
- `RENDERER_VERSION = 12` in `app/services/renderer.py` — bump this whenever render output changes to bust cached HTML
- `slugify()` is public in `app/services/pages.py` — always lowercases; slug is for URL routing only, title is stored separately
- **Do not apply Jinja2 `| title` filter** to slugs when pre-filling Create Page form — it destroys acronyms (MQ→Mq, PERL→Perl). Use `slug | replace('-', ' ')` only.
- `/admin` UI route does **not** exist — the nav "Admin" link points to `/special`
- First registered user auto-becomes admin (`users.py` counts existing users at registration)

## MediaWiki migration helpers
- **`[[Image:name.png]]`** is a valid alias for `[[File:name.png]]` — both are handled by the wikitext renderer
- **Missing image/file links** render as `<a class="missing-file">` linking to `/special/upload?filename=...`; `view_page` enriches these with `namespace`, `page` slug and `back` URL so the upload form is pre-filled
- **Back button after create**: `GET /create` captures HTTP Referer (if it's a `/wiki/` page, not an edit/history/move page) as `back_url`; hidden field threads through POST; short-lived cookie (1 hr) set on save; `page_view` reads cookie, shows `← Back` button once then clears it
- **Bare URL auto-linking** in wikitext uses lookahead `(?=[\s<>'"]|$)` — matches URLs at end-of-line, not just space-terminated
- **Red links**: after render, `view_page` batch-queries slug existence via `page_svc.check_slugs_exist()`; missing wikilinks get `class="wikilink missing"` → styled red via `.wiki-content a.wikilink.missing { color: var(--danger) }`
- **Default namespace**: stored in `pref_namespace` cookie (1 year); auto-updated on page create; explicit ⭐ Set default button on `/special/namespaces`

## Math rendering (KaTeX)
- KaTeX `v0.16.11` loaded from CDN in `base.html` — CSS in `<head>`, JS + auto-render deferred at `</body>`
- Auto-render scans `document.body` on load; ignores `<pre>`, `<code>`, `<script>`, `<style>` tags and elements with class `no-math`
- **Wikitext**: `<math>expr</math>` → `\(expr\)` (inline); `<math display="block">expr</math>` → `\[expr\]` (display) — handled in `_render_wikitext()` block pre-pass + `_inline()` pass
- **Markdown**: `$expr$` / `$$expr$$` passed through unchanged — mistune doesn't touch them; KaTeX auto-render handles client-side
- **RST**: `:math:\`expr\`` and `.. math::` pre-processed in `_preprocess_rst_math()` before docutils sees them (prevents MathML output); inline becomes a `.. raw:: html` substitution (`<span class="math-inline">\(expr\)</span>`); block becomes `.. raw:: html \[...\]`
- `raw_enabled: True` added to docutils `settings_overrides` to allow `.. raw:: html` directives
- 9 tests in `tests/test_17_math.py`

## Renderer pipeline (`app/services/renderer.py`)
- Supports three formats: `markdown` (mistune), `rst` (docutils), `wikitext` (custom)
- **RST image syntax**: `.. image:: attachment:file.jpg` with options indented below:
  - `:width: 300px` or `:width: 50%` — scales the image
  - `:align: left|right|center` — positions/floats the image
  - Use `.. figure::` for a captioned image (blank line between options and caption text)
- **RST heading levels**: any underline char works; docutils assigns levels by order of first use — `===`, `---`, `~~~`, `^^^` are common
- **`doctitle_xform=False`**: must be set in `_render_rst` — without it, the first `===` heading is promoted to document title and stripped from `body`; fixed in RENDERER_VERSION 11
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
6. Tag: `git tag -a vX.Y.Z -m 'Release vX.Y.Z'`
7. Push tag: `git push origin vX.Y.Z`
8. If post-release commits need to be included in the tag (e.g. a same-session bugfix): `git tag -d vX.Y.Z && git tag -a vX.Y.Z -m 'Release vX.Y.Z' && git push origin :refs/tags/vX.Y.Z && git push origin vX.Y.Z`

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

## Working Practices
- **Update `TODO.md` when work is completed** — mark items `[x]` with a brief note of what was done and the version. Do this at the end of each session or when a feature/fix is confirmed working.
- **Push to origin after each session** — run `git push origin devel` before finishing. Never commit directly on the server; always push from Windows and pull on the server. If `git pull` on the server says "already up to date" but fixes aren't showing, check that the Windows commits were actually pushed (`git log --oneline origin/devel | head -5`).


---

## User Style Conventions
## Deployment
- Deploy files in `deploy/`: `README.md`, `pywiki.service`, `nginx-pywiki.conf`, `.env.example`, `requirements.txt`
- Uvicorn listens on `127.0.0.1:8222`; nginx proxies from port 443
- SSL: wildcard cert at `/etc/openssl/certs/<domain>/_.domain.fullchain.crt` + `.key`; **not** Let's Encrypt
- `deploy/requirements.txt` — use instead of `pip install -e .` on server (avoids setuptools build backend issues)
- Recent releases: v0.6.6 (colour utility classes, redirect deletion), v0.6.7 (selective export, ZIP import with attachments), v0.6.8 (delete page from editor)

### Verification command
```bash
journalctl -u pywiki -n 50 --no-pager | grep -i 'error\|exception'
```

### Fresh server install checklist
Do these steps in order:
```bash
cd /opt/pywiki
git pull origin devel
pip install -r deploy/requirements.txt
cp deploy/.env.example .env   # edit: DATABASE_URL, BASE_URL, SECRET_KEY, etc.
systemctl start pywiki        # create_all_tables() creates schema from ORM models on first start
journalctl -u pywiki -n 30 --no-pager | grep -iE 'seed|error|exception'
```
- **`create_all_tables()`** (called in `lifespan`) issues `CREATE TABLE IF NOT EXISTS` from current ORM model definitions — this correctly creates all tables including all columns for a truly empty database.
- **Do NOT run `alembic upgrade head` on a fresh install** where `create_all_tables()` already ran — it will try to `CREATE TABLE` tables that already exist and fail.
- After first start, check `journalctl` for `Seeded 'Main' namespace` and `Seeded Category namespace` to confirm seeding ran.

### Migration troubleshooting (existing DB)
If you see `UndefinedColumnError` after startup, **first verify the column actually missing** before taking action:
```bash
psql $DATABASE_URL -c "\d page_versions"
```
- If the column **is present**: the error was transient (from a request that arrived before the table was fully committed on first start). Restart the service — `systemctl stop pywiki && systemctl start pywiki` — and the error will clear.
- If the column **is genuinely missing** (DB created with an older code version): add it manually, then stamp Alembic and upgrade:
```bash
psql $DATABASE_URL -c "ALTER TABLE page_versions ADD COLUMN IF NOT EXISTS rendered TEXT;"
.venv/bin/alembic stamp b7ed900152d9   # mark DB as being at initial schema
.venv/bin/alembic upgrade head          # apply only incremental migrations
systemctl stop pywiki && systemctl start pywiki
```
- `alembic stamp <rev>` sets the `alembic_version` row without running SQL — safe when tables already exist.
- Migration revision IDs: `b7ed900152d9` (initial schema), `a1b2c3d4e5f6` (email verification columns), `58579c489d29` (FTS GIN indexes).

### Production gotchas (lessons learned)
- **Stale system `jose` package**: some distros have a Python 2 `jose.py` at `/usr/local/lib/python3.12/dist-packages/` that shadows `python-jose`; fix: `pip install --force-reinstall "python-jose[cryptography]>=3.3.0"` into the venv
- **`setuptools.backends.legacy` unavailable**: older setuptools doesn't support this build backend — use `pip install -r deploy/requirements.txt` instead of `pip install -e .`; `pyproject.toml` now uses `setuptools.build_meta`
- **`PYTHONPATH` inheritance**: systemd service sets `Environment=PYTHONPATH=/opt/pywiki` and `PATH=...` explicitly to prevent root's custom path leaking in
- **Inline `.env` comments**: pydantic-settings parses the whole line as the value — never put `# comment` on the same line as a value (e.g. `KEY=value  # comment` will fail int/bool parsing)
- **`systemctl restart` vs stop+start**: `restart` can leave old workers running if the master is stuck; use `systemctl stop && systemctl start` to guarantee a clean reload
- **Install sequence on server** (updates): `stop service` → `git pull` → `pip install -r deploy/requirements.txt` → `alembic upgrade head` → `start service`
- **`Category` namespace must not become default**: `pref_namespace` cookie is never set to `Category` (fixed v0.5.2+). On older installs where the cookie is already wrong, user clicks ⭐ Set default next to `Main` on `/special/namespaces` to fix it.
- **nginx `proxy_pass` port**: must match the uvicorn port in `pywiki.service` — both are `8222`. A mismatch causes 502 for all dynamic requests while static files still load (served directly by nginx), making the site appear partially functional
- **`BASE_URL` must be the external HTTPS URL** (e.g. `https://expanse.performiq.com`), not `http://localhost:8222`. Uvicorn's internal port is only relevant to nginx's `proxy_pass` — `BASE_URL` controls what gets embedded in attachment URLs in rendered HTML, so it must be browser-reachable

## UI / Template rules
- **Nested `<form>` elements are illegal HTML** — browsers silently discard the inner form and submit only the outermost one. Always place secondary action forms (delete, etc.) *outside* the main form's closing `</form>` tag.
- **`cookie_auth()` returns `{"Cookie": "access_token=..."}` — always pass as `headers=` not `cookies=`** in `httpx` test calls. Passing as `cookies=` does not work.
- **Import route: capture `ns.id` before the loop** — SQLAlchemy expires object attributes after `db.execute()` calls inside the loop; store `ns_id = ns.id` before any loop that issues further queries.

## Git
- Branch: `devel`
- Commit often with descriptive messages
 