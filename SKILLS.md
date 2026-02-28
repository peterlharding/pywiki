# PyWiki — Session Primer (v0.2.0)

## Project
- **Location**: `c:\src\projects\pywiki` (Windows) / `/mnt/c/src/projects/pywiki` (WSL)
- **Stack**: FastAPI + SQLAlchemy (async) + Jinja2 + PostgreSQL (prod) / SQLite (tests)
- **Python env**: `.venv` inside the project root (managed by `uv`)
- **uv path**: `/home/plh/.local/bin/uv` — not on default WSL PATH
- **Install packages**: `/home/plh/.local/bin/uv pip install <pkg> --python .venv/bin/python`

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
- Tests use **SQLite in-memory** — `conftest.py` sets `ALLOW_REGISTRATION=true` and `DATABASE_URL` env vars and clears `get_settings()` lru_cache before imports
- Never use `wsl.exe ... | tail -N` — the pipe swallows intermediate output

## Database
- **Production**: PostgreSQL via `asyncpg` — `DATABASE_URL` in `.env`
- **Migrations**: Alembic (`alembic upgrade head`), or `make db-upgrade`
- **Tests**: SQLite in-memory, managed by `conftest.py` fixtures — never touches production DB
- **Seeding**: `_seed_defaults()` in `app/main.py` creates `Main` and `Category` namespaces on startup if absent

## Key architecture notes
- `get_settings()` is `@lru_cache` — call `get_settings.cache_clear()` if overriding in tests
- `RENDERER_VERSION = 5` in `app/services/renderer.py` — bump this whenever render output changes to bust cached HTML
- `slugify()` is public in `app/services/pages.py`
- `/admin` UI route does **not** exist — the nav "Admin" link points to `/special`
- First registered user auto-becomes admin (`users.py` counts existing users at registration)

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
```

## Release Process
When cutting a new release (e.g. vX.Y.Z):
1. Update `CHANGELOG.md` — move `[Unreleased]` section to `[X.Y.Z] — YYYY-MM-DD`, add a new empty `[Unreleased]` above it, and add the `[X.Y.Z]` compare link at the bottom
2. Create `release_notes/vX.Y.Z.md` — standalone release note with highlights, full what's-new breakdown, upgrade instructions, and known limitations
3. Bump `version` in `pyproject.toml`
4. Update version in `SKILLS.md` header
5. Commit all four files: `git commit -m "chore: bump version to vX.Y.Z"`
6. Tag: `git tag vX.Y.Z`

## Git
- Branch: `devel`
- Commit often with descriptive messages
