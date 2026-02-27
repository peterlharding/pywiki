#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Pages router
============
GET    /api/v1/namespaces/{ns}/pages                       — list pages
POST   /api/v1/namespaces/{ns}/pages                       — create page     [auth]
GET    /api/v1/namespaces/{ns}/pages/{slug}                — get latest (rendered)
GET    /api/v1/namespaces/{ns}/pages/{slug}/raw            — get raw source
GET    /api/v1/namespaces/{ns}/pages/{slug}/history        — version list
GET    /api/v1/namespaces/{ns}/pages/{slug}/diff/{a}/{b}   — diff two versions
PUT    /api/v1/namespaces/{ns}/pages/{slug}                — save new version [auth]
POST   /api/v1/namespaces/{ns}/pages/{slug}/rename         — rename page      [auth]
DELETE /api/v1/namespaces/{ns}/pages/{slug}                — delete page      [auth]
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user_id
from app.schemas import (
    DiffResponse, OKResponse,
    PageCreate, PageRename, PageResponse,
    PageSummary, PageUpdate, PageVersionResponse,
)
from app.services import pages as page_svc
from app.services.renderer import render


# -----------------------------------------------------------------------------

router = APIRouter(prefix="/namespaces/{namespace_name}/pages", tags=["pages"])


# -----------------------------------------------------------------------------

def _render_page(content: str, fmt: str, namespace_name: str) -> str:
    settings = get_settings()
    return render(content, fmt, namespace=namespace_name, base_url=settings.base_url)


# ── List ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PageSummary])
async def list_pages(
    namespace_name: str,
    skip:   int          = Query(0, ge=0),
    limit:  int          = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=256),
    db: AsyncSession     = Depends(get_db),
):
    return await page_svc.list_pages(db, namespace_name, skip=skip, limit=limit, search=search)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=PageResponse, status_code=201)
async def create_page(
    namespace_name: str,
    data: PageCreate,
    user_id: str     = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    page, ver = await page_svc.create_page(db, namespace_name, data, author_id=user_id)
    rendered = _render_page(ver.content, ver.format, namespace_name)
    ver.rendered = rendered
    return _page_response(namespace_name, page, ver, rendered)


# ── Read ──────────────────────────────────────────────────────────────────────

@router.get("/{slug}", response_model=PageResponse)
async def get_page(
    namespace_name: str,
    slug: str,
    version: Optional[int] = Query(None, ge=1),
    render_html: bool      = Query(True, alias="render"),
    db: AsyncSession       = Depends(get_db),
):
    page, ver = await page_svc.get_page(db, namespace_name, slug, version=version)

    rendered = None
    if render_html:
        cacheable = version is None
        if ver.rendered and cacheable:
            rendered = ver.rendered
        else:
            rendered = _render_page(ver.content, ver.format, namespace_name)
            if cacheable:
                ver.rendered = rendered

    return _page_response(namespace_name, page, ver, rendered)


# ── Raw source ────────────────────────────────────────────────────────────────

@router.get("/{slug}/raw")
async def get_page_raw(
    namespace_name: str,
    slug: str,
    version: Optional[int] = Query(None, ge=1),
    db: AsyncSession       = Depends(get_db),
):
    """Return raw Markdown / RST source as plain text."""
    page, ver = await page_svc.get_page(db, namespace_name, slug, version=version)
    return Response(content=ver.content, media_type="text/plain; charset=utf-8")


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/{slug}/history", response_model=list[PageVersionResponse])
async def get_history(
    namespace_name: str,
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    versions = await page_svc.get_page_history(db, namespace_name, slug)
    return [_ver_response(v) for v in versions]


# ── Diff ──────────────────────────────────────────────────────────────────────

@router.get("/{slug}/diff/{from_ver}/{to_ver}", response_model=DiffResponse)
async def get_diff(
    namespace_name: str,
    slug: str,
    from_ver: int,
    to_ver: int,
    db: AsyncSession = Depends(get_db),
):
    diff = await page_svc.get_diff(db, namespace_name, slug, from_ver, to_ver)
    return DiffResponse(
        namespace=namespace_name,
        slug=slug,
        from_version=from_ver,
        to_version=to_ver,
        diff=diff,
    )


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{slug}", response_model=PageResponse)
async def update_page(
    namespace_name: str,
    slug: str,
    data: PageUpdate,
    user_id: str     = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    page, ver = await page_svc.update_page(db, namespace_name, slug, data, author_id=user_id)
    rendered = _render_page(ver.content, ver.format, namespace_name)
    ver.rendered = rendered
    return _page_response(namespace_name, page, ver, rendered)


# ── Rename ────────────────────────────────────────────────────────────────────

@router.post("/{slug}/rename", response_model=OKResponse)
async def rename_page(
    namespace_name: str,
    slug: str,
    data: PageRename,
    user_id: str     = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    page = await page_svc.rename_page(db, namespace_name, slug, data, author_id=user_id)
    return OKResponse(message=f"Page renamed to '{data.new_title}' (slug: '{page.slug}')")


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{slug}", response_model=OKResponse)
async def delete_page(
    namespace_name: str,
    slug: str,
    user_id: str     = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    await page_svc.delete_page(db, namespace_name, slug)
    return OKResponse(message=f"Page '{slug}' deleted")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Response builders
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _page_response(namespace_name, page, ver, rendered) -> dict:
    return {
        "id":              page.id,
        "namespace":       namespace_name,
        "title":           page.title,
        "slug":            page.slug,
        "version":         ver.version,
        "content":         ver.content,
        "format":          ver.format,
        "rendered":        rendered,
        "author_id":       ver.author_id,
        "author_username": ver.author.username if ver.author else None,
        "comment":         ver.comment,
        "created_at":      page.created_at,
        "updated_at":      ver.created_at,
    }


# -----------------------------------------------------------------------------

def _ver_response(ver) -> dict:
    return {
        "id":              ver.id,
        "version":         ver.version,
        "content":         ver.content,
        "format":          ver.format,
        "author_id":       ver.author_id,
        "author_username": ver.author.username if ver.author else None,
        "comment":         ver.comment,
        "created_at":      ver.created_at,
    }


# -----------------------------------------------------------------------------
