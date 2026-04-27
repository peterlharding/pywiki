# PyWiki

A MediaWiki-inspired wiki built with **FastAPI** and **Python**, supporting both **Markdown** and **reStructuredText (RST)** page content.

## Features

- 📝 **Markdown** and **reStructuredText** content formats (selectable per page/version)
- 🗂️ **Namespaces** — organise pages into named namespaces (like MediaWiki)
- 📜 **Full revision history** — every save appends a new version; nothing is overwritten
- ↔️ **Diff viewer** — compare any two versions of a page
- 📎 **File attachments** — upload files to any page
- 🔍 **Full-text search** across all pages and namespaces
- 👤 **User accounts** — registration, JWT authentication, admin roles
- 🔗 **`[[WikiLink]]`** syntax — inter-page links auto-resolved to the correct URL
- ⚡ **REST API** (`/api/v1/…`) — full JSON API with OpenAPI docs
- 🖥️ **Jinja2 web UI** — server-rendered HTML with live edit preview
- 💾 **PostgreSQL** for production, **SQLite** for development (zero setup)
- 🗄️ **Alembic** migrations — version-controlled schema with autogenerate

## Quick Start

Checkout the files in the deploy sub directory. You should customize
these to suit your deloyment requirements.  For example, for 'newwiki':

```bash
# 1. Clone and enter the repo

  git clone https://github.com/peterlharding/pywiki.git newwiki
  cd newwiki


# 2. Setup Linux User and Group and DB user

The wiki is setup to use pywiki:pywiki.  If it alrady exists you are
good to go, otherwise:

  sudo useradd -r -s /bin/false -d /opt/newwiki pywiki
  sudo mkdir -p /opt/newwiki/data/attachments
  sudo chown -R pywiki:pywiki /opt/newwwiki

The database access will also need a pywiki user:

  # psql
  psql (17.2 (Ubuntu 17.2-1.pgdg22.04+1))
  Type "help" for help.
  
  root=# \du
                               List of roles
   Role name |                         Attributes
  -----------+------------------------------------------------------------
   pywiki    |

If it does not exist you will need to create it - To do so run sql/add_pywiki.sql
as the Postgres superuser.


# 3. Create and activate a virtual environment

  cd /opt/newwiki
  python -m venv .venv

Or using uv

  uv venv .venv

Then activate the venv:

## Windows
  .venv\Scripts\activate
## macOS / Linux
  source .venv/bin/activate


# 4. Install dependencies

  pip install -r requirements.txt

or:

  uv pipinstall -r requirements.txt

# 5. Copy and edit the environment file

  cp .env.example .env

## Edit .env and set DATABASE_URL for your environment (see below)
## And the PORT to use to publish both the  WEB UI and API UI

# Setup the Database

As your root Postgres user create the newwiki DB and run the script -
sql/grant.sql - to assign ownership and privileges to 'pywiki'


# 6. Apply database migrations

  alembic upgrade head


# 7. Start the development server

  uvicorn app.main:app --reload --port 8xxx
```

Open http://localhost:8xxx in your browser.

The API docs are at http://localhost:8xxx/api/docs.

## Project Structure

```
pywiki/
├── app/
│   ├── core/
│   │   ├── config.py        # Pydantic-settings configuration
│   │   ├── database.py      # SQLAlchemy async engine + session
│   │   └── security.py      # bcrypt + JWT helpers
│   ├── models/
│   │   └── models.py        # ORM models: User, Namespace, Page, PageVersion, Attachment
│   ├── schemas/
│   │   └── schemas.py       # Pydantic v2 request / response schemas
│   ├── services/
│   │   ├── users.py         # User CRUD & authentication
│   │   ├── namespaces.py    # Namespace CRUD
│   │   ├── pages.py         # Page CRUD, history, diff, search
│   │   ├── attachments.py   # File upload / download
│   │   └── renderer.py      # Markdown (mistune) + RST (docutils) renderer
│   ├── routes/              # FastAPI API routers
│   │   ├── auth.py
│   │   ├── namespaces.py
│   │   ├── pages.py
│   │   ├── attachments.py
│   │   ├── search.py
│   │   ├── admin.py
│   │   └── render.py        # Live-preview endpoint
│   ├── ui/
│   │   └── views.py         # Jinja2 HTML views (server-rendered UI)
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS and JavaScript
│       ├── css/wiki.css
│       └── js/wiki.js
├── alembic/
│   ├── env.py               # Async Alembic environment (reads DATABASE_URL from settings)
│   ├── script.py.mako       # Migration file template
│   └── versions/            # Auto-generated migration scripts
├── tests/
│   ├── conftest.py          # In-memory SQLite fixtures (never touches production DB)
│   ├── test_01_auth.py
│   ├── test_02_namespaces.py
│   └── ...
├── deploy/
│   ├── 01_add_user.py       # Setup User and Group
│   ├── 02_setup_db.sh
│   ├── 03_setup_service.sh
│   └── ...
├── alembic.ini
├── .env.example
├── requirements.txt
└── Makefile
```

