#!/usr/bin/env python
#
#
# -----------------------------------------------------------------------------
"""
Render endpoint — live preview for the editor.

POST /api/v1/render   { "content": "...", "format": "markdown", "namespace": "Main", "slug": "" }
"""
# -----------------------------------------------------------------------------

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.services.attachments import attachment_url, list_attachments
from app.services.renderer import render


# -----------------------------------------------------------------------------

router = APIRouter(prefix="/render", tags=["render"])


class RenderRequest(BaseModel):
    content:   str = ""
    format:    str = "markdown"
    namespace: str = "Main"
    slug:      str = ""


# -----------------------------------------------------------------------------

async def _do_render(content: str, format: str, namespace: str, slug: str, db: AsyncSession) -> dict:
    """Shared render logic used by both POST and GET handlers."""
    settings = get_settings()
    att_map: dict[str, str] | None = None
    if slug:
        try:
            atts = await list_attachments(db, namespace, slug)
            if atts:
                att_map = {a.filename: attachment_url(a, settings.base_url) for a in atts}
        except Exception:
            pass
    html = render(content, format, namespace=namespace, base_url=settings.base_url, attachments=att_map)
    return {"html": html, "format": format}


@router.post("")
async def render_preview_post(
    body: RenderRequest,
    db:   AsyncSession = Depends(get_db),
):
    """Return rendered HTML for a snippet of wiki content — used by the live editor preview."""
    return await _do_render(body.content, body.format, body.namespace, body.slug, db)


@router.get("")
async def render_preview_get(
    content:   str = Query(default="", max_length=1_000_000),
    format:    str = Query(default="markdown"),
    namespace: str = Query(default="Main"),
    slug:      str = Query(default=""),
    db:        AsyncSession = Depends(get_db),
):
    """Backward-compatible GET endpoint — prefer POST for large content."""
    return await _do_render(content, format, namespace, slug, db)


# -----------------------------------------------------------------------------
