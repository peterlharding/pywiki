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
from app.schemas import PageCreate, PageUpdate, PageRename, UserCreate, UserUpdate, NamespaceCreate, NamespaceUpdate
from app.services import namespaces as ns_svc
from app.services import pages as page_svc
from app.services.renderer import render as render_markup, extract_categories, parse_redirect, is_cache_valid
from app.services.users import (
    authenticate_user, create_user, get_user_by_id_or_none,
    list_users, get_user_by_username, update_user, set_admin, set_active,
    get_user_contributions, get_user_edit_count,
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
        # print("DEBUG _current_user: no user_id from cookie")
        return None, None
    user = await get_user_by_id_or_none(db, user_id)
    # print(f"DEBUG _current_user: user_id={user_id} user={user} is_admin={user.is_admin if user else 'N/A'}")
    return user, new_token



def _ctx(user, **extra) -> dict:
    """Base template context (request passed separately as first arg to TemplateResponse)."""
    settings = get_settings()
    return {
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
        rendered = ver.rendered if is_cache_valid(ver.rendered) else render_markup(
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
        request,
        "home.html",
        _ctx(user,
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
        request,
        "recent_changes.html",
        _ctx(user,
             changes=changes,
             namespaces=namespaces,
             selected_namespace=namespace,
             limit=limit),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Category index
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/category/{category_name}", response_class=HTMLResponse)
async def category_index(
    request: Request,
    category_name: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    pages = await page_svc.get_pages_in_category(db, category_name)

    # Look up optional description page in the "Category" namespace
    from app.services.renderer import render
    cat_slug = page_svc.slugify(category_name)
    cat_description_html: str | None = None
    try:
        _, cat_ver = await page_svc.get_page(db, "Category", cat_slug)
        cat_description_html = render(cat_ver.content, cat_ver.format,
                                      namespace="Category", base_url="")
    except Exception:
        pass

    resp = templates.TemplateResponse(
        request,
        "category.html",
        _ctx(user,
             category_name=category_name,
             cat_slug=cat_slug,
             cat_description_html=cat_description_html,
             pages=pages),
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
        request,
        "namespace.html",
        _ctx(user, ns=ns, pages=pages, page_count=count),
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
    redirect: Optional[str] = None,
    redirected_from: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    settings = get_settings()

    try:
        page, ver = await page_svc.get_page(db, namespace_name, slug, version=version)
    except HTTPException as e:
        if e.status_code == 404:
            return templates.TemplateResponse(
                request,
                "page_not_found.html",
                _ctx(user, namespace_name=namespace_name, slug=slug),
                status_code=404,
            )
        raise

    # Handle #REDIRECT — unless ?redirect=no is set (to allow viewing the stub)
    if redirect != "no" and version is None:
        target_title = parse_redirect(ver.content)
        if target_title:
            from app.services.renderer import _slugify as _rslugify
            target_slug = _rslugify(target_title)
            url = f"/wiki/{namespace_name}/{target_slug}?redirected_from={slug}"
            resp = RedirectResponse(url=url, status_code=302)
            _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
            return resp

    if is_cache_valid(ver.rendered) and version is None:
        rendered = ver.rendered
    else:
        rendered = render_markup(
            ver.content, ver.format,
            namespace=namespace_name,
            base_url=settings.base_url,
        )
        if version is None:
            ver.rendered = rendered

    categories = extract_categories(ver.content, ver.format)

    resp = templates.TemplateResponse(
        request,
        "page_view.html",
        _ctx(user,
             page=page,
             ver=ver,
             rendered=rendered,
             namespace_name=namespace_name,
             viewing_version=version,
             categories=categories,
             redirected_from=redirected_from),
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
        request,
        "page_edit.html",
        _ctx(user,
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
            request,
            "page_edit.html",
            _ctx(user,
                 page=page,
                 ver=ver_old,
                 namespace_name=namespace_name,
                 error=e.detail),
            status_code=400,
        )
        _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
        return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Page move / rename
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wiki/{namespace_name}/{slug}/move", response_class=HTMLResponse)
async def move_page_form(
    request: Request,
    namespace_name: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user:
        return _login_redirect(f"/wiki/{namespace_name}/{slug}/move")
    page, ver = await page_svc.get_page(db, namespace_name, slug)
    resp = templates.TemplateResponse(
        request,
        "page_move.html",
        _ctx(user, page=page, ver=ver, namespace_name=namespace_name, error=None),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/wiki/{namespace_name}/{slug}/move", response_class=HTMLResponse)
async def move_page_submit(
    request: Request,
    namespace_name: str,
    slug: str,
    new_title: str      = Form(...),
    reason: str         = Form(default=""),
    leave_redirect: str = Form(default=""),
    db: AsyncSession    = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user:
        return _login_redirect(f"/wiki/{namespace_name}/{slug}/move")

    from app.schemas import PageRename
    try:
        page = await page_svc.rename_page(
            db, namespace_name, slug,
            PageRename(
                new_title=new_title,
                reason=reason,
                leave_redirect=bool(leave_redirect),
            ),
            author_id=user.id,
        )
        resp = RedirectResponse(
            url=f"/wiki/{namespace_name}/{page.slug}", status_code=303
        )
        _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
        return resp
    except HTTPException as e:
        page, ver = await page_svc.get_page(db, namespace_name, slug)
        resp = templates.TemplateResponse(
            request,
            "page_move.html",
            _ctx(user, page=page, ver=ver, namespace_name=namespace_name,
                 error=e.detail, prefill_title=new_title,
                 prefill_reason=reason, prefill_redirect=bool(leave_redirect)),
            status_code=400,
        )
        _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
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
        request,
        "page_history.html",
        _ctx(user,
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
        request,
        "page_diff.html",
        _ctx(user,
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
    ns_format_map = {ns.name: ns.default_format for ns in namespaces}
    resp = templates.TemplateResponse(
        request,
        "page_create.html",
        _ctx(user,
             namespaces=namespaces,
             ns_format_map=ns_format_map,
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
        ns_format_map = {ns.name: ns.default_format for ns in namespaces}
        resp = templates.TemplateResponse(
            request,
            "page_create.html",
            _ctx(user,
                 namespaces=namespaces,
                 ns_format_map=ns_format_map,
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
        request,
        "search.html",
        _ctx(user,
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
        request,
        "login.html",
        _ctx(user, next=next, error=None),
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
            request,
            "login.html",
            _ctx(None, next=next, error="Invalid username or password"),
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
            request,
            "error.html",
            _ctx(None, message="Public registration is disabled."),
            status_code=403,
        )
    user, _ = await _current_user(request, db)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "register.html", _ctx(user, error=None))


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
            request,
            "register.html",
            _ctx(None, error=error_msg),
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Special pages — Categories
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/special/categories", response_class=HTMLResponse)
async def special_categories(
    request: Request,
    from_: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    categories = await page_svc.get_all_categories(db, starts_with=from_ or "")
    resp = templates.TemplateResponse(
        request,
        "special_categories.html",
        _ctx(user, categories=categories, from_=from_ or ""),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Special pages
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/special", response_class=HTMLResponse)
async def special_pages(request: Request, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    settings = get_settings()

    from sqlalchemy import func, select as sa_select
    from app.models import Page, PageVersion, User as UserModel

    total_pages    = (await db.execute(sa_select(func.count()).select_from(Page))).scalar_one()
    total_versions = (await db.execute(sa_select(func.count()).select_from(PageVersion))).scalar_one()
    total_users    = (await db.execute(sa_select(func.count()).select_from(UserModel))).scalar_one()
    namespaces = await ns_svc.list_namespaces(db)

    # Collect all declared categories from latest versions
    max_ver_sub = (
        sa_select(PageVersion.page_id, func.max(PageVersion.version).label("max_ver"))
        .group_by(PageVersion.page_id)
        .subquery()
    )
    q = (
        sa_select(PageVersion.content, PageVersion.format)
        .join(max_ver_sub,
              (PageVersion.page_id == max_ver_sub.c.page_id)
              & (PageVersion.version == max_ver_sub.c.max_ver))
        .where(PageVersion.content.ilike("%[[Category:%"))
    )
    rows = (await db.execute(q)).all()
    cat_set: set[str] = set()
    for content, fmt in rows:
        for c in extract_categories(content, fmt):
            cat_set.add(c)
    all_categories = sorted(cat_set, key=str.lower)

    resp = templates.TemplateResponse(
        request,
        "special_pages.html",
        _ctx(user,
             total_pages=total_pages,
             total_versions=total_versions,
             total_users=total_users,
             namespaces=namespaces,
             all_categories=all_categories),
    )
    _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Namespace management (admin only)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/special/namespaces", response_class=HTMLResponse)
async def ns_list_view(request: Request, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    namespaces_raw = await ns_svc.list_namespaces(db)
    ns_rows = []
    for ns in namespaces_raw:
        count = await ns_svc.get_page_count(db, ns.id)
        ns_rows.append({
            "name": ns.name,
            "description": ns.description,
            "default_format": ns.default_format,
            "page_count": count,
        })
    resp = templates.TemplateResponse(
        request,
        "ns_list.html",
        _ctx(user, namespaces=ns_rows),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.get("/special/namespaces/create", response_class=HTMLResponse)
async def ns_create_form(request: Request, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    resp = templates.TemplateResponse(
        request,
        "ns_manage.html",
        _ctx(user, edit_mode=False, error=None,
             prefill_name="", prefill_description="", prefill_format="markdown"),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/special/namespaces/create", response_class=HTMLResponse)
async def ns_create_submit(
    request: Request,
    name: str             = Form(...),
    description: str      = Form(default=""),
    default_format: str   = Form(default="markdown"),
    db: AsyncSession      = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    from pydantic import ValidationError as PydanticValidationError
    try:
        await ns_svc.create_namespace(db, NamespaceCreate(
            name=name, description=description, default_format=default_format
        ))
        resp = RedirectResponse(url="/special/namespaces", status_code=303)
    except (HTTPException, PydanticValidationError) as e:
        error_msg = e.detail if isinstance(e, HTTPException) else e.errors()[0]["msg"]
        resp = templates.TemplateResponse(
            request,
            "ns_manage.html",
            _ctx(user, edit_mode=False, error=error_msg,
                 prefill_name=name, prefill_description=description, prefill_format=default_format),
            status_code=400,
        )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.get("/special/namespaces/{ns_name}/edit", response_class=HTMLResponse)
async def ns_edit_form(
    request: Request,
    ns_name: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    ns = await ns_svc.get_namespace_by_name(db, ns_name)
    resp = templates.TemplateResponse(
        request,
        "ns_manage.html",
        _ctx(user, edit_mode=True, ns=ns, error=None,
             prefill_description=ns.description, prefill_format=ns.default_format),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/special/namespaces/{ns_name}/edit", response_class=HTMLResponse)
async def ns_edit_submit(
    request: Request,
    ns_name: str,
    description: str     = Form(default=""),
    default_format: str  = Form(default="markdown"),
    db: AsyncSession     = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    ns = await ns_svc.get_namespace_by_name(db, ns_name)
    try:
        await ns_svc.update_namespace(db, ns_name, NamespaceUpdate(
            description=description, default_format=default_format
        ))
        resp = RedirectResponse(url="/special/namespaces", status_code=303)
    except HTTPException as e:
        resp = templates.TemplateResponse(
            request,
            "ns_manage.html",
            _ctx(user, edit_mode=True, ns=ns, error=e.detail,
                 prefill_description=description, prefill_format=default_format),
            status_code=400,
        )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/special/namespaces/{ns_name}/delete", response_class=HTMLResponse)
async def ns_delete_submit(
    request: Request,
    ns_name: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    await ns_svc.delete_namespace(db, ns_name)
    resp = RedirectResponse(url="/special/namespaces", status_code=303)
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# User profile (public)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/user/{username}", response_class=HTMLResponse)
async def user_profile(request: Request, username: str, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    profile = await get_user_by_username(db, username)
    contributions = await get_user_contributions(db, profile.id)
    edit_count = await get_user_edit_count(db, profile.id)
    resp = templates.TemplateResponse(
        request, "user_profile.html",
        _ctx(user, profile=profile, contributions=contributions, edit_count=edit_count),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# User management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/special/users", response_class=HTMLResponse)
async def user_list_view(request: Request, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    users = await list_users(db)
    resp = templates.TemplateResponse(
        request, "user_list.html", _ctx(user, users=users),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.get("/special/users/create", response_class=HTMLResponse)
async def user_create_form(request: Request, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    resp = templates.TemplateResponse(
        request, "user_create.html",
        _ctx(user, error=None, prefill={}),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/special/users/create", response_class=HTMLResponse)
async def user_create_submit(
    request: Request,
    username: str     = Form(...),
    display_name: str = Form(default=""),
    email: str        = Form(...),
    password: str     = Form(...),
    is_admin: str     = Form(default=""),
    db: AsyncSession  = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        new_user = await create_user(db, UserCreate(
            username=username,
            display_name=display_name or username,
            email=email,
            password=password,
        ))
        if is_admin == "1":
            await set_admin(db, username, True)
        await db.commit()
        resp = RedirectResponse(url=f"/special/users/{username}", status_code=303)
    except HTTPException as e:
        resp = templates.TemplateResponse(
            request, "user_create.html",
            _ctx(user, error=e.detail,
                 prefill={"username": username, "display_name": display_name,
                          "email": email, "is_admin": is_admin == "1"}),
            status_code=400,
        )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.get("/special/users/{username}", response_class=HTMLResponse)
async def user_view(request: Request, username: str, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    target = await get_user_by_username(db, username)
    resp = templates.TemplateResponse(
        request, "user_edit.html",
        _ctx(user, u=target, edit_mode=False, error=None, prefill={}),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.get("/special/users/{username}/edit", response_class=HTMLResponse)
async def user_edit_form(request: Request, username: str, db: AsyncSession = Depends(get_db)):
    user, new_token = await _current_user(request, db)
    if not user or (not user.is_admin and user.username != username):
        raise HTTPException(status_code=403, detail="Not authorised")
    target = await get_user_by_username(db, username)
    resp = templates.TemplateResponse(
        request, "user_edit.html",
        _ctx(user, u=target, edit_mode=True, error=None, prefill={}),
    )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


@router.post("/special/users/{username}/edit", response_class=HTMLResponse)
async def user_edit_submit(
    request: Request,
    username: str,
    display_name: str  = Form(default=""),
    email: str         = Form(default=""),
    new_password: str  = Form(default=""),
    is_admin: str      = Form(default=""),
    is_active: str     = Form(default=""),
    db: AsyncSession   = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    if not user or (not user.is_admin and user.username != username):
        raise HTTPException(status_code=403, detail="Not authorised")

    target = await get_user_by_username(db, username)
    try:
        update_data = UserUpdate(
            display_name=display_name or None,
            email=email or None,
            password=new_password or None,
        )
        await update_user(db, target.id, update_data)
        if user.is_admin:
            await set_admin(db, username, is_admin == "1")
            await set_active(db, username, is_active == "1")
        await db.commit()
        resp = RedirectResponse(url=f"/special/users/{username}", status_code=303)
    except HTTPException as e:
        target = await get_user_by_username(db, username)
        resp = templates.TemplateResponse(
            request, "user_edit.html",
            _ctx(user, u=target, edit_mode=True, error=e.detail,
                 prefill={"display_name": display_name, "email": email}),
            status_code=400,
        )
    _apply_new_token(resp, new_token, get_settings().access_token_expire_minutes)
    return resp


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Printable version
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/wiki/{namespace_name}/{slug}/print", response_class=HTMLResponse)
async def print_page(
    request: Request,
    namespace_name: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    user, new_token = await _current_user(request, db)
    settings = get_settings()

    try:
        page, ver = await page_svc.get_page(db, namespace_name, slug)
    except HTTPException as e:
        if e.status_code == 404:
            return templates.TemplateResponse(
                request,
                "page_not_found.html",
                _ctx(user, namespace_name=namespace_name, slug=slug),
                status_code=404,
            )
        raise

    rendered = ver.rendered if is_cache_valid(ver.rendered) else render_markup(
        ver.content, ver.format,
        namespace=namespace_name,
        base_url=settings.base_url,
    )
    categories = extract_categories(ver.content, ver.format)

    resp = templates.TemplateResponse(
        request,
        "page_print.html",
        _ctx(user,
             page=page,
             ver=ver,
             rendered=rendered,
             namespace_name=namespace_name,
             categories=categories),
    )
    _apply_new_token(resp, new_token, settings.access_token_expire_minutes)
    return resp


# -----------------------------------------------------------------------------