## Content Formats

### Markdown

Uses [mistune](https://mistune.lepture.com/) with tables, fenced code blocks, strikethrough, and auto-URL plugins.

```markdown
# My Page

This is **bold** and _italic_.

| Col 1 | Col 2 |
|-------|-------|
| A     | B     |

[[Link to Another Page]]
```

### reStructuredText (RST)

Uses [docutils](https://docutils.sourceforge.io/).

```rst
My Page
=======

This is **strong** and *emphasis*.

.. code-block:: python

   print("Hello, PyWiki!")

`Link to Another Page <http://localhost:8000/wiki/Main/another-page>`_
```

### WikiLinks

Both formats support `[[Page Title]]` and `[[Page Title|Display Text]]` syntax.  
These are rewritten to the appropriate `/wiki/<namespace>/<slug>` URL before rendering.

## API Overview

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register a user |
| POST | `/api/v1/auth/token` | Login (OAuth2 form) |
| GET | `/api/v1/namespaces` | List namespaces |
| POST | `/api/v1/namespaces` | Create namespace (admin) |
| GET | `/api/v1/namespaces/{ns}/pages` | List pages |
| POST | `/api/v1/namespaces/{ns}/pages` | Create page (auth) |
| GET | `/api/v1/namespaces/{ns}/pages/{slug}` | Get page (rendered) |
| PUT | `/api/v1/namespaces/{ns}/pages/{slug}` | Update page (auth) |
| GET | `/api/v1/namespaces/{ns}/pages/{slug}/history` | Version history |
| GET | `/api/v1/namespaces/{ns}/pages/{slug}/diff/{a}/{b}` | Diff two versions |
| GET | `/api/v1/search?q=...` | Full-text search |
| GET | `/api/v1/render?content=...&format=markdown` | Live preview |
| GET | `/api/health` | Health check |

Full interactive docs: http://localhost:8000/api/docs

## Database Setup

### PostgreSQL (production)

```sql
-- As a PostgreSQL superuser:
CREATE USER pywiki WITH PASSWORD 'yourpassword';
CREATE DATABASE pywiki OWNER pywiki;
```

```bash
# In .env:
DATABASE_URL=postgresql+asyncpg://pywiki:yourpassword@localhost:5432/pywiki

# Apply all migrations:
alembic upgrade head
```

### SQLite (development / quick start)

```bash
# In .env:
DATABASE_URL=sqlite+aiosqlite:///./pywiki.db

# Apply all migrations:
alembic upgrade head
# or use the Makefile shortcut:
make db-reset-dev
```

### Alembic commands

```bash
alembic upgrade head          # Apply all pending migrations
alembic downgrade -1          # Roll back one migration
alembic current               # Show current revision
alembic history --verbose     # Show full migration history

# Generate a new migration after changing models:
make db-revision MSG="add_user_preferences"
```

### Tests

Tests always use an **in-memory SQLite** database regardless of `DATABASE_URL`. No external database is required to run the test suite.

```bash
pytest tests/ -v
# or:
make test
```

## Environment Variables

See `.env.example` for all available settings. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://pywiki:pywiki@localhost/pywiki` | Database connection string |
| `DB_POOL_SIZE` | `10` | PostgreSQL connection pool size |
| `DB_MAX_OVERFLOW` | `20` | PostgreSQL pool max overflow |
| `SECRET_KEY` | *(change this!)* | JWT signing secret |
| `SITE_NAME` | `PyWiki` | Displayed site name |
| `DEFAULT_NAMESPACE` | `Main` | Namespace created on first run |
| `ALLOW_REGISTRATION` | `true` | Allow public user registration |

## License

MIT
