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
- 💾 **SQLite** by default (zero setup), PostgreSQL-ready

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/peterlharding/pywiki.git
cd pywiki

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Copy and edit the environment file
cp .env.example .env

# 5. Start the development server
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

The API docs are at http://localhost:8000/api/docs.

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
├── tests/
│   ├── conftest.py
│   ├── test_01_auth.py
│   ├── test_02_namespaces.py
│   └── test_03_pages.py
├── .env.example
├── requirements.txt
├── pytest.ini
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

## Running Tests

```bash
pytest tests/ -v
```

## Environment Variables

See `.env.example` for all available settings. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./pywiki.db` | Database connection string |
| `SECRET_KEY` | *(change this!)* | JWT signing secret |
| `SITE_NAME` | `PyWiki` | Displayed site name |
| `DEFAULT_NAMESPACE` | `Main` | Namespace created on first run |
| `ALLOW_REGISTRATION` | `true` | Allow public user registration |

## License

MIT
