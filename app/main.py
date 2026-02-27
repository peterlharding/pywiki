#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
PyWiki — FastAPI application factory
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.database import create_all_tables, init_db
from app.routes import auth, namespaces, pages, attachments, search, admin, render
from app.ui import views


# -----------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    init_db()
    await create_all_tables()   # safe: CREATE TABLE IF NOT EXISTS
    # Seed default namespace on first run
    await _seed_defaults()
    yield


# -----------------------------------------------------------------------------

async def _seed_defaults() -> None:
    """Create the default namespace and Main Page if they don't exist yet."""
    from app.core.database import get_session_factory
    from app.models import Namespace, Page
    from sqlalchemy import select

    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        try:
            result = await session.execute(
                select(Namespace).where(Namespace.name == settings.default_namespace)
            )
            if not result.scalar_one_or_none():
                ns = Namespace(
                    name=settings.default_namespace,
                    description="The default wiki namespace.",
                    default_format="markdown",
                )
                session.add(ns)
                await session.flush()

                main_page = Page(
                    namespace_id=ns.id,
                    title="Main Page",
                    slug="main-page",
                )
                session.add(main_page)
                await session.flush()

                from app.models.models import PageVersion
                version = PageVersion(
                    page_id=main_page.id,
                    version=1,
                    content=(
                        "# Welcome to PyWiki\n\n"
                        "PyWiki is a fast, modern wiki platform built with **FastAPI** and **Python**.\n\n"
                        "## Features\n\n"
                        "- ✅ **Markdown** and **reStructuredText (RST)** content\n"
                        "- ✅ Full revision history with diffs\n"
                        "- ✅ Namespaces (like MediaWiki)\n"
                        "- ✅ File attachments\n"
                        "- ✅ Full-text search\n"
                        "- ✅ User accounts with JWT authentication\n"
                        "- ✅ REST API + Jinja2 web UI\n\n"
                        "## Getting Started\n\n"
                        "[[Create a new page]] using the **New Page** button above, "
                        "or browse the [[Main]] namespace to see existing pages.\n"
                    ),
                    format="markdown",
                    comment="Initial welcome page",
                )
                session.add(version)
                await session.commit()
        except Exception:
            await session.rollback()


# -----------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="A MediaWiki-inspired wiki supporting Markdown and RST content.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Static files ──────────────────────────────────────────────────────

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # ── CORS ──────────────────────────────────────────────────────────────

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routers ───────────────────────────────────────────────────────

    prefix = "/api/v1"

    app.include_router(auth.router,        prefix=prefix)
    app.include_router(namespaces.router,  prefix=prefix)
    app.include_router(pages.router,       prefix=prefix)
    app.include_router(attachments.router, prefix=prefix)
    app.include_router(search.router,      prefix=prefix)
    app.include_router(admin.router,       prefix=prefix)
    app.include_router(render.router,      prefix=prefix)

    # ── UI (Jinja2) router ────────────────────────────────────────────────

    app.include_router(views.router)

    # ── Global exception handlers ─────────────────────────────────────────

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": "Not found"},
            )
        from fastapi.templating import Jinja2Templates
        tmpl = Jinja2Templates(directory="app/templates")
        return tmpl.TemplateResponse(
            "error.html",
            {"request": request, "site_name": settings.site_name, "user": None,
             "message": "The page you requested could not be found."},
            status_code=404,
        )

    @app.exception_handler(500)
    async def server_error(request: Request, exc):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )

    # ── Health check ──────────────────────────────────────────────────────

    @app.get("/api/health", tags=["system"])
    async def health():
        return {"status": "ok", "version": settings.app_version, "app": settings.app_name}

    return app


# -----------------------------------------------------------------------------

app = create_app()


# -----------------------------------------------------------------------------
