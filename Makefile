
APP_PORT   :=  $(shell grep "^APP_PORT=" .env | sed 's/APP_PORT=//')


# -----------------------------------------------------------------------------

.PHONY: install run dev test test-v lint clean import-mw \
        db-upgrade db-downgrade db-revision db-history db-current db-reset-dev


# -----------------------------------------------------------------------------

chk-env:
	@echo "APP_PORT |${APP_PORT}|"

venv:
	uv venv .venv

install:
	uv pip install -r requirements.txt


# -----------------------------------------------------------------------------

run:
	uvicorn app.main:app --host 127.0.0.1 --port ${APP_PORT}

dev:
	uvicorn app.main:app --host 127.0.0.1 --port ${APP_PORT} --reload

test:
	PYTHONUNBUFFERED=1 .venv/bin/python -u -m pytest tests/

test-q:
	PYTHONUNBUFFERED=1 .venv/bin/python -u -m pytest tests/ -q

test-v:
	PYTHONUNBUFFERED=1 .venv/bin/python -u -m pytest tests/ -v

lint:
	ruff check app/ tests/

# Usage: make import-mw XML=path/to/export.xml [ARGS="--dry-run --limit 10"]
import-mw:
	PYTHONUNBUFFERED=1 .venv/bin/python scripts/import_mediawiki.py $(XML) $(ARGS)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	rm -f pywiki.db test_pywiki.db


# ── Database (Alembic) ─────────────────────────────────────────────────────

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-history:
	alembic history --verbose

db-current:
	alembic current

# Usage: make db-revision MSG="add_user_preferences"
db-revision:
	alembic revision --autogenerate -m "$(MSG)"

# Dev only: drop and recreate the local SQLite DB
db-reset-dev:
	rm -f pywiki.db
	DATABASE_URL=sqlite+aiosqlite:///./pywiki.db alembic upgrade head



