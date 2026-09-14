# PyWiki - Session Primer (v0.9.0)

## Project
- **Stack**: FastAPI + SQLAlchemy (async) + Jinja2 + PostgreSQL (prod) / SQLite (tests)
- **Location**: wherever the repo is checked out; all commands below run from the repo root
- **Dev platforms**: macOS, Linux, or Windows via WSL2; on Windows run everything inside WSL, not PowerShell
- **Python env**: `.venv` inside the project root, managed by `uv` (`make venv && make install`)
- **Install packages**: `uv pip install <pkg> --python .venv/bin/python`
  If `uv` is not on `PATH` (common in WSL), it usually lives at `~/.local/bin/uv`.
- **PostgreSQL** (only needed when running the app against Postgres): expected on `localhost:5432`, often in Docker.
  If the app fails to start with `ConnectionRefusedError`, the database isn't running.
  For a zero-setup local run, use `DATABASE_URL=sqlite+aiosqlite:///./pywiki.db` in `.env`.

## Running the app
```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# or via make (uses APP_PORT from .env):
make dev
```

## Running tests
```bash
make test
```
- `PYTHONUNBUFFERED=1` is set in the Makefile `test` target so output streams live, including through `wsl.exe` pipes on Windows
- Tests use **SQLite in-memory** - `conftest.py` sets `PYWIKI_ENV_FILE=""` (so the developer's `.env` is not read), `ALLOW_REGISTRATION=true` and `DATABASE_URL`, and clears the `get_settings()` lru_cache before imports
- **NEVER pipe or tail test output** (`| tail -N`, `| head`, etc.) - always run the full command and show all output so failures are visible

## Database
- **Production**: PostgreSQL via `asyncpg` - `DATABASE_URL` in `.env`
- **Migrations**: Alembic (`alembic upgrade head`), or `make db-upgrade`
- **Tests**: SQLite in-memory, managed by `conftest.py` fixtures - never touches production DB
- **Seeding**: `_seed_defaults()` in `app/main.py` creates `Main` and `Category` namespaces on startup if absent

## Key architecture notes - DB commit before redirect (CRITICAL)
- **Always `await db.commit()` before any `RedirectResponse`** in POST handlers. The `get_db` dependency commits *after* the response is sent, but the browser follows a `303` redirect immediately - so the next GET arrives before the session commits, causing "Page not found" or stale namespace list.
- Routes that already have explicit commit: `ns_create_submit`, `ns_edit_submit`, `ns_delete_submit`, `create_page_submit`, `edit_page_submit`.
- Pattern: call `await db.commit()` after all DB work, just before building the `RedirectResponse`.

## Key architecture notes
- `get_settings()` is `@lru_cache` - call `get_settings.cache_clear()` if overriding in tests
- `RENDERER_VERSION = 15` in `app/services/renderer.py` - bump this whenever render output changes to bust cached HTML
- `slugify()` is public in `app/services/pages.py` - always lowercases; slug is for URL routing only, title is stored separately
- **Do not apply Jinja2 `| title` filter** to slugs when pre-filling Create Page form - it destroys acronyms (MQ→Mq, PERL→Perl). Use `slug | replace('-', ' ')` only.
- `/admin` UI route does **not** exist - the nav "Admin" link points to `/special`
- First registered user auto-becomes admin (`users.py` counts existing users at registration)

## Attachments (`app/core/filetypes.py`, `app/services/attachments.py`)
- **Allowed types** come from `ATTACHMENT_EXTENSIONS` (comma/space-separated, default `png,jpg,jpeg,gif,webp,avif,svg,bmp,pdf,txt,md,csv,docx,xlsx,pptx,odt,ods,odp`); `filetypes.PROHIBITED_EXTENSIONS` (html, js, php, exe, macro-enabled Office files, ...) is not configurable and always wins. A startup warning lists prohibited types found in the setting.
- **Every write path goes through `save_attachment()`** (API upload, Special:Upload, editor panel, ZIP import): sanitizes the filename, checks type (415) and size (413), sets `content_type` from the extension (never the client), and clears the page's cached HTML via `invalidate_rendered_html()`. Delete clears it too.
- **Serving** (`routes/attachments.py::_file_response`): content type from extension, `X-Content-Type-Options: nosniff`; raster images, PDF, TXT and MD are `inline` (MD as `text/plain`), everything else (including SVG, Office files) is a download; all except PDF get a `sandbox` CSP (Chrome's PDF viewer breaks under it).
- **Link syntax for non-images**: Markdown `[label](attachment:file.pdf)`, wikitext `[[Media:file.pdf|label]]` (also `[[File:file.pdf]]` for non-images), RST `` `label <attachment:file.pdf>`_ ``. Missing files render as red `missing-file` upload links in all of these.
- **Templates** get `attachment_policy()` (Jinja global: extensions, `accept` string, `max_mb`), the `image_file` test and the `filesize` filter from `app/ui/views.py`.
- API page routes render with the attachment map (`attachment_map()`), so HTML they cache matches the UI.

## MediaWiki migration helpers
- **`[[Image:name.png]]`** is a valid alias for `[[File:name.png]]` - both are handled by the wikitext renderer
- **Missing image/file links** render as `<a class="missing-file">` linking to `/special/upload?filename=...`; `view_page` enriches these with `namespace`, `page` slug and `back` URL so the upload form is pre-filled
- **Back button after create**: `GET /create` captures HTTP Referer (if it's a `/wiki/` page, not an edit/history/move page) as `back_url`; hidden field threads through POST; short-lived cookie (1 hr) set on save; `page_view` reads cookie, shows `← Back` button once then clears it
- **Bare URL auto-linking** in wikitext uses lookahead `(?=[\s<>'"]|$)` - matches URLs at end-of-line, not just space-terminated
- **Red links**: after render, `view_page` batch-queries slug existence via `page_svc.check_slugs_exist()`; missing wikilinks get `class="wikilink missing"` → styled red via `.wiki-content a.wikilink.missing { color: var(--danger) }`
- **Default namespace**: stored in `pref_namespace` cookie (1 year); auto-updated on page create; explicit ⭐ Set default button on `/special/namespaces`

## Math rendering (KaTeX)
- KaTeX `v0.16.11` loaded from CDN in `base.html` - CSS in `<head>`, JS + auto-render deferred at `</body>`
- Auto-render scans `document.body` on load; ignores `<pre>`, `<code>`, `<script>`, `<style>` tags and elements with class `no-math`
- **Wikitext**: `<math>expr</math>` → `\(expr\)` (inline); `<math display="block">expr</math>` → `\[expr\]` (display) - handled in `_render_wikitext()` block pre-pass + `_inline()` pass
- **Markdown**: `$expr$` / `$$expr$$` passed through unchanged - mistune doesn't touch them; KaTeX auto-render handles client-side
- **RST**: `:math:\`expr\`` and `.. math::` pre-processed in `_preprocess_rst_math()` before docutils sees them (prevents MathML output); inline becomes a `.. raw:: html` substitution (`<span class="math-inline">\(expr\)</span>`); block becomes `.. raw:: html \[...\]`
- `raw_enabled: True` added to docutils `settings_overrides` to allow `.. raw:: html` directives
- 9 tests in `tests/test_17_math.py`

## Renderer pipeline (`app/services/renderer.py`)
- Supports three formats: `markdown` (mistune), `rst` (docutils), `wikitext` (custom)
- **RST image syntax**: `.. image:: attachment:file.jpg` with options indented below:
  - `:width: 300px` or `:width: 50%` - scales the image
  - `:align: left|right|center` - positions/floats the image
  - Use `.. figure::` for a captioned image (blank line between options and caption text)
- **RST heading levels**: any underline char works; docutils assigns levels by order of first use - `===`, `---`, `~~~`, `^^^` are common
- **`doctitle_xform=False`**: must be set in `_render_rst` - without it, the first `===` heading is promoted to document title and stripped from `body`; fixed in RENDERER_VERSION 11
- **Syntax highlighting**: `_highlight_code()` via Pygments; fenced blocks in Markdown, `<syntaxhighlight>`/fenced/`<pre>`/space-indent in wikitext, `syntax_highlight="short"` for RST
- **Macro pre-processor**: `_expand_macros()` runs first on raw source; replaces `{{toc}}` / `__TOC__` with sentinel `<!--PYWIKI-TOC-PLACEHOLDER-->`
- **TOC**: opt-in via `{{toc}}` or `__TOC__` macro - heading `id=` attributes are always added; `<div class="toc">` only injected at sentinel position; `TOC_MIN_HEADINGS` retained for import compat only
- **Pygments CSS**: `app/static/css/pygments.css` (friendly theme), linked in `base.html`
- Pipeline order: `_expand_macros()` → format render → `_add_external_link_targets()` → `_add_toc()`
- `render()` returns `_CACHE_STAMP + html`; `is_cache_valid()` checks the stamp

## Search (`app/services/pages.py`)
- `search_pages()` detects dialect via `_db_dialect()`: uses `tsvector`/`plainto_tsquery`/`ts_rank` on PostgreSQL, `ILIKE` fallback on SQLite
- GIN indexes: migration `58579c489d29` adds `ix_page_versions_fts` and `ix_pages_title_fts`; created `CONCURRENTLY` using `autocommit_block()` - run `make db-upgrade` on deploy
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
1. Update `CHANGELOG.md` (hand-maintained, Keep a Changelog format; there is no generator, so edit it directly).
   Add a `## [X.Y.Z] - YYYY-MM-DD` section below `[Unreleased]` (moving anything listed under `[Unreleased]` into it), point the `[Unreleased]` compare link at `vX.Y.Z...HEAD`, and add a `[X.Y.Z]: .../compare/vPREV...vX.Y.Z` link.
   This must be in the release commit so the tag includes it.
2. Create `release_notes/vX.Y.Z.md` - standalone release note with highlights, full what's-new breakdown, upgrade instructions, and known limitations
3. Bump `version` in `pyproject.toml` (`app/_version.py` reads it; there is no other version string)
4. Update version in `SKILLS.md` header
5. Commit on `devel`: `git commit -m "chore: release vX.Y.Z"`
6. Tag that commit (still on `devel`): `git tag -a vX.Y.Z -m 'Release vX.Y.Z'`
7. Merge into `main`: `git checkout main && git merge --no-ff devel -m "chore: merge devel into main for vX.Y.Z release"`
8. Push branches and tag: `git push origin devel main vX.Y.Z`
9. If post-release commits need to be included in the tag (e.g. a same-session bugfix): `git tag -d vX.Y.Z && git tag -a vX.Y.Z -m 'Release vX.Y.Z' && git push origin :refs/tags/vX.Y.Z && git push origin vX.Y.Z`

## Email System (`app/services/email.py`)
- `send_email(to, subject, body_text, body_html)` - sends via `aiosmtplib`; prints to stdout when `SMTP_HOST` is empty (dev mode)
- `send_verification_email()` and `send_password_reset_email()` - convenience wrappers
- SMTP config in `Settings`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_from`, `smtp_tls`, `smtp_ssl`
- `REQUIRE_EMAIL_VERIFICATION=false` (default) - set `true` to block login until email verified; admins are always exempt
- User model: `email_verified`, `verification_token`, `reset_token`, `reset_token_expires` columns (migration `a1b2c3d4e5f6`)
- Service helpers: `set_verification_token`, `verify_email_token`, `set_reset_token`, `consume_reset_token` in `users.py`
- Routes: `GET /verify-email?token=...`, `GET+POST /forgot-password`, `GET+POST /reset-password`
- Reset tokens expire after **1 hour**; timezone-naive datetimes from SQLite handled by `.replace(tzinfo=utc)`


---

## Working Practices
- **Update `TODO.md` when work is completed** - mark items `[x]` with a brief note of what was done and the version. Do this at the end of each session or when a feature/fix is confirmed working.
- **Push to origin after each session** - run `git push origin devel` before finishing.
  Never commit directly on the server; always push from the dev machine and pull on the server.
  If `git pull` on the server says "already up to date" but fixes aren't showing, check that the local commits were actually pushed (`git log --oneline -5 origin/devel`).


---

## Deployment
- All setup and deployment materials live in `setup/` (see `setup/README.md` for the file list): env template `env.template`, `requirements.txt`, `pywiki.service`, `nginx-pywiki.conf`, `grant.sql`, `setup-jose.sh`, and scripts `01_add_user.sh`-`03_setup_service.sh`.
  Keep new setup material there too.
- **Ports**: several instances can run on one server, each behind its own nginx site.
  Each uvicorn port is `8` + the instance IP's last octet, zero-padded (`.222` -> `8222`, `.82` -> `8082`).
  It is set once as `APP_PORT` in `.env`; `pywiki.service` reads it via `${APP_PORT}`, and nginx `proxy_pass` must match.
  Development uses `8000` (octet `.0` is never a host, so it can't clash).
- **TLS**: this is a public repo, so the shipped docs and `setup/nginx-pywiki.conf` default to Let's Encrypt (option A) and document bring-your-own certificates (option B); deployers make their own arrangements.
  The maintainer's performiq.com sites use option B with a wildcard cert at `/etc/openssl/certs/<domain>/_.domain.fullchain.crt` + `.key`; all other sites use Let's Encrypt.
  Keep maintainer-specific infrastructure out of `setup/`.
- `setup/requirements.txt` - use instead of `pip install -e .` on server (avoids setuptools build backend issues)
- Recent releases: v0.7.0 (setup/ folder, APP_PORT in systemd unit, TLS docs, fresh-install and attachment-link fixes), v0.8.0 (document attachments, ATTACHMENT_EXTENSIONS, defensive file serving), v0.9.0 (wide-screen layout, LAYOUT_MAX_WIDTH, width toggle)

### Verification command
```bash
journalctl -u pywiki -n 50 --no-pager | grep -i 'error\|exception'
```

### Fresh server install checklist
Do these steps in order:
```bash
cd /opt/pywiki
git pull origin devel
pip install -r setup/requirements.txt
cp setup/env.template .env    # edit: DATABASE_URL, BASE_URL, SECRET_KEY, etc.
systemctl start pywiki        # create_all_tables() creates schema from ORM models on first start
journalctl -u pywiki -n 30 --no-pager | grep -iE 'seed|error|exception'
```
- **`create_all_tables()`** (called in `lifespan`) issues `CREATE TABLE IF NOT EXISTS` from current ORM model definitions - this correctly creates all tables including all columns for a truly empty database.
- **Do NOT run `alembic upgrade head` on a fresh install** where `create_all_tables()` already ran - it will try to `CREATE TABLE` tables that already exist and fail.
- After first start, check `journalctl` for `Seeded 'Main' namespace` and `Seeded Category namespace` to confirm seeding ran.

### Migration troubleshooting (existing DB)
If you see `UndefinedColumnError` after startup, **first verify the column actually missing** before taking action:
```bash
psql $DATABASE_URL -c "\d page_versions"
```
- If the column **is present**: the error was transient (from a request that arrived before the table was fully committed on first start). Restart the service - `systemctl stop pywiki && systemctl start pywiki` - and the error will clear.
- If the column **is genuinely missing** (DB created with an older code version): add it manually, then stamp Alembic and upgrade:
```bash
psql $DATABASE_URL -c "ALTER TABLE page_versions ADD COLUMN IF NOT EXISTS rendered TEXT;"
.venv/bin/alembic stamp b7ed900152d9   # mark DB as being at initial schema
.venv/bin/alembic upgrade head          # apply only incremental migrations
systemctl stop pywiki && systemctl start pywiki
```
- `alembic stamp <rev>` sets the `alembic_version` row without running SQL - safe when tables already exist.
- Migration revision IDs: `b7ed900152d9` (initial schema), `a1b2c3d4e5f6` (email verification columns), `58579c489d29` (FTS GIN indexes).

### Production gotchas (lessons learned)
- **Stale system `jose` package**: some distros have a Python 2 `jose.py` at `/usr/local/lib/python3.12/dist-packages/` that shadows `python-jose`; fix: `pip install --force-reinstall "python-jose[cryptography]>=3.3.0"` into the venv
- **`setuptools.backends.legacy` unavailable**: older setuptools doesn't support this build backend - use `pip install -r setup/requirements.txt` instead of `pip install -e .`; `pyproject.toml` now uses `setuptools.build_meta`
- **`PYTHONPATH` inheritance**: systemd service sets `Environment=PYTHONPATH=/opt/pywiki` and `PATH=...` explicitly to prevent root's custom path leaking in
- **Inline `.env` comments**: systemd's `EnvironmentFile` keeps `# comment` as part of the value and pydantic-settings then fails int/bool parsing, so the service won't start - never put `# comment` on the same line as a value (verified: `MAX_ATTACHMENT_BYTES=52428800   # 50 MB` arrives as `52428800   # 50 MB`)
- **`systemctl restart` vs stop+start**: `restart` can leave old workers running if the master is stuck; use `systemctl stop && systemctl start` to guarantee a clean reload
- **Install sequence on server** (updates): `stop service` → `git pull` → `pip install -r setup/requirements.txt` → `alembic upgrade head` → `start service`
- **`Category` namespace must not become default**: `pref_namespace` cookie is never set to `Category` (fixed v0.5.2+). On older installs where the cookie is already wrong, user clicks ⭐ Set default next to `Main` on `/special/namespaces` to fix it.
- **nginx `proxy_pass` port**: must match `APP_PORT` in `.env` (which `pywiki.service` passes to uvicorn). A mismatch causes 502 for all dynamic requests while static files still load (served directly by nginx), making the site appear partially functional
- **`BASE_URL` must be the external HTTPS URL** (e.g. `https://wiki.example.com`), not `http://localhost:<APP_PORT>`. Uvicorn's internal port is only relevant to nginx's `proxy_pass` - `BASE_URL` controls what gets embedded in attachment URLs in rendered HTML, so it must be browser-reachable

## UI / Template rules
- **Layout width**: `--max-w` (nav and `.page-wrapper`) follows `html[data-width]` = `limited` | `full`. `LAYOUT_MAX_WIDTH` (`auto` | `full` | CSS length) is rendered as `html[data-layout-width]`; the pre-paint script in `base.html` sets `--limit-w` (configured length, or 90% of `screen.availWidth`, min 1200px) and the initial mode from `localStorage['pywiki-width']`. `wiki.js` runs the header toggle and hides it when the window is narrower than the limit. `editor-page` / `wide-page` bodies are always full width and have no toggle.
- **Nested `<form>` elements are illegal HTML** - browsers silently discard the inner form and submit only the outermost one. Always place secondary action forms (delete, etc.) *outside* the main form's closing `</form>` tag.
- **`cookie_auth()` returns `{"Cookie": "access_token=..."}` - always pass as `headers=` not `cookies=`** in `httpx` test calls. Passing as `cookies=` does not work.
- **Import route: capture `ns.id` before the loop** - SQLAlchemy expires object attributes after `db.execute()` calls inside the loop; store `ns_id = ns.id` before any loop that issues further queries.

## Git
- Day-to-day work happens on `devel`; `main` only receives release merges (`chore: merge devel into main for vX.Y.Z release`).
- If a fix is committed directly on `main` (e.g. while installing on a server), apply the same change to `devel` before the next release so the branches don't diverge.
- Commit often with descriptive messages
 