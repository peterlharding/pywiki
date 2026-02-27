#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Jinja2 UI views (server-rendered HTML pages)
============================================
GET  /                          — home / recent changes
GET  /wiki/{namespace}/{slug}   — view a page
GET  /wiki/{namespace}/{slug}/edit   — edit a page
POST /wiki/{namespace}/{slug}/edit   — save edits
GET  /wiki/{namespace}/{slug}/history   — page history
GET  /wiki/{namespace}/{slug}/diff/{a}/{b}  — diff view
GET  /wiki/{namespace}          — namespace index
GET  /search                    — search results
GET  /login                     — login form
POST /login                     — process login
GET  /logout                    — logout
GET  /register                  — register form
POST /register                  — process registration
GET  /create                    — new page form
POST /create                    — create new page
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token, create_refresh_token,
    get_current_user_id_cookie, get_refreshed_user_id_cookie,
)
from app.schemas import PageCreate, PageUpdate, PageRename, UserCreate
from app.services import namespaces as ns_svc
from app.services import pages as page_svc
from app.services.renderer import render as render_markup
from app.services.users import (
    authenticate_user, create_user, get_user_by_id_or_none,
)


# -----------------------------------------------------------------------------

router = APIRouter(tags=["ui"])
templates = Jinja2Templates(directory="app/templates")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

async def _current_user(request: Request, db: AsyncSession):
    """Return (User | None, new_access_token | None).

    The second element is non-None when the access token was transparently
    renewed via the refresh token; callers should set it on their response.
    """
    user_id, new_token = get_refreshed_user_id_cookie(request)
    if not user_id:
        return None, None
    user = await get_user_by_id_or_none(db, user_id)
    return user, new_token


def _ctx(request: Request, user, **extra) -> dict:
    """Base template context."""
    settings = get_settings()
    return {
        "request": request,
        "user": user,
        "site_name": settings.site_name,
        "app_version": settings.app_version,
        **extra,
    }


def _login_redirect(next_url: str = "/") -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={next_url}", status_code=302)


def _apply_new_token(response, new_token: str | None, expire_minutes: int) -> None:
    """If a refreshed access token was issued, set it on the response."""
    if new_token:
        response.set_cookie(
            key="access_token",
            value=new_token,
            httponly=True,
            max_age=expire_minutes * 60,
            samesite="lax",
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Home
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    settings = get_settings()

    # Try to load the Main page of the default namespace
    featured_page = None
    try:
        ns = await ns_svc.get_namespace_by_name(db, settings.default_namespace)
        page, ver = await page_svc.get_page(db, settings.default_namespace, "main-page")
        rendered = ver.rendered or render_markup(
            ver.content, ver.format,
            namespace=settings.default_namespace,
            base_url=settings.base_url,
        )
        featured_page = {"page": page, "rendered": rendered, "namespace": settings.default_namespace}
    except HTTPException:
        pass

    # Recent changes: last 10 across all namespaces
    recent = await page_svc.get_recent_changes(db, limit=10)

    namespaces = await ns_svc.list_namespaces(db)

    resp = templates.TemplateResponse(
        "home.html",
        _ctx(request, user,
             featured_page=featured_page,
             recent=recent,
             namespaces=namespaces),
    )
    _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Recent changes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/recent", response_class=HTMLResponse)
async def recent_changes(
    request: Request,
    namespace: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    changes = await page_svc.get_recent_changes(db, limit=min(limit, 200), namespace_name=namespace)
    namespaces = await ns_svc.list_namespaces(db)
    resp = templates.TemplateResponse(
        "recent_changes.html",
        _ctx(request, user,
             changes=changes,
             namespaces=namespaces,
             selected_namespace=namespace,
             limit=limit),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Namespace index
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wiki/{namespace_name}", response_class=HTMLResponse)
async def namespace_index(
    request: Request,
    namespace_name: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    ns = await ns_svc.get_namespace_by_name(db, namespace_name)
    pages = await page_svc.list_pages(db, namespace_name, limit=500)
    count = await ns_svc.get_page_count(db, ns.id)

    resp = templates.TemplateResponse(
        "namespace.html",
        _ctx(request, user, ns=ns, pages=pages, page_count=count),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page view
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wiki/{namespace_name}/{slug}", response_class=HTMLResponse)
async def view_page(
    request: Request,
    namespace_name: str,
    slug: str,
    version: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    settings = get_settings()

    try:
        page, ver = await page_svc.get_page(db, namespace_name, slug, version=version)
    except HTTPException as e:
        if e.status_code == 404:
            # Page doesn't exist — offer to create it
            return templates.TemplateResponse(
                "page_not_found.html",
                _ctx(request, user, namespace_name=namespace_name, slug=slug),
                status_code=404,
            )
        raise

    rendered = ver.rendered
    if not rendered or version is not None:
        rendered = render_markup(
            ver.content, ver.format,
            namespace=namespace_name,
            base_url=settings.base_url,
        )
        if version is None:
            ver.rendered = rendered

    resp = templates.TemplateResponse(
        "page_view.html",
        _ctx(request, user,
             page=page,
             ver=ver,
             rendered=rendered,
             namespace_name=namespace_name,
             viewing_version=version),
    )
    _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page edit
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wiki/{namespace_name}/{slug}/edit", response_class=HTMLResponse)
async def edit_page_form(
    request: Request,
    namespace_name: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user:
        return _login_redirect(f"/wiki/{namespace_name}/{slug}/edit")

    page, ver = await page_svc.get_page(db, namespace_name, slug)

    resp = templates.TemplateResponse(
        "page_edit.html",
        _ctx(request, user,
             page=page,
             ver=ver,
             namespace_name=namespace_name,
             error=None),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/wiki/{namespace_name}/{slug}/edit", response_class=HTMLResponse)
async def edit_page_submit(
    request: Request,
    namespace_name: str,
    slug: str,
    content: str         = Form(...),
    fmt: str             = Form(default="markdown"),
    comment: str         = Form(default=""),
    db: AsyncSession     = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user:
        return _login_redirect(f"/wiki/{namespace_name}/{slug}/edit")

    data = PageUpdate(content=content, format=fmt, comment=comment)
    settings = get_settings()
    try:
        page, ver = await page_svc.update_page(db, namespace_name, slug, data, author_id=user.id)
        rendered = render_markup(ver.content, ver.format, namespace=namespace_name, base_url=settings.base_url)
        ver.rendered = rendered
        resp = RedirectResponse(url=f"/wiki/{namespace_name}/{slug}", status_code=303)
        _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
        return resp
    except HTTPException as e:
        page, ver_old = await page_svc.get_page(db, namespace_name, slug)
        resp = templates.TemplateResponse(
            "page_edit.html",
            _ctx(request, user,
                 page=page,
                 ver=ver_old,
                 namespace_name=namespace_name,
                 error=e.detail),
            status_code=400,
        )
        _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
        return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page history
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wiki/{namespace_name}/{slug}/history", response_class=HTMLResponse)
async def page_history(
    request: Request,
    namespace_name: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    page, _ = await page_svc.get_page(db, namespace_name, slug)
    versions = await page_svc.get_page_history(db, namespace_name, slug)

    resp = templates.TemplateResponse(
        "page_history.html",
        _ctx(request, user,
             page=page,
             versions=versions,
             namespace_name=namespace_name),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page diff
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wiki/{namespace_name}/{slug}/diff/{from_ver}/{to_ver}", response_class=HTMLResponse)
async def page_diff(
    request: Request,
    namespace_name: str,
    slug: str,
    from_ver: int,
    to_ver: int,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    page, _ = await page_svc.get_page(db, namespace_name, slug)
    diff = await page_svc.get_diff(db, namespace_name, slug, from_ver, to_ver)

    resp = templates.TemplateResponse(
        "page_diff.html",
        _ctx(request, user,
             page=page,
             diff=diff,
             from_ver=from_ver,
             to_ver=to_ver,
             namespace_name=namespace_name),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Create new page
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/create", response_class=HTMLResponse)
async def create_page_form(
    request: Request,
    namespace: Optional[str] = None,
    title: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user:
        return _login_redirect("/create")
    namespaces = await ns_svc.list_namespaces(db)
    resp = templates.TemplateResponse(
        "page_create.html",
        _ctx(request, user,
             namespaces=namespaces,
             prefill_namespace=namespace,
             prefill_title=title,
             error=None),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/create", response_class=HTMLResponse)
async def create_page_submit(
    request: Request,
    namespace_name: str  = Form(...),
    title: str           = Form(...),
    content: str         = Form(default=""),
    fmt: str             = Form(default="markdown"),
    comment: str         = Form(default=""),
    db: AsyncSession     = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user:
        return _login_redirect("/create")

    data = PageCreate(title=title, content=content, format=fmt, comment=comment or "Initial version")
    settings = get_settings()
    try:
        page, ver = await page_svc.create_page(db, namespace_name, data, author_id=user.id)
        rendered = render_markup(ver.content, ver.format, namespace=namespace_name, base_url=settings.base_url)
        ver.rendered = rendered
        resp = RedirectResponse(url=f"/wiki/{namespace_name}/{page.slug}", status_code=303)
        _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
        return resp
    except HTTPException as e:
        namespaces = await ns_svc.list_namespaces(db)
        resp = templates.TemplateResponse(
            "page_create.html",
            _ctx(request, user,
                 namespaces=namespaces,
                 prefill_namespace=namespace_name,
                 prefill_title=title,
                 error=e.detail),
            status_code=400,
        )
        _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
        return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Search
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/search", response_class=HTMLResponse)
async def search_view(
    request: Request,
    q: Optional[str] = None,
    namespace: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    results = []
    if q:
        results = await page_svc.search_pages(db, q, namespace_name=namespace, limit=50)
    namespaces = await ns_svc.list_namespaces(db)
    resp = templates.TemplateResponse(
        "search.html",
        _ctx(request, user,
             q=q or "",
             results=results,
             namespaces=namespaces,
             selected_namespace=namespace),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Auth UI
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/login", response_class=HTMLResponse)
async def login_form(
    request: Request,
    next: str = "/",
    db: AsyncSession = Depends(get_db),
):
    user, _ = await _current_user(request, db)
    if user:
        return RedirectResponse(url=next, status_code=302)
    return templates.TemplateResponse(
        "login.html",
        _ctx(request, user, next=next, error=None),
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    username: str    = Form(...),
    password: str    = Form(...),
    next: str        = Form(default="/"),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await authenticate_user(db, username, password)
    except HTTPException:
        return templates.TemplateResponse(
            "login.html",
            _ctx(request, None, next=next, error="Invalid username or password"),
            status_code=401,
        )

    settings = get_settings()
    token = create_access_token(user.id, extra={"username": user.username})
    refresh = create_refresh_token(user.id)
    response = RedirectResponse(url=next, status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        samesite="lax",
    )
    return response


@router.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    if not settings.allow_registration:
        return templates.TemplateResponse(
            "error.html",
            _ctx(request, None, message="Public registration is disabled."),
            status_code=403,
        )
    user, _ = await _current_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", _ctx(request, user, error=None))


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    username: str     = Form(...),
    email: str        = Form(...),
    password: str     = Form(...),
    display_name: str = Form(default=""),
    db: AsyncSession  = Depends(get_db),
):
    settings = get_settings()
    if not settings.allow_registration:
        return RedirectResponse(url="/", status_code=302)

    try:
        data = UserCreate(
            username=username,
            email=email,
            password=password,
            display_name=display_name,
        )
        user = await create_user(db, data)
    except Exception as e:
        error_msg = str(e)
        if hasattr(e, "detail"):
            error_msg = e.detail
        return templates.TemplateResponse(
            "register.html",
            _ctx(request, None, error=error_msg),
            status_code=400,
        )

    token = create_access_token(user.id, extra={"username": user.username})
    refresh = create_refresh_token(user.id)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh,
        httponly=True,
        max_age=settings.refresh_token_expire_days * 86400,
        samesite="lax",
    )
    return response


# -----------------------------------------------------------------------------
